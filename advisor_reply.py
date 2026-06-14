"""Reply handler for the weekly growth-advisor email.

When Igor replies to a "Weekly Growth Report" email with a question, this:
  1. Finds unread replies in those threads (Gmail API).
  2. Hands the question to Claude with live data tools (GA4 / Stripe / beehiiv / GSC),
     so it can pull specific, on-demand data to answer — not just reuse the weekly numbers.
  3. Replies in the same thread with the answer (Gmail API).
  4. Marks the message read so it's never answered twice.

Runs on a short cron (.github/workflows/advisor-reply.yml). Outgoing advisor mail carries
an `X-CT-Advisor` header so the poller never tries to "answer" its own messages.

Run locally:   .venv/bin/python advisor_reply.py --dry-run   # find + answer, print, don't send
               .venv/bin/python advisor_reply.py             # answer + send for real
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from datetime import date, timedelta
from email.mime.text import MIMEText

# weekly_advisor runs load_dotenv + secret materialization at import time, and exposes
# the config + data helpers we reuse here.
import weekly_advisor as wa
from data_layer import (
    beehiiv_metrics,
    ga4_audience_metrics,
    ga4_funnel_events,
    ga4_modules_finished_by_campaign,
    ga4_modules_finished_by_channel,
    gsc_keyword_position,
    stripe_charges_daily_by_amounts,
    stripe_metrics,
    stripe_revenue_by_category,
    stripe_revenue_by_product,
)

ADVISOR_HEADER = "X-CT-Advisor"
SUBJECT_MATCH = "Weekly Growth Report"
MAX_TOOL_TURNS = 8


# --- data tools exposed to Claude -------------------------------------------
def _default_range(start, end):
    """Default to the last 7 days (ending yesterday) when dates are omitted."""
    e = date.fromisoformat(end) if end else date.today() - timedelta(days=1)
    s = date.fromisoformat(start) if start else e - timedelta(days=6)
    return s, e


def _tool_weekly_history(num_weeks=4, **_):
    ref = date.today() - timedelta(days=1)
    return wa.gather_history(int(num_weeks), ref)


def _tool_ga4_metrics(start=None, end=None, **_):
    s, e = _default_range(start, end)
    out = ga4_audience_metrics(s, e)
    out.update(ga4_funnel_events(s, e))
    return out


def _tool_ga4_by_channel(start=None, end=None, **_):
    s, e = _default_range(start, end)
    return {
        "email_submits_by_channel": ga4_modules_finished_by_channel(s, e),
        "email_submits_by_campaign": ga4_modules_finished_by_campaign(s, e),
    }


def _tool_stripe_revenue(start=None, end=None, **_):
    s, e = _default_range(start, end)
    return {
        "totals": stripe_metrics(s, e),
        "by_category": stripe_revenue_by_category(s, e),
        "by_product": stripe_revenue_by_product(s, e),
    }


def _tool_stripe_sales_count(start=None, end=None, amounts_cents=None, exclude_subscriptions=False, **_):
    s, e = _default_range(start, end)
    amts = tuple(int(a) for a in (amounts_cents or [])) or (900,)
    return stripe_charges_daily_by_amounts(s, e, amts, bool(exclude_subscriptions))


def _tool_beehiiv(start=None, end=None, **_):
    s, e = _default_range(start, end)
    return beehiiv_metrics(s, e)


def _tool_gsc_keyword(keyword="personality test", **_):
    return gsc_keyword_position(keyword)


TOOL_FNS = {
    "weekly_history": _tool_weekly_history,
    "ga4_metrics": _tool_ga4_metrics,
    "ga4_by_channel": _tool_ga4_by_channel,
    "stripe_revenue": _tool_stripe_revenue,
    "stripe_sales_count": _tool_stripe_sales_count,
    "beehiiv_metrics": _tool_beehiiv,
    "gsc_keyword_position": _tool_gsc_keyword,
}

_DATE = {"type": "string", "description": "ISO date YYYY-MM-DD. Optional; defaults to last 7 days."}
TOOLS = [
    {
        "name": "weekly_history",
        "description": "The standard weekly KPI set (tools finished, revenue, PDF/cognitive sales, "
                       "newsletter subs/unsubs, funnel conversion rates) for the last N 7-day buckets, "
                       "most recent first. Use this for trends and week-over-week comparisons.",
        "input_schema": {"type": "object", "properties": {"num_weeks": {"type": "integer", "description": "How many weeks (default 4)."}}},
    },
    {
        "name": "ga4_metrics",
        "description": "GA4 for a date range: users, sessions, pageviews, and funnel event counts "
                       "(Viewed/Accepted Privacy Policy, Submitted Email).",
        "input_schema": {"type": "object", "properties": {"start": _DATE, "end": _DATE}},
    },
    {
        "name": "ga4_by_channel",
        "description": "GA4 'Submitted Email' (tools finished) broken down by traffic channel and by campaign.",
        "input_schema": {"type": "object", "properties": {"start": _DATE, "end": _DATE}},
    },
    {
        "name": "stripe_revenue",
        "description": "Stripe revenue for a range: totals (total/subscription/non-subscription), by category "
                       "(subscriptions/pdf/cognitive/other), and by product.",
        "input_schema": {"type": "object", "properties": {"start": _DATE, "end": _DATE}},
    },
    {
        "name": "stripe_sales_count",
        "description": "Count of successful Stripe charges matching specific amounts (in cents). "
                       "E.g. amounts_cents=[900] for the $9 PDF; [3500,1750] for the cognitive assessment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": _DATE, "end": _DATE,
                "amounts_cents": {"type": "array", "items": {"type": "integer"}, "description": "Charge amounts in cents."},
                "exclude_subscriptions": {"type": "boolean", "description": "Skip charges from subscription invoices."},
            },
        },
    },
    {
        "name": "beehiiv_metrics",
        "description": "beehiiv newsletter stats for a range: total/new subscribers, emails sent, open/click/"
                       "unsubscribe rates, unsubscribes, and per-campaign breakdown.",
        "input_schema": {"type": "object", "properties": {"start": _DATE, "end": _DATE}},
    },
    {
        "name": "gsc_keyword_position",
        "description": "Google Search Console average position, clicks and impressions for a single keyword.",
        "input_schema": {"type": "object", "properties": {"keyword": {"type": "string"}}},
    },
]


# --- Claude answer loop -----------------------------------------------------
def answer_question(question: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    today = date.today().isoformat()
    system = (
        "You are Igor's AI growth advisor for Clearer Thinking (clearerthinking.org). Igor replied "
        "to your weekly report with a question. Answer it precisely using the data tools when you "
        f"need specific numbers (today is {today}; the business sells a paid subscription, a $9 "
        "personality-test PDF, a $35/$17.50 cognitive assessment, and runs a beehiiv newsletter). "
        "Pull real data rather than guessing. Reply in PLAIN TEXT (no markdown/asterisks), concise "
        "and direct, like a sharp advisor answering by email. If a question is ambiguous, state your "
        "assumption and answer anyway. If you genuinely can't get the data, say so plainly."
    )
    messages = [{"role": "user", "content": question}]

    for _ in range(MAX_TOOL_TURNS):
        resp = client.messages.create(
            model=wa.ADVISOR_MODEL,
            max_tokens=2000,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                fn = TOOL_FNS.get(block.name)
                try:
                    out = fn(**(block.input or {})) if fn else {"error": f"unknown tool {block.name}"}
                    content = json.dumps(out, default=str)
                except Exception as e:  # noqa: BLE001
                    content = json.dumps({"error": f"{type(e).__name__}: {e}"})
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
            messages.append({"role": "user", "content": results})
            continue
        # final answer
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

    return ("I wasn't able to finish answering within the tool-call limit. Try narrowing the question "
            "(e.g. a specific metric and date range).")


# --- Gmail --------------------------------------------------------------------
def gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    from ga4_client import TOKEN_FILE

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract_plain(payload: dict) -> str:
    """Pull the text/plain body and drop the quoted original message."""
    def walk(p):
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "replace")
        for sub in p.get("parts", []) or []:
            t = walk(sub)
            if t:
                return t
        return ""

    text = walk(payload) or ""
    # Strip the quoted reply chain ("On <date>, <name> wrote:" and >-prefixed lines).
    lines = []
    for ln in text.splitlines():
        if re.match(r"^\s*On .*wrote:\s*$", ln) or ln.strip().startswith(">"):
            break
        lines.append(ln)
    return "\n".join(lines).strip() or text.strip()


def find_pending(svc) -> list[dict]:
    """Unread replies from the account owner in Weekly Growth Report threads (skip our own sends)."""
    q = f'is:unread in:inbox newer_than:14d subject:"{SUBJECT_MATCH}"'
    listing = svc.users().messages().list(userId="me", q=q, maxResults=20).execute()
    pending = []
    for ref in listing.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        if _header(headers, ADVISOR_HEADER):
            continue  # our own report/answer, not a question
        pending.append({
            "id": msg["id"],
            "threadId": msg["threadId"],
            "from": _header(headers, "From"),
            "subject": _header(headers, "Subject"),
            "message_id": _header(headers, "Message-ID"),
            "references": _header(headers, "References"),
            "question": _extract_plain(msg.get("payload", {})),
        })
    return pending


def send_reply(svc, item: dict, answer: str) -> None:
    msg = MIMEText(answer, "plain", "utf-8")
    msg["To"] = wa.EMAIL_FROM
    msg["From"] = f"CT Growth Advisor <{wa.EMAIL_FROM}>"
    subj = item["subject"]
    msg["Subject"] = subj if subj.lower().startswith("re:") else f"Re: {subj}"
    if item["message_id"]:
        msg["In-Reply-To"] = item["message_id"]
        msg["References"] = (item["references"] + " " + item["message_id"]).strip()
    msg[ADVISOR_HEADER] = "answer"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw, "threadId": item["threadId"]}).execute()


def mark_read(svc, msg_id: str) -> None:
    svc.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()


# --- main ---------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="answer + print, don't send or mark read")
    args = ap.parse_args()

    svc = gmail_service()
    pending = find_pending(svc)
    if not pending:
        print("[reply] no pending questions.", file=sys.stderr)
        return 0

    print(f"[reply] {len(pending)} question(s) to answer.", file=sys.stderr)
    for item in pending:
        q = item["question"]
        if not q:
            print(f"[reply] skipping {item['id']} (empty body).", file=sys.stderr)
            continue
        print(f"[reply] answering: {q[:120]!r}", file=sys.stderr)
        try:
            answer = answer_question(q)
        except Exception as e:  # noqa: BLE001
            print(f"[error] answering failed: {e}", file=sys.stderr)
            continue

        if args.dry_run:
            print(f"\n--- Q: {q}\n--- A:\n{answer}\n")
            continue
        try:
            send_reply(svc, item, answer)
            mark_read(svc, item["id"])
            print(f"[reply] sent answer for {item['id']}.", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"[error] sending reply failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
