"""Weekly AI growth-advisor email for Clearer Thinking.

Every Friday this:
  1. Builds the current 7-day period plus several prior 7-day buckets (the "track record"):
     GA4 (tools finished = Submitted Email, users/sessions, funnel conversion rates), Stripe
     (total + subscription revenue, PDF and cognitive-assessment sales, new subscriptions,
     cancellations with reasons) and beehiiv (new/unsubscribed subscribers, unsub rate).
  2. Takes a goals snapshot (gross revenue YTD, active subscribers, MRR, Google position for
     "personality test", average unique opens per campaign) against the targets in GOALS.md.
  3. Runs automatic data-quality checks so a broken data source reads as "probably a data
     problem", not as a business collapse.
  4. Loads the advisor's memory (advisor_memory.py): durable facts/preferences Igor has given,
     the audience/brand knowledge base, and the digests of Igor's Claude Code sessions this
     week (advisor_conversations.py) so the letter knows what he actually worked on.
  5. Asks Claude, in character as Igor's senior growth advisor, to write the ENTIRE email as
     one letter in three movements: results, the week's work, next week's priorities.
  6. Extracts any new durable facts from the week's sessions into the durable memory.
  7. Refreshes frontend/public/snapshot.json (same as fetch-snapshot.yml) so the dashboard
     linked at the bottom is current, then sends the letter via the Gmail API.

Robustness ("just send it if everything works, otherwise tell me why"):
  - Every data source is wrapped so one failure can't kill the run; failed sources are
    listed in the email with specific fix instructions.
  - If the email transport itself is down (the one thing that can't email you about
    itself), it falls back to a Slack alert with the reason + fix steps.

Run locally:   .venv/bin/python weekly_advisor.py --dry-run        # print, don't send
               .venv/bin/python weekly_advisor.py                  # send for real
On CI:         .github/workflows/weekly-advisor-email.yml (Fridays 11:00 UTC = 08:00 BRT)
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent


def _materialize_ci_secrets() -> None:
    """On CI the OAuth JSON blobs arrive as env vars; write them where the clients expect."""
    blobs = {
        "OAUTH_CLIENT_JSON": ROOT / "secrets" / "oauth-client.json",
        "GOOGLE_TOKEN_JSON": ROOT / "secrets" / "ga4-token.json",
    }
    for env_var, target in blobs.items():
        blob = os.environ.get(env_var, "").strip()
        if not blob:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blob)


load_dotenv()
_materialize_ci_secrets()

import advisor_memory as mem  # noqa: E402
import email_transport  # noqa: E402

# Imports that touch credentials happen after materialization.
from data_layer import (  # noqa: E402
    beehiiv_avg_unique_opens_per_campaign,
    beehiiv_daily_new_subscribers,
    beehiiv_metrics,
    ga4_audience_metrics,
    ga4_funnel_events,
    gsc_keyword_position,
    stripe_active_subscriber_count,
    stripe_charges_daily_by_amounts,
    stripe_current_mrr,
    stripe_metrics,
    stripe_new_subscribers_daily,
    stripe_revenue_by_category,
)

# --- config -----------------------------------------------------------------
PDF_AMOUNTS = (900,)            # $9.00 Personality Test PDF (non-subscription)
COG_AMOUNTS = (3500, 1750)      # $35.00 / $17.50 Cognitive Assessment
ADVISOR_MODEL = mem.advisor_model()

# Re-exported for advisor_reply.py, which reads wa.EMAIL_FROM.
EMAIL_FROM = email_transport.EMAIL_FROM
EMAIL_TO = os.getenv("ADVISOR_EMAIL_TO") or EMAIL_FROM

DASHBOARD_URL = "https://growth-advisor-clearerthinking.vercel.app/"
SNAPSHOT_FILE = ROOT / "frontend" / "public" / "snapshot.json"
GOALS_FILE = ROOT / "GOALS.md"

# Numeric targets behind GOALS.md (GOALS.md stays the source of truth for definitions and
# wording; keep these numbers in sync with it and with frontend/components/goals-table.tsx).
GOAL_TARGETS = {
    "gross_revenue_ytd_usd": 120_000,
    "active_subscribers": 100,
    "personality_test_google_position": 1,
    "avg_unique_opens_per_campaign": 100_000,
    "mrr_usd": 5_000,
}
PERSONALITY_KEYWORD = "personality test"

# Metrics checked by flag_data_anomalies (label -> week-dict key).
ANOMALY_METRICS = {
    "tools finished (GA4 Submitted Email)": "tools_finished",
    "GA4 users": "ga4_users",
    "total revenue": "revenue_total",
    "new newsletter subscribers": "new_subscribers",
    "emails sent": "emails_sent",
}


def load_memory(max_chars: int = 6000) -> str:
    """Durable memory (kept as a function so advisor_reply.py's import keeps working)."""
    return mem.load_durable_memory(max_chars=max_chars)


# Human-readable fix steps surfaced when a given source fails.
FIX_INSTRUCTIONS = {
    "ga4": "GA4 auth likely expired. Re-run `python auth_ga4.py` locally and update the "
           "GOOGLE_TOKEN_JSON GitHub secret with the new secrets/ga4-token.json.",
    "ga4_audience": "GA4 users/sessions query failed (same fix as ga4).",
    "stripe": "Check STRIPE_SECRET_KEY (rotated or revoked?) in .env and the GitHub secret.",
    "pdf_sales": "Stripe charge query failed. Check STRIPE_SECRET_KEY.",
    "cog_sales": "Stripe charge query failed. Check STRIPE_SECRET_KEY.",
    "stripe_new_subs": "Stripe subscriptions query failed. Check STRIPE_SECRET_KEY.",
    "stripe_cancellations": "Stripe events query failed. Check STRIPE_SECRET_KEY.",
    "beehiiv": "beehiiv API failed. Check BEEHIIV_API_KEY and BEEHIIV_PUB_CLEARER_THINKING "
               "in .env and the GitHub secrets.",
    "beehiiv_new_subs": "beehiiv subscriptions query failed. Check BEEHIIV_API_KEY / "
                        "BEEHIIV_PUB_CLEARER_THINKING.",
    "goals_gross_revenue_ytd_usd": "Stripe year-to-date charge listing failed. Check STRIPE_SECRET_KEY.",
    "goals_active_subscribers": "Stripe subscription count failed. Check STRIPE_SECRET_KEY.",
    "goals_mrr_usd": "Stripe MRR snapshot failed. Check STRIPE_SECRET_KEY.",
    "goals_personality_test_google_position": "Search Console query failed. Check GSC_SITE_URL and the Google token.",
    "goals_avg_unique_opens_per_campaign": "beehiiv posts listing failed. Check BEEHIIV_API_KEY.",
    "memory": "The advisor memory couldn't be decrypted. Make sure the GitHub secret "
              "ADVISOR_MEMORY_KEY matches ADVISOR_MEMORY_KEY in .env.",
    "conversations": "Conversation digests couldn't be read (see memory).",
    "narrative": "Claude API call failed. Check ANTHROPIC_API_KEY and account credits, "
                 f"and that the model id '{ADVISOR_MODEL}' is available (override with ADVISOR_MODEL).",
    "consolidation": "The end-of-week memory update failed (letter still sent). Same checks as narrative.",
    "transport": email_transport.TRANSPORT_FIX,
    "dashboard": "Snapshot refresh or publish failed. Run `python fetch_snapshot.py` locally to see the "
                 "real error, or check the fetch-snapshot.yml workflow logs.",
}


# --- small helpers ----------------------------------------------------------
def _safe(label: str, fn, *args, **kwargs):
    """Run fn; on failure return ('__error__', message) so callers can record it."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {label} failed: {e}", file=sys.stderr)
        return ("__error__", f"{type(e).__name__}: {e}")


def _is_err(v) -> bool:
    return isinstance(v, tuple) and len(v) == 2 and v[0] == "__error__"


def _ratio(num, den):
    """num/den as a float, or None if either is missing / den is 0."""
    if isinstance(num, (int, float)) and isinstance(den, (int, float)) and den:
        return num / den
    return None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _count_cancellations(start: date, end: date, with_reasons: bool) -> dict:
    """Subscriptions cancelled in [start, end] (inclusive days), via stripe_cancellations_report."""
    from stripe_cancellations_report import gather_cancellations

    s = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    e = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    rows = gather_cancellations(s, e)
    out = {"count": len(rows)}
    if with_reasons:
        out["reasons"] = [f"{r['product']}: {r['reason']}" for r in rows]
    return out


# --- gathering --------------------------------------------------------------
def gather_week(start: date, end: date, new_subscribers, current: bool = False) -> dict:
    """All KPIs for one 7-day window. Records per-source errors instead of raising.

    `new_subscribers` is computed once across the whole span (see gather_history) and
    passed in, because beehiiv's subscriptions endpoint has no date filter.
    """
    errors: dict[str, str] = {}

    def grab(label, fn, *a, **k):
        v = _safe(label, fn, *a, **k)
        if _is_err(v):
            errors[label] = v[1]
            return None
        return v

    funnel = grab("ga4", ga4_funnel_events, start, end)
    audience = grab("ga4_audience", ga4_audience_metrics, start, end)
    revenue = grab("stripe", stripe_metrics, start, end)
    rev_cat = grab("stripe", stripe_revenue_by_category, start, end)
    pdf = grab("pdf_sales", stripe_charges_daily_by_amounts, start, end, PDF_AMOUNTS, True)
    cog = grab("cog_sales", stripe_charges_daily_by_amounts, start, end, COG_AMOUNTS, False)
    new_subs = grab("stripe_new_subs", stripe_new_subscribers_daily, start, end)
    cancels = grab("stripe_cancellations", _count_cancellations, start, end, current)
    bh = grab("beehiiv", beehiiv_metrics, start, end)
    # beehiiv_metrics returns {"error": "..."} instead of raising on auth/config problems.
    if isinstance(bh, dict) and bh.get("error"):
        errors["beehiiv"] = bh["error"]

    viewed = (funnel or {}).get("viewed_privacy")
    accepted = (funnel or {}).get("accepted_privacy")
    submitted = (funnel or {}).get("submitted_email")
    aud = {k: v for k, v in (audience or {}).items() if isinstance(v, (int, float))}

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        # GA4
        "tools_finished": submitted,            # "Submitted Email" event
        "viewed_privacy": viewed,
        "accepted_privacy": accepted,
        "conv_view_to_accept": _ratio(accepted, viewed),
        "conv_accept_to_submit": _ratio(submitted, accepted),
        "ga4_users": aud.get("users", aud.get("total_users")),
        "ga4_sessions": aud.get("sessions"),
        # Stripe
        "revenue_total": (revenue or {}).get("revenue_usd"),
        "revenue_subscription": (revenue or {}).get("subscription_usd"),
        "pdf_sales": (pdf or {}).get("total"),
        "pdf_revenue": (rev_cat or {}).get("pdf"),
        "cognitive_sales": (cog or {}).get("total"),
        "cognitive_revenue": (rev_cat or {}).get("cognitive"),
        "new_stripe_subscriptions": (new_subs or {}).get("total"),
        "cancelled_subscriptions": (cancels or {}).get("count"),
        "cancellation_reasons": (cancels or {}).get("reasons"),
        # beehiiv newsletter
        "new_subscribers": new_subscribers,
        "unsubscribers": (bh or {}).get("unsubscribes"),
        "unsubscribe_rate": (bh or {}).get("unsubscribe_rate"),
        "emails_sent": (bh or {}).get("emails_sent"),
        "errors": errors,
    }


def gather_history(num_weeks: int, ref: date) -> list[dict]:
    """Most-recent-first list of week dicts. Current week = 7 days ending `ref` (yesterday)."""
    oldest_start = (ref - timedelta(days=7 * (num_weeks - 1))) - timedelta(days=6)

    # New subscribers: fetch the whole span ONCE (beehiiv subs endpoint has no date filter),
    # then bucket per week.
    daily_map: dict[str, int] = {}
    new_subs_err = None
    bh_daily = _safe("beehiiv_new_subs", beehiiv_daily_new_subscribers, oldest_start, ref)
    if _is_err(bh_daily):
        new_subs_err = bh_daily[1]
    elif isinstance(bh_daily, dict):
        if bh_daily.get("error"):
            new_subs_err = bh_daily["error"]
        for row in bh_daily.get("daily", []):
            daily_map[row["date"]] = row["count"]

    weeks = []
    for i in range(num_weeks):
        end = ref - timedelta(days=7 * i)
        start = end - timedelta(days=6)
        if new_subs_err:
            wk_new = None
        else:
            wk_new = sum(daily_map.get((start + timedelta(days=d)).isoformat(), 0) for d in range(7))
        wk = gather_week(start, end, wk_new, current=(i == 0))
        if new_subs_err:
            wk["errors"]["beehiiv_new_subs"] = new_subs_err
        weeks.append(wk)
    return weeks


def compute_goal_progress(current: dict, targets: dict = GOAL_TARGETS) -> dict:
    """Per goal: current value, target, and progress. For the Google position goal
    (lower is better) progress is expressed as the gap to #1 instead of a percentage."""
    out = {}
    for key, target in targets.items():
        cur = _num(current.get(key))
        row = {"current": cur, "target": target}
        if cur is None:
            row["progress_pct"] = None
        elif key == "personality_test_google_position":
            row["positions_from_target"] = round(cur - target, 1)
        else:
            row["progress_pct"] = round(100 * cur / target, 1) if target else None
        out[key] = row
    return out


def gather_goals(ref: date) -> tuple[dict, dict]:
    """Live goal values (each independently wrapped) and a per-goal error map."""
    errors: dict[str, str] = {}
    current: dict = {}

    def grab(key, fn, *a, **k):
        v = _safe(f"goals_{key}", fn, *a, **k)
        if _is_err(v):
            errors[f"goals_{key}"] = v[1]
            return None
        return v

    ytd = grab("gross_revenue_ytd_usd", stripe_metrics, date(ref.year, 1, 1), ref)
    current["gross_revenue_ytd_usd"] = (ytd or {}).get("gross_usd")
    current["active_subscribers"] = grab("active_subscribers", stripe_active_subscriber_count)
    current["mrr_usd"] = grab("mrr_usd", stripe_current_mrr)
    kw = grab("personality_test_google_position", gsc_keyword_position, PERSONALITY_KEYWORD)
    current["personality_test_google_position"] = (kw or {}).get("position")
    opens = grab("avg_unique_opens_per_campaign", beehiiv_avg_unique_opens_per_campaign)
    if isinstance(opens, dict) and opens.get("error"):
        errors["goals_avg_unique_opens_per_campaign"] = opens["error"]
        opens = None
    current["avg_unique_opens_per_campaign"] = (opens or {}).get("avg_unique_opens")

    goals = compute_goal_progress(current)
    goals["gross_revenue_ytd_usd"]["note"] = f"gross Stripe charges from {ref.year}-01-01 to {ref.isoformat()}"
    goals["personality_test_google_position"]["note"] = "GSC average position, last 28 days (lower is better)"
    if isinstance(opens, dict):
        goals["avg_unique_opens_per_campaign"]["note"] = (
            f"average over {opens.get('campaigns_count')} campaigns sent to >100k subscribers")
    return goals, errors


# --- data-quality checks -------------------------------------------------------
def flag_data_anomalies(history: list[dict]) -> list[str]:
    """Plain-language flags for the current week versus the prior weeks' track record.

    A zero/missing value where the prior median is clearly positive almost always means a
    broken source (expired token, API outage), so it's called out as a probable data problem.
    A value more than 3x the prior median is flagged for a double-count / bot-traffic check.
    """
    if not history:
        return []
    cur, prior = history[0], history[1:]
    flags = []
    for label, key in ANOMALY_METRICS.items():
        prior_vals = [v for v in (_num(w.get(key)) for w in prior) if v is not None]
        if len(prior_vals) < 2:
            continue
        med = statistics.median(prior_vals)
        if med <= 0:
            continue
        val = _num(cur.get(key))
        if val is None:
            flags.append(f"{label} is missing this week (prior median {med:,.0f}): probably a data "
                         f"source problem, not a real drop.")
        elif val == 0:
            flags.append(f"{label} is exactly 0 this week versus a prior median of {med:,.0f}: "
                         f"treat as a probable data problem unless independently confirmed.")
        elif val > 3 * med:
            flags.append(f"{label} is {val:,.0f}, more than 3x the prior median of {med:,.0f}: "
                         f"check for double counting, an import, or bot traffic before celebrating.")
    return flags


# --- narrative --------------------------------------------------------------
LETTER_SYSTEM = (
    "You are Igor's senior growth advisor for Clearer Thinking (clearerthinking.org), a "
    "publisher of free interactive self-insight tools that monetizes via a paid subscription, "
    "a $9 personality-test PDF, and a $35/$17.50 cognitive assessment, plus a beehiiv "
    "newsletter. He pays you to review the week and tell him straight what happened, what it "
    "means against his goals, and what he should do next week. You write like a real "
    "consultant emailing a client, not a report generator.\n\n"
    "You receive: the current 7-day period and several prior periods as JSON (most recent "
    "first); a goals snapshot with targets and progress; automatic data-quality flags; "
    "GOALS.md; durable memory of things Igor has told you; a knowledge base about the "
    "audience and how Clearer Thinking communicates; and digests of the Claude Code working "
    "sessions Igor had this week (what he actually worked on). Nobody else sees the raw "
    "numbers: you are the entire email.\n\n"
    "Write one letter of plain prose in three movements, without headers:\n"
    "1. Results. The handful of numbers that actually matter this week, each with enough "
    "context (versus prior weeks, versus his goals) to mean something on its own. Progress "
    "toward each goal where it moved. Anything abnormal versus the track record, named with "
    "the numbers behind it. When a data-quality flag says a metric probably broke, say that "
    "plainly instead of narrating a collapse. If nothing is off, say so in one line.\n"
    "2. The week's work. From the session digests: what he spent his time on, what shipped, "
    "what is still unfinished, and whether that effort is pointed at the goals. Call out "
    "drift honestly, and credit real progress specifically. If there are no digests, say "
    "you have no record of his work this week and move on.\n"
    "3. Next week. Three to five concrete priorities as a short numbered list (the one place "
    "a list is allowed), each tied to a goal or to a result above, specific enough to start "
    "on Monday morning. Prefer finishing open threads over starting new ones unless the "
    "numbers argue otherwise.\n\n"
    "Rules: 350 to 650 words. Cite a specific figure when it is the evidence for a point; "
    "never dump every metric. Never use em dashes. If data is missing (null fields), say so "
    "briefly and never invent numbers. Apply his standing preferences and past corrections "
    "from memory without restating them, and apply the audience knowledge when judging ideas. "
    "Tone: direct, a little informal, confident; skip the throat-clearing and get straight "
    "into it. No greeting and no sign-off: the email around your text already has both."
)

CONSOLIDATE_SYSTEM = (
    "You maintain the durable memory of Igor's growth advisor for Clearer Thinking. From this "
    "week's session digests, extract facts, preferences, corrections or standing context that "
    "will still matter in future weeks and are NOT already captured in the existing memory. "
    "Think: how he wants things done, what he cares about, decisions taken, recurring "
    "constraints, key numbers that define the business. Skip one-off task details.\n\n"
    "Return ONLY a JSON array (no prose) of up to 8 objects shaped "
    '{"entry": "<one or two self-contained sentences>", "category": "preference|correction|context"}. '
    "Return [] if there is nothing new. Never use em dashes."
)


def build_narrative(history: list[dict], goals: dict, flags: list[str], goals_text: str,
                    memory_text: str, knowledge_text: str, conversations_text: str) -> str:
    """Ask Claude to write the entire advisor letter (the whole email body)."""
    user = (
        f"Today is {date.today().isoformat()}.\n\n"
        f"GOALS.md:\n{goals_text or '(missing)'}\n\n"
        f"Goals snapshot (live values vs targets), JSON:\n{json.dumps(goals, indent=1, default=str)}\n\n"
        f"Data-quality flags:\n" + ("\n".join(f"- {f}" for f in flags) if flags else "- none") + "\n\n"
        f"Durable memory of things Igor has told you:\n{memory_text or '(nothing recorded yet)'}\n\n"
        f"Knowledge base (audience and communication):\n{knowledge_text or '(none)'}\n\n"
        f"Digests of Igor's working sessions this week:\n{conversations_text or '(no sessions recorded this week)'}\n\n"
        f"Weekly metrics (most recent first), JSON:\n{json.dumps(history, indent=1, default=str)}"
    )
    return mem.claude_text(LETTER_SYSTEM, user, max_tokens=4000)


def parse_json_array(text: str) -> list:
    """Pull the first JSON array out of a model reply; [] if there isn't a valid one."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        val = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return val if isinstance(val, list) else []


def consolidate_memory(conversations_text: str, memory_text: str) -> list[str]:
    """Extract new durable entries from the week's digests, append them, return the lines."""
    if not conversations_text.strip():
        return []
    user = (f"Existing durable memory:\n{memory_text or '(empty)'}\n\n"
            f"This week's session digests:\n{conversations_text}")
    reply = mem.claude_text(CONSOLIDATE_SYSTEM, user, max_tokens=2000)
    added = []
    for item in parse_json_array(reply):
        if not isinstance(item, dict):
            continue
        cat = item.get("category") if item.get("category") in ("preference", "correction", "context") else "context"
        line = mem.append_durable_memory(str(item.get("entry", "")), cat)
        if line:
            added.append(line)
    return added


# --- compose + send ---------------------------------------------------------
def collect_errors(history: list[dict], *extra: dict) -> dict[str, str]:
    errs: dict[str, str] = dict(history[0].get("errors", {})) if history else {}
    for e in extra:
        errs.update({k: v for k, v in e.items() if v})
    return errs


def build_email(history: list[dict], narrative: str, errors: dict[str, str]) -> tuple[str, str]:
    cur = history[0]
    flag = "⚠️ PARTIAL, some sources failed" if errors else ""
    subject = f"Weekly Growth Report, week of {cur['start']} {flag}".strip()

    parts = ["Hi Igor,", ""]
    if narrative:
        parts.append(narrative)
    else:
        parts.append(
            "Couldn't pull together my usual read on this week: the write-up failed to "
            "generate. See the data issue below."
        )

    if errors:
        parts.append("")
        parts.append("One more thing: a few pieces didn't come through, so some of the above "
                     "may be incomplete:")
        for src, msg in errors.items():
            parts.append(f"  • {src}: {msg}")
            fix = FIX_INSTRUCTIONS.get(src)
            if fix:
                parts.append(f"      Fix: {fix}")

    parts.append("")
    parts.append(f"Full dashboard: {DASHBOARD_URL}")
    parts.append("")
    parts.append("Talk next week.")
    parts.append("")
    parts.append("Reply to this email with any question and I'll answer.")
    return subject, "\n".join(parts)


# --- dashboard ----------------------------------------------------------------
def refresh_dashboard_snapshot() -> str | None:
    """Regenerate frontend/public/snapshot.json and push it if changed, so the dashboard
    linked in the email is current as of send time (not just the last <=30-min cron tick).
    Returns an error string on failure; never raises (this shouldn't block sending the report).
    """
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "fetch_snapshot.py")],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=20 * 60,
        )
    except subprocess.CalledProcessError as e:
        return f"fetch_snapshot.py failed: {e.stderr[-500:] if e.stderr else e}"
    except Exception as e:  # noqa: BLE001
        return f"fetch_snapshot.py failed: {e}"
    err = mem.git_commit_and_push([SNAPSHOT_FILE], f"snapshot: {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}")
    return f"couldn't publish updated snapshot: {err}" if err else None


