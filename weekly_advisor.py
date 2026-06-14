"""Weekly AI growth-advisor email for Clearer Thinking.

Every Friday this:
  1. Builds the current 7-day period plus several prior 7-day buckets (the "track record").
  2. Computes Section 1 KPIs: tools finished (GA4 Submitted Email), total + subscription
     revenue (Stripe), personality-PDF and cognitive-assessment sale counts + revenue
     (Stripe), new + unsubscribed newsletter subscribers and unsub rate (beehiiv), and the
     two GA4 funnel conversion rates (Viewed→Accepted, Accepted→Submitted privacy policy).
  3. Asks Claude (acting as a growth advisor) to write Section 2 (anomalies vs prior weeks)
     and Section 3 (the three most important insights).
  4. Sends it as a plain-text email via the Gmail API (SMTP fallback locally).

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
import os
import smtplib
import ssl
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
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

# Imports that touch credentials happen after materialization.
from data_layer import (  # noqa: E402
    beehiiv_daily_new_subscribers,
    beehiiv_metrics,
    ga4_funnel_events,
    stripe_charges_daily_by_amounts,
    stripe_metrics,
    stripe_revenue_by_category,
)

# --- config -----------------------------------------------------------------
PDF_AMOUNTS = (900,)            # $9.00 Personality Test PDF (non-subscription)
COG_AMOUNTS = (3500, 1750)      # $35.00 / $17.50 Cognitive Assessment
ADVISOR_MODEL = os.getenv("ADVISOR_MODEL") or os.getenv("ANTHROPIC_MODEL") or "claude-opus-4-8"

EMAIL_FROM = os.getenv("GMAIL_ADDRESS", "igormscaldini@gmail.com")
EMAIL_TO = os.getenv("ADVISOR_EMAIL_TO", EMAIL_FROM)
# Gmail app passwords are 16 chars; Google displays them in 4 space-separated groups.
# Strip spaces so the secret works whether pasted with or without them.
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

# Human-readable fix steps surfaced when a given source fails.
FIX_INSTRUCTIONS = {
    "ga4": "GA4 auth likely expired. Re-run `python auth_ga4.py` locally and update the "
           "GOOGLE_TOKEN_JSON GitHub secret with the new secrets/ga4-token.json.",
    "stripe": "Check STRIPE_SECRET_KEY (rotated or revoked?) in .env and the GitHub secret.",
    "pdf_sales": "Stripe charge query failed — check STRIPE_SECRET_KEY.",
    "cog_sales": "Stripe charge query failed — check STRIPE_SECRET_KEY.",
    "beehiiv": "beehiiv API failed — check BEEHIIV_API_KEY and BEEHIIV_PUB_CLEARER_THINKING "
               "in .env and the GitHub secrets.",
    "beehiiv_new_subs": "beehiiv subscriptions query failed — check BEEHIIV_API_KEY / "
                        "BEEHIIV_PUB_CLEARER_THINKING.",
    "narrative": "Claude API call failed — check ANTHROPIC_API_KEY and account credits, "
                 f"and that the model id '{ADVISOR_MODEL}' is available (override with ADVISOR_MODEL).",
    "transport": "Email send failed. The Gmail API needs the gmail.send scope on the shared "
                 "Google token — re-run `python auth_ga4.py` to re-consent, then update the "
                 "GOOGLE_TOKEN_JSON secret. (SMTP fallback only works from your local IP.) ",
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


# --- small math helper ------------------------------------------------------
def _ratio(num, den):
    """num/den as a float, or None if either is missing / den is 0."""
    if isinstance(num, (int, float)) and isinstance(den, (int, float)) and den:
        return num / den
    return None


# --- gathering --------------------------------------------------------------
def gather_week(start: date, end: date, new_subscribers) -> dict:
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
    revenue = grab("stripe", stripe_metrics, start, end)
    rev_cat = grab("stripe", stripe_revenue_by_category, start, end)
    pdf = grab("pdf_sales", stripe_charges_daily_by_amounts, start, end, PDF_AMOUNTS, True)
    cog = grab("cog_sales", stripe_charges_daily_by_amounts, start, end, COG_AMOUNTS, False)
    bh = grab("beehiiv", beehiiv_metrics, start, end)
    # beehiiv_metrics returns {"error": "..."} instead of raising on auth/config problems.
    if isinstance(bh, dict) and bh.get("error"):
        errors["beehiiv"] = bh["error"]

    viewed = (funnel or {}).get("viewed_privacy")
    accepted = (funnel or {}).get("accepted_privacy")
    submitted = (funnel or {}).get("submitted_email")

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        # GA4
        "tools_finished": submitted,            # "Submitted Email" event
        "viewed_privacy": viewed,
        "accepted_privacy": accepted,
        "conv_view_to_accept": _ratio(accepted, viewed),
        "conv_accept_to_submit": _ratio(submitted, accepted),
        # Stripe
        "revenue_total": (revenue or {}).get("revenue_usd"),
        "revenue_subscription": (revenue or {}).get("subscription_usd"),
        "pdf_sales": (pdf or {}).get("total"),
        "pdf_revenue": (rev_cat or {}).get("pdf"),
        "cognitive_sales": (cog or {}).get("total"),
        "cognitive_revenue": (rev_cat or {}).get("cognitive"),
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
        wk = gather_week(start, end, wk_new)
        if new_subs_err:
            wk["errors"]["beehiiv_new_subs"] = new_subs_err
        weeks.append(wk)
    return weeks


# --- formatting -------------------------------------------------------------
def _money(v) -> str:
    return f"${v:,.2f}" if isinstance(v, (int, float)) else "n/a"


def _num(v) -> str:
    return f"{v:,}" if isinstance(v, (int, float)) else "n/a"


def _delta(cur, prev) -> str:
    if not isinstance(cur, (int, float)) or not isinstance(prev, (int, float)):
        return ""
    diff = cur - prev
    if prev:
        pct = diff / prev * 100
        arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "—")
        return f" ({arrow} {diff:+,.0f}, {pct:+.0f}% WoW)"
    return f" ({diff:+,.0f} WoW)"


def _money_delta(cur, prev) -> str:
    if not isinstance(cur, (int, float)) or not isinstance(prev, (int, float)):
        return ""
    diff = cur - prev
    if prev:
        pct = diff / prev * 100
        arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "—")
        return f" ({arrow} {diff:+,.0f} USD, {pct:+.0f}% WoW)"
    return f" ({diff:+,.0f} USD WoW)"


def _pct(v) -> str:
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "n/a"


def _pct_delta(cur, prev) -> str:
    """Percentage-point change for rate metrics."""
    if not isinstance(cur, (int, float)) or not isinstance(prev, (int, float)):
        return ""
    pp = (cur - prev) * 100
    arrow = "▲" if pp > 0 else ("▼" if pp < 0 else "—")
    return f" ({arrow} {pp:+.1f}pp WoW)"


def build_kpis(cur: dict, prev: dict) -> str:
    """Section 1 — deterministic, always-accurate KPI block."""
    L = []
    L.append("SECTION 1: MAIN KPIs")
    L.append(f"Period: {cur['start']} → {cur['end']} (vs prior 7 days {prev.get('start','?')} → {prev.get('end','?')})")
    L.append("")
    L.append(f"  Tools Finished (Submitted Email):   {_num(cur['tools_finished'])}{_delta(cur['tools_finished'], prev.get('tools_finished'))}")
    L.append(f"  Total Revenue:                      {_money(cur['revenue_total'])}{_money_delta(cur['revenue_total'], prev.get('revenue_total'))}")
    L.append(f"  Revenue from Subscriptions:         {_money(cur['revenue_subscription'])}{_money_delta(cur['revenue_subscription'], prev.get('revenue_subscription'))}")
    L.append(f"  Personality PDF ($9):               {_num(cur['pdf_sales'])} sales · {_money(cur['pdf_revenue'])}{_delta(cur['pdf_sales'], prev.get('pdf_sales'))}")
    L.append(f"  Cognitive Assessment ($35/$17.50):  {_num(cur['cognitive_sales'])} sales · {_money(cur['cognitive_revenue'])}{_delta(cur['cognitive_sales'], prev.get('cognitive_sales'))}")
    L.append(f"  New Newsletter Subscribers:         {_num(cur['new_subscribers'])}{_delta(cur['new_subscribers'], prev.get('new_subscribers'))}")
    L.append(f"  Newsletter Unsubscribers:           {_num(cur['unsubscribers'])}{_delta(cur['unsubscribers'], prev.get('unsubscribers'))}")
    L.append(f"  Unsubscription Rate:                {_pct(cur['unsubscribe_rate'])}{_pct_delta(cur['unsubscribe_rate'], prev.get('unsubscribe_rate'))}")
    L.append(f"  Viewed → Accepted Privacy Policy:   {_pct(cur['conv_view_to_accept'])}{_pct_delta(cur['conv_view_to_accept'], prev.get('conv_view_to_accept'))}")
    L.append(f"  Accepted Privacy → Email Submitted: {_pct(cur['conv_accept_to_submit'])}{_pct_delta(cur['conv_accept_to_submit'], prev.get('conv_accept_to_submit'))}")
    return "\n".join(L)


# --- narrative --------------------------------------------------------------
def build_narrative(history: list[dict], goals_text: str) -> str:
    """Ask Claude, as a growth advisor, to analyze anomalies + give insights/tips/concerns."""
    import json

    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    system = (
        "You are a seasoned growth advisor for Clearer Thinking (clearerthinking.org), a "
        "publisher of free interactive self-insight tools that monetizes via a paid "
        "subscription, a $9 personality-test PDF, and a $35/$17.50 cognitive assessment, plus "
        "a beehiiv newsletter. You are writing two sections of a weekly email to Igor, who runs "
        "growth. You are given the current 7-day period and several prior 7-day periods (most "
        "recent first) as JSON. Section 1 (the KPI table) is already shown to Igor, so do NOT "
        "restate every figure. Output EXACTLY these two sections, with these exact headers:\n\n"
        "SECTION 2: ANOMALIES\n"
        "Call out anything abnormal or unexpected versus the prior weeks' track record (sharp "
        "moves, reversals, new zero values, suspicious spikes). Reference concrete numbers. If "
        "nothing is abnormal, say so in one line.\n\n"
        "SECTION 3: INSIGHTS\n"
        "Exactly THREE insights — the three most important this week. Number them 1-3. Each one "
        "very straightforward: one or two sentences, specific and actionable. No preamble.\n\n"
        "Write PLAIN TEXT only — no markdown, no asterisks, no '#'. Be direct and concise. If "
        "some data is missing (null fields), note it briefly rather than inventing numbers."
    )
    user = (
        f"GOALS.md:\n{goals_text}\n\n"
        f"Weekly metrics (most recent first), JSON:\n{json.dumps(history, indent=2, default=str)}"
    )
    msg = client.messages.create(
        model=ADVISOR_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


# --- compose + send ---------------------------------------------------------
def collect_errors(history: list[dict], narrative_err: str | None) -> dict[str, str]:
    errs: dict[str, str] = {}
    for src, msg in history[0].get("errors", {}).items():
        errs[src] = msg
    if narrative_err:
        errs["narrative"] = narrative_err
    return errs


def build_email(history: list[dict], narrative: str, errors: dict[str, str]) -> tuple[str, str]:
    cur, prev = history[0], (history[1] if len(history) > 1 else {})
    flag = "⚠️ PARTIAL — some sources failed" if errors else ""
    subject = f"Weekly Growth Report — week of {cur['start']} {flag}".strip()

    parts = [f"Clearer Thinking — Weekly Growth Report", f"Week of {cur['start']} to {cur['end']}", ""]
    parts.append(build_kpis(cur, prev))
    parts.append("")
    if narrative:
        parts.append(narrative)
    else:
        parts.append("SECTION 2: ANOMALIES")
        parts.append("(Unavailable this week — see data issues below.)")
        parts.append("")
        parts.append("SECTION 3: INSIGHTS")
        parts.append("(Unavailable this week — see data issues below.)")

    if errors:
        parts.append("")
        parts.append("— ⚠️ DATA ISSUES THIS WEEK —")
        parts.append("Some sources couldn't be reached, so the figures above may be incomplete:")
        for src, msg in errors.items():
            parts.append(f"  • {src}: {msg}")
            fix = FIX_INSTRUCTIONS.get(src)
            if fix:
                parts.append(f"      Fix: {fix}")

    parts.append("")
    parts.append("— end of report —")
    parts.append("Reply to this email with any question and your AI growth advisor will answer.")
    return subject, "\n".join(parts)


def _build_mime(subject: str, body: str) -> MIMEText:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"CT Growth Advisor <{EMAIL_FROM}>"
    msg["To"] = EMAIL_TO
    # Marks this as advisor-sent so the reply poller never tries to "answer" our own report.
    msg["X-CT-Advisor"] = "report"
    return msg


def send_via_gmail_api(subject: str, body: str) -> None:
    """Send through the Gmail API using the shared Google OAuth token (needs gmail.send scope).

    This is the primary transport: it works from cloud IPs (GitHub Actions), unlike Gmail
    SMTP app-password login, which Google blocks from datacenter ranges.
    """
    import base64

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    from ga4_client import TOKEN_FILE

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw = base64.urlsafe_b64encode(_build_mime(subject, body).as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()


def send_via_smtp(subject: str, body: str) -> None:
    """Fallback transport (works locally; Google blocks it from cloud IPs)."""
    if not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_APP_PASSWORD not set")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(EMAIL_FROM, GMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], _build_mime(subject, body).as_string())


def send_email(subject: str, body: str) -> None:
    """Try the Gmail API first, then SMTP. Raise with both errors if both fail."""
    try:
        send_via_gmail_api(subject, body)
        return
    except Exception as api_err:  # noqa: BLE001
        print(f"[warn] Gmail API send failed: {api_err}", file=sys.stderr)
        try:
            send_via_smtp(subject, body)
            return
        except Exception as smtp_err:  # noqa: BLE001
            raise RuntimeError(
                f"Gmail API failed ({api_err}); SMTP fallback failed ({smtp_err})"
            ) from smtp_err


def slack_fallback(reason: str) -> bool:
    """Last resort when email transport is down. Returns True if Slack accepted the message."""
    token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    channel = os.getenv("SLACK_DEFAULT_CHANNEL", "").strip()
    if not token or not channel:
        return False
    import requests

    text = (
        ":warning: Weekly growth report could not be emailed.\n"
        f"Reason: {reason}\n"
        "Fix: " + FIX_INSTRUCTIONS.get("transport", "")
        + "Check GMAIL_APP_PASSWORD (App Password may be revoked/expired) or run "
        "`.venv/bin/python weekly_advisor.py --dry-run` to inspect."
    )
    try:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": text},
            timeout=15,
        )
        return r.ok and r.json().get("ok", False)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] slack fallback failed: {e}", file=sys.stderr)
        return False


# --- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=8, help="weeks of history (incl. current)")
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of sending")
    ap.add_argument("--ref", help="reference end date YYYY-MM-DD (default: yesterday)")
    args = ap.parse_args()

    ref = date.fromisoformat(args.ref) if args.ref else date.today() - timedelta(days=1)
    print(f"[advisor] building {args.weeks} weeks ending {ref}...", file=sys.stderr)
    history = gather_history(args.weeks, ref)

    goals_text = ""
    gp = ROOT / "GOALS.md"
    if gp.exists():
        goals_text = gp.read_text()[:4000]

    narrative, narrative_err = "", None
    try:
        narrative = build_narrative(history, goals_text)
    except Exception as e:  # noqa: BLE001
        narrative_err = f"{type(e).__name__}: {e}"
        print(f"[warn] narrative failed: {e}", file=sys.stderr)

    errors = collect_errors(history, narrative_err)
    subject, body = build_email(history, narrative, errors)

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(body)
        return 0

    try:
        send_email(subject, body)
        print("[advisor] email sent.", file=sys.stderr)
        return 0
    except Exception as e:  # noqa: BLE001
        reason = f"{type(e).__name__}: {e}"
        print(f"[error] email send failed: {reason}", file=sys.stderr)
        traceback.print_exc()
        if slack_fallback(reason):
            print("[advisor] notified via Slack fallback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
