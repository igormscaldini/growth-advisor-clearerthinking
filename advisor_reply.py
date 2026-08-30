"""Reply handler for the weekly growth-advisor email.

When Igor replies to a "Weekly Growth Report" email with a question, this:
  1. Finds unread replies in those threads (Gmail API).
  2. Hands the question to Claude with live data tools (GA4 / Stripe / beehiiv / GSC),
     so it can pull specific, on-demand data to answer — not just reuse the weekly numbers.
     Claude also has a `remember_this` tool it calls if the exchange contains a durable
     preference, correction, or standing context worth carrying into future reports.
  3. Replies in the same thread with the answer (Gmail API).
  4. Marks the message read so it's never answered twice.
  5. If any memory was saved, commits advisor_memory/durable.md.enc back to the repo so it
     persists across runs (this workflow is otherwise stateless on GitHub Actions). Memory
     is encrypted at rest because the repo is public (see advisor_memory.py).

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
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText

# weekly_advisor runs load_dotenv + secret materialization at import time, and exposes
# the config + data helpers we reuse here.
import advisor_inbox
import advisor_memory as mem
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


def _tool_inbox(days=7, **_):
    return advisor_inbox.weekly_inbox_digest(int(days))


# Entries saved this run, so main() knows whether ADVISOR_MEMORY.md needs to be committed.
_memory_written_this_run: list[str] = []
# --dry-run should have no side effects (see module docstring), so gate the actual file write.
DRY_RUN = False


def _tool_remember_this(entry=None, category="context", **_):
    """Append a durable memory entry. `entry` should be a short, first-person-from-the-advisor
    summary of the fact/preference/correction — written so it reads naturally when re-read as
    context in a future prompt.
    """
    if not entry or not str(entry).strip():
        return {"saved": False, "reason": "empty entry"}
    if DRY_RUN:
        print(f"[reply] (dry-run, not written) would remember: {entry!r} ({category})", file=sys.stderr)
        return {"saved": True, "dry_run": True}
    line = mem.append_durable_memory(str(entry), category)
    _memory_written_this_run.append(line)
    return {"saved": True}


def _commit_memory_file() -> None:
    """Push the durable memory back to the repo so it survives across ephemeral CI runs."""
    err = mem.git_commit_and_push([mem.DURABLE_FILE], "advisor memory: remember new context from Igor's reply")
    if err:
        print(f"[warn] could not commit durable memory: {err}", file=sys.stderr)
    else:
        print("[reply] committed durable memory.", file=sys.stderr)


TOOL_FNS = {
    "weekly_history": _tool_weekly_history,
    "ga4_metrics": _tool_ga4_metrics,
    "ga4_by_channel": _tool_ga4_by_channel,
    "stripe_revenue": _tool_stripe_revenue,
    "stripe_sales_count": _tool_stripe_sales_count,
    "beehiiv_metrics": _tool_beehiiv,
    "gsc_keyword_position": _tool_gsc_keyword,
    "inbox_recent": _tool_inbox,
    "remember_this": _tool_remember_this,
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
    {
        "name": "inbox_recent",
        "description": "Igor's recent Gmail threads (what he sent and what people wrote to him; "
                       "newsletters and automated mail removed), grouped by thread. Use it when a "
                       "question is about his projects, partners, requests or commitments.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "description": "Look-back window in days (default 7)."}}},
    },
    {
        "name": "remember_this",
        "description": "Save a durable fact, preference, or correction from Igor for future weekly "
                       "reports and Q&A — e.g. he says he doesn't want a certain metric flagged, "
                       "explains a seasonal pattern, corrects a wrong assumption you made, or gives "
                       "standing context about the business. Call this whenever the reply contains "
                       "something worth carrying forward, in ADDITION to answering the question — do "
                       "not call it for simple one-off factual questions with no lasting takeaway.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry": {"type": "string", "description": "One short, self-contained sentence or two "
                                                             "capturing the durable takeaway, written so "
                                                             "it's clear on its own when re-read weeks later."},
                "category": {"type": "string", "enum": ["preference", "correction", "context"],
                             "description": "preference = how he wants things weighted/flagged; "
                                             "correction = you got something wrong and he fixed it; "
                                             "context = a standing fact about the business."},
            },
            "required": ["entry"],
        },
    },
]


# --- Claude answer loop -----------------------------------------------------
def answer_question(question: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    today = date.today().isoformat()
    memory_text = wa.load_memory()
    try:
        knowledge_text = mem.load_knowledge(max_chars=30_000)
        conversations_text = mem.load_recent_conversations(days=14, max_chars=40_000)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] memory unavailable: {e}", file=sys.stderr)
        knowledge_text = conversations_text = ""
    system = (
        "You are Igor's AI growth advisor for Clearer Thinking (clearerthinking.org). Igor replied "
        "to your weekly report with a question. Answer it precisely using the data tools when you "
        f"need specific numbers (today is {today}; the business sells a paid subscription, a $9 "
        "personality-test PDF, a $35/$17.50 cognitive assessment, and runs a beehiiv newsletter). "
        "Pull real data rather than guessing. Reply in PLAIN TEXT (no markdown/asterisks), concise "
        "and direct, like a sharp advisor answering by email. If a question is ambiguous, state your "
        "assumption and answer anyway. If you genuinely can't get the data, say so plainly.\n\n"
        f"Durable memory of things Igor has told you before:\n{memory_text or '(nothing recorded yet)'}\n\n"
        f"Knowledge base (audience and communication):\n{knowledge_text or '(none)'}\n\n"
        f"Digests of Igor's Claude Code working sessions in the last two weeks (what he has been "
        f"working on; use them to answer questions about his own projects):\n"
        f"{conversations_text or '(none)'}\n\n"
        "Never use em dashes. If THIS reply contains a new durable preference, correction, or standing context worth "
        "carrying into future reports, call remember_this to save it (in addition to answering)."
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
    return advisor_inbox.gmail_service()


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract_plain(payload: dict) -> str:
    return advisor_inbox.extract_plain(payload)


def find_pending(svc) -> list[dict]:
    """Unread replies from the account owner in Weekly Growth Report threads (skip our own sends).

    Note: the advisor sends from Igor's own address to himself, so his replies land under
    SENT (no INBOX label). We therefore do NOT filter `in:inbox` — the X-CT-Advisor header
    is what distinguishes our own outgoing mail from a genuine question.
    """
    q = f'is:unread newer_than:14d subject:"{SUBJECT_MATCH}"'
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
    global DRY_RUN
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="answer + print, don't send or mark read")
    args = ap.parse_args()
    DRY_RUN = args.dry_run

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

    if _memory_written_this_run and not args.dry_run:
        _commit_memory_file()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