# --- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=8, help="weeks of history (incl. current)")
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of sending")
    ap.add_argument("--ref", help="reference end date YYYY-MM-DD (default: yesterday)")
    ap.add_argument("--skip-consolidate", action="store_true", help="don't update durable memory")
    args = ap.parse_args()

    ref = date.fromisoformat(args.ref) if args.ref else date.today() - timedelta(days=1)
    print(f"[advisor] building {args.weeks} weeks ending {ref}...", file=sys.stderr)
    history = gather_history(args.weeks, ref)
    print("[advisor] goals snapshot...", file=sys.stderr)
    goals, goal_errors = gather_goals(ref)
    flags = flag_data_anomalies(history)
    for f in flags:
        print(f"[advisor] flag: {f}", file=sys.stderr)

    goals_text = GOALS_FILE.read_text()[:4000] if GOALS_FILE.exists() else ""
    mem_errors: dict[str, str] = {}
    memory_text = knowledge_text = conversations_text = ""
    try:
        memory_text = mem.load_durable_memory()
        knowledge_text = mem.load_knowledge()
        conversations_text = mem.load_recent_conversations(days=7, ref=date.today())
    except Exception as e:  # noqa: BLE001
        mem_errors["memory"] = f"{type(e).__name__}: {e}"
        print(f"[warn] memory unavailable: {e}", file=sys.stderr)
    print(f"[advisor] memory: {len(memory_text)} chars durable, {len(knowledge_text)} chars knowledge, "
          f"{len(conversations_text)} chars of session digests", file=sys.stderr)

    narrative, narrative_err = "", None
    try:
        narrative = build_narrative(history, goals, flags, goals_text, memory_text, knowledge_text, conversations_text)
    except Exception as e:  # noqa: BLE001
        narrative_err = f"{type(e).__name__}: {e}"
        print(f"[warn] narrative failed: {e}", file=sys.stderr)

    consolidation_err = None
    if not args.dry_run and not args.skip_consolidate and not mem_errors:
        try:
            added = consolidate_memory(conversations_text, memory_text)
            print(f"[advisor] durable memory: {len(added)} new entries", file=sys.stderr)
            if added:
                err = mem.git_commit_and_push([mem.DURABLE_FILE], "advisor memory: weekly consolidation")
                if err:
                    consolidation_err = err
        except Exception as e:  # noqa: BLE001
            consolidation_err = f"{type(e).__name__}: {e}"
            print(f"[warn] consolidation failed: {e}", file=sys.stderr)

    errors = collect_errors(history, goal_errors, mem_errors,
                            {"narrative": narrative_err, "consolidation": consolidation_err})

    if args.dry_run:
        print("[advisor] --dry-run: skipping dashboard snapshot refresh.", file=sys.stderr)
    else:
        print("[advisor] refreshing dashboard snapshot...", file=sys.stderr)
        dashboard_err = refresh_dashboard_snapshot()
        if dashboard_err:
            errors["dashboard"] = dashboard_err
            print(f"[warn] dashboard refresh failed: {dashboard_err}", file=sys.stderr)

    subject, body = build_email(history, narrative, errors)

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(body)
        return 0

    try:
        email_transport.send_email(subject, body, EMAIL_TO, from_label="CT Growth Advisor", header_tag="report")
        print("[advisor] email sent.", file=sys.stderr)
        return 0
    except Exception as e:  # noqa: BLE001
        reason = f"{type(e).__name__}: {e}"
        print(f"[error] email send failed: {reason}", file=sys.stderr)
        traceback.print_exc()
        extra_fix = "Check GMAIL_APP_PASSWORD (App Password may be revoked/expired) or run `.venv/bin/python weekly_advisor.py --dry-run` to inspect."
        if email_transport.slack_fallback(reason, "Weekly growth report", extra_fix):
            print("[advisor] notified via Slack fallback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
