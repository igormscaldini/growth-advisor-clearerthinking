"""Reply handler for the weekly growth-advisor email.

When Igor replies to a "Weekly Growth Report" email with a question, this:
  1. Finds unread replies in those threads (Gmail API).
  2. Hands the question to Claude with live data tools (GA4 / Stripe / beehiiv / GSC),
     so it can pull specific, on-demand data to answer, not just reuse the weekly numbers.
     The session is headless Claude Code on Igor's subscription (advisor_memory.run_claude_code,
     no Anthropic API credits): its only tool is Bash, allow-listed to
     `python advisor_reply.py --tool <name> '<json>'`, which runs one data tool and prints
     JSON. Claude also has a `remember_this` tool it calls if the exchange contains a durable
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
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

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
TOOL_SCRIPT = "advisor_reply.py"
DRY_RUN_ENV = "ADVISOR_REPLY_DRY_RUN"


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


# --dry-run must have no side effects (see module docstring). The tool runs in a child
# process of the headless session, so the flag also travels as the DRY_RUN_ENV variable.
DRY_RUN = False


def _tool_remember_this(entry=None, category="context", **_):
    """Append a durable memory entry. `entry` should be a short, first-person-from-the-advisor
    summary of the fact/preference/correction, written so it reads naturally when re-read as
    context in a future prompt.
    """
    if not entry or not str(entry).strip():
        return {"saved": False, "reason": "empty entry"}
    if DRY_RUN:
        print(f"[reply] (dry-run, not written) would remember: {entry!r} ({category})", file=sys.stderr)
        return {"saved": True, "dry_run": True}
    mem.append_durable_memory(str(entry), category)
    return {"saved": True}


def _durable_bytes() -> bytes:
    """Snapshot of the durable memory file, to detect writes made by the tool child process."""
    return mem.DURABLE_FILE.read_bytes() if mem.DURABLE_FILE.exists() else b""


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


# --- Claude answer (headless Claude Code with a Bash bridge to the tools above) ----------
def _python_cmd() -> str:
    """The interpreter the model invokes --tool mode with, from the repo root. The venv's
    `.venv/bin/python` is made relative (no spaces even though the repo path has them, so
    the Bash allow-list prefix matches what the model types); an interpreter elsewhere
    (GitHub Actions) is used by its absolute path; a path with spaces falls back to `python`."""
    exe = os.path.abspath(sys.executable)
    root = os.path.abspath(wa.ROOT)
    if exe.startswith(root + os.sep):
        return os.path.relpath(exe, root)
    return exe if " " not in exe else "python"


def tool_command_prefix() -> str:
    return f"{_python_cmd()} {TOOL_SCRIPT} --tool"


def tools_prompt() -> str:
    """The tool catalogue for the system prompt: each data tool is one shell command that prints JSON."""
    lines = [
        "Data tools. Each one is a shell command, run from the repository root with the Bash tool, "
        "that prints a JSON result. Call it exactly as:",
        f"  {tool_command_prefix()} <tool_name> '<JSON object of arguments>'",
        "(single-quote the JSON; pass '{}' when there are no arguments). Never run any other command. "
        "Tools:",
    ]
    for t in TOOLS:
        props = (t.get("input_schema") or {}).get("properties") or {}
        args = "; ".join(f"{k}: {v.get('type', 'string')}, {v.get('description', '')}".rstrip(", ")
                         for k, v in props.items()) or "none"
        lines.append(f"- {t['name']}: {t['description']} Arguments: {args}")
    return "\n".join(lines)


def run_tool(name: str, args_json: str) -> dict:
    """--tool mode: run one data tool and return its result. Problems come back as
    {"error": ...} so the model can read them instead of a stack trace."""
    fn = TOOL_FNS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name!r}; available: {', '.join(TOOL_FNS)}"}
    try:
        args = json.loads(args_json or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"JSONDecodeError in arguments: {e}"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object"}
    try:
        return fn(**args)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def answer_question(question: str) -> str:
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
        "and direct, like a sharp advisor answering by email; your final message is sent to Igor "
        "verbatim, so it must contain only the answer. If a question is ambiguous, state your "
        "assumption and answer anyway. If you genuinely can't get the data, say so plainly.\n\n"
        f"{tools_prompt()}\n\n"
        f"Durable memory of things Igor has told you before:\n{memory_text or '(nothing recorded yet)'}\n\n"
        f"Knowledge base (audience and communication):\n{knowledge_text or '(none)'}\n\n"
        f"Digests of Igor's Claude Code working sessions in the last two weeks (what he has been "
        f"working on; use them to answer questions about his own projects):\n"
        f"{conversations_text or '(none)'}\n\n"
        "Never use em dashes. If THIS reply contains a new durable preference, correction, or standing context worth "
        "carrying into future reports, run the remember_this tool to save it (in addition to answering)."
    )
    # No retries here: an unread question is picked up again by the next cron tick, and a retry
    # after a partial run could save the same memory entry twice.
    return mem.run_claude_code(system, question, cwd=wa.ROOT, tools=["Bash"],
                               allowed_tools=[f"Bash({tool_command_prefix()}:*)"])


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
    ap.add_argument("--tool", metavar="NAME",
                    help="run one data tool and print its JSON result (how the headless Claude session "
                         "calls the tools); TOOL_ARGS is a JSON object of arguments")
    ap.add_argument("tool_args", nargs="?", default="{}", metavar="TOOL_ARGS")
    args = ap.parse_args()

    if args.tool:
        DRY_RUN = os.getenv(DRY_RUN_ENV) == "1"
        print(json.dumps(run_tool(args.tool, args.tool_args), default=str))
        return 0

    DRY_RUN = args.dry_run
    if DRY_RUN:
        os.environ[DRY_RUN_ENV] = "1"   # inherited by the tool child processes

    svc = gmail_service()
    pending = find_pending(svc)
    if not pending:
        print("[reply] no pending questions.", file=sys.stderr)
        return 0

    print(f"[reply] {len(pending)} question(s) to answer.", file=sys.stderr)
    memory_before = _durable_bytes()
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

    if not args.dry_run and _durable_bytes() != memory_before:
        _commit_memory_file()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
