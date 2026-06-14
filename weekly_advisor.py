"""Weekly AI growth-advisor email for Clearer Thinking.

Every Friday this:
  1. Builds the current 7-day period plus several prior 7-day buckets (the "track record").
  2. Computes the exact metrics Igor asked for (traffic + email submits by source,
     total / subscription / non-subscription revenue, PDF sales, cognitive-assessment
     sales, new subscribers, cancelled subscribers, GSC clicks/impressions).
  3. Asks Claude (acting as a growth advisor) to write the analysis: anomalies vs the
     prior weeks, plus insights / tips / concerns.
  4. Sends it as a plain-text email via Gmail SMTP.

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
    ga4_audience_metrics,
    ga4_modules_finished_by_channel,
    stripe_charges_daily_by_amounts,
    stripe_metrics,
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
    "submits_by_channel": "GA4 auth likely expired (see GOOGLE_TOKEN_JSON secret / `python auth_ga4.py`).",
    "stripe": "Check STRIPE_SECRET_KEY (rotated or revoked?) in .env and the GitHub secret.",
    "pdf_sales": "Stripe charge query failed — check STRIPE_SECRET_KEY.",
    "cog_sales": "Stripe charge query failed — check STRIPE_SECRET_KEY.",
    "subs": "Stripe subscription query failed — check STRIPE_SECRET_KEY.",
    "gsc": "Search Console auth likely expired — refresh the GOOGLE_TOKEN_JSON secret "
           "(same OAuth token as GA4) or confirm GSC_SITE_URL.",
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


# --- direct-client helpers not in data_layer --------------------------------
def ga4_sessions_by_channel(start: date, end: date) -> list[dict]:
    """Sessions grouped by default channel group — i.e. sources of traffic."""
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        OrderBy,
        RunReportRequest,
    )
    from ga4_client import get_client, property_path

    resp = get_client().run_report(RunReportRequest(
        property=property_path(),
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    ))
    return [
        {"channel": r.dimension_values[0].value or "(not set)", "sessions": int(r.metric_values[0].value)}
        for r in resp.rows
    ]


def stripe_sub_changes(start: date, end: date) -> dict:
    """New and cancelled subscription counts within [start, end] (UTC)."""
    from stripe_client import get_client

    s = get_client()
    start_ts = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp()) + 86400

    new = cancelled = 0
    for sub in s.Subscription.list(status="all", limit=100).auto_paging_iter():
        created = getattr(sub, "created", None)
        if created and start_ts <= created < end_ts:
            new += 1
        cancel_ts = getattr(sub, "canceled_at", None)
        if cancel_ts and start_ts <= cancel_ts < end_ts:
            cancelled += 1
    return {"new": new, "cancelled": cancelled}


def gsc_weekly_totals(start: date, end: date) -> dict:
    """Total clicks + impressions from Search Console for the window."""
    from gsc_client import SITE_URL, get_client

    if not SITE_URL:
        raise RuntimeError("GSC_SITE_URL not set")
    svc = get_client()
    resp = svc.searchanalytics().query(
        siteUrl=SITE_URL,
        body={"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": []},
    ).execute()
    rows = resp.get("rows", [])
    if not rows:
        return {"clicks": 0, "impressions": 0}
    r = rows[0]
    return {"clicks": int(r.get("clicks", 0)), "impressions": int(round(r.get("impressions", 0)))}


# --- gathering --------------------------------------------------------------
def gather_week(start: date, end: date) -> dict:
    """All metrics for one 7-day window. Records per-source errors instead of raising."""
    errors: dict[str, str] = {}

    def grab(label, fn, *a, **k):
        v = _safe(label, fn, *a, **k)
        if _is_err(v):
            errors[label] = v[1]
            return None
        return v

    audience = grab("ga4", ga4_audience_metrics, start, end)
    traffic = grab("ga4", ga4_sessions_by_channel, start, end)
    submits = grab("submits_by_channel", ga4_modules_finished_by_channel, start, end)
    revenue = grab("stripe", stripe_metrics, start, end)
    pdf = grab("pdf_sales", stripe_charges_daily_by_amounts, start, end, PDF_AMOUNTS, True)
    cog = grab("cog_sales", stripe_charges_daily_by_amounts, start, end, COG_AMOUNTS, False)
    subs = grab("subs", stripe_sub_changes, start, end)
    gsc = grab("gsc", gsc_weekly_totals, start, end)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "users": (audience or {}).get("users"),
        "sessions": (audience or {}).get("sessions"),
        "email_submits": (audience or {}).get("modules_finished"),
        "traffic_by_channel": traffic,
        "submits_by_channel": submits,
        "revenue_total": (revenue or {}).get("revenue_usd"),
        "revenue_subscription": (revenue or {}).get("subscription_usd"),
        "revenue_non_subscription": (revenue or {}).get("non_subscription_usd"),
        "pdf_sales": (pdf or {}).get("total"),
        "cognitive_sales": (cog or {}).get("total"),
        "new_subscribers": (subs or {}).get("new"),
        "cancelled_subscribers": (subs or {}).get("cancelled"),
        "gsc_clicks": (gsc or {}).get("clicks"),
        "gsc_impressions": (gsc or {}).get("impressions"),
        "errors": errors,
    }


def gather_history(num_weeks: int, ref: date) -> list[dict]:
    """Most-recent-first list of week dicts. Current week = 7 days ending `ref` (yesterday)."""
    weeks = []
    for i in range(num_weeks):
        end = ref - timedelta(days=7 * i)
        start = end - timedelta(days=6)
        weeks.append(gather_week(start, end))
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


def build_glance(cur: dict, prev: dict) -> str:
    """Deterministic, always-accurate metrics block."""
    L = []
    L.append("— THIS WEEK AT A GLANCE —")
    L.append(f"Period: {cur['start']} → {cur['end']} (vs prior 7 days {prev.get('start','?')} → {prev.get('end','?')})")
    L.append("")
    L.append("TRAFFIC & ENGAGEMENT (GA4)")
    L.append(f"  Users:          {_num(cur['users'])}{_delta(cur['users'], prev.get('users'))}")
    L.append(f"  Sessions:       {_num(cur['sessions'])}{_delta(cur['sessions'], prev.get('sessions'))}")
    L.append(f"  Email submits:  {_num(cur['email_submits'])}{_delta(cur['email_submits'], prev.get('email_submits'))}")
    if cur.get("traffic_by_channel"):
        L.append("  Traffic sources (sessions):")
        for r in cur["traffic_by_channel"][:6]:
            L.append(f"    - {r['channel']}: {_num(r['sessions'])}")
    if cur.get("submits_by_channel"):
        L.append("  Email submits by source:")
        for r in cur["submits_by_channel"][:6]:
            L.append(f"    - {r['channel']}: {_num(r['count'])}")
    L.append("")
    L.append("REVENUE (Stripe)")
    L.append(f"  Total:              {_money(cur['revenue_total'])}{_money_delta(cur['revenue_total'], prev.get('revenue_total'))}")
    L.append(f"  Subscription:       {_money(cur['revenue_subscription'])}{_money_delta(cur['revenue_subscription'], prev.get('revenue_subscription'))}")
    L.append(f"  Non-subscription:   {_money(cur['revenue_non_subscription'])}{_money_delta(cur['revenue_non_subscription'], prev.get('revenue_non_subscription'))}")
    L.append("")
    L.append("SALES & SUBSCRIBERS (Stripe)")
    L.append(f"  Personality PDF sales ($9):        {_num(cur['pdf_sales'])}{_delta(cur['pdf_sales'], prev.get('pdf_sales'))}")
    L.append(f"  Cognitive assessment sales ($35/$17.50): {_num(cur['cognitive_sales'])}{_delta(cur['cognitive_sales'], prev.get('cognitive_sales'))}")
    L.append(f"  New subscribers:                   {_num(cur['new_subscribers'])}{_delta(cur['new_subscribers'], prev.get('new_subscribers'))}")
    L.append(f"  Cancelled subscribers (churn):     {_num(cur['cancelled_subscribers'])}{_delta(cur['cancelled_subscribers'], prev.get('cancelled_subscribers'))}")
    L.append("")
    L.append("SEARCH (Google Search Console)")
    L.append(f"  Clicks:       {_num(cur['gsc_clicks'])}{_delta(cur['gsc_clicks'], prev.get('gsc_clicks'))}")
    L.append(f"  Impressions:  {_num(cur['gsc_impressions'])}{_delta(cur['gsc_impressions'], prev.get('gsc_impressions'))}")
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
        "subscription, a $9 personality-test PDF, and a $35/$17.50 cognitive assessment. "
        "You are writing the analysis section of a weekly email to Igor, who runs growth. "
        "You are given the current 7-day period and several prior 7-day periods (most recent "
        "first) as JSON. The exact numbers are already shown to Igor in a separate table, so "
        "do NOT just restate every figure. Instead:\n"
        "1) ANOMALIES: call out anything that looks abnormal or unexpected vs the prior weeks' "
        "track record (sharp moves, reversals, new zero values, suspicious spikes). If nothing "
        "is abnormal, say so plainly.\n"
        "2) INSIGHTS / TIPS / CONCERNS: 3-6 crisp, specific, actionable points a sharp advisor "
        "overseeing this business would raise this week, grounded in the data and the goals.\n"
        "Write PLAIN TEXT only — no markdown, no asterisks, no headers with '#'. Use short "
        "paragraphs or simple dashes. Be direct and concise. Note explicitly if some data was "
        "missing this week (fields will be null)."
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
    parts.append(build_glance(cur, prev))
    parts.append("")
    parts.append("— ADVISOR NOTES —")
    parts.append(narrative if narrative else "(Advisor analysis unavailable this week — see data issues below.)")

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
    parts.append("Sent automatically by your AI growth advisor (weekly_advisor.py).")
    return subject, "\n".join(parts)


def _build_mime(subject: str, body: str) -> MIMEText:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"CT Growth Advisor <{EMAIL_FROM}>"
    msg["To"] = EMAIL_TO
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
