"""Weekly scan of Igor's Gmail for the advisor letter (and the reply handler's inbox tool).

Pulls the last N days of mail through the Gmail API (the shared Google token already carries
gmail.modify, which includes read access), drops newsletters and automated senders, and
returns a compact text digest of the threads Igor actually wrote in or was addressed in. The
letter uses it to spot promising projects, unanswered requests and commitments he may be
missing. Nothing from the inbox is stored; it only travels into the Claude prompt.

Run locally:   .venv/bin/python advisor_inbox.py            # print this week's digest
"""
from __future__ import annotations

import base64
import re
import sys
from datetime import datetime, timezone

import email_transport

OWN_ADDRESS = email_transport.EMAIL_FROM.lower()
ADVISOR_HEADER = "X-CT-Advisor"
DEFAULT_DAYS = 7
DEFAULT_MAX_MESSAGES = 80   # messages whose full body is fetched and shown
LIST_MAX = 400              # messages scanned (metadata only) per run
BODY_CHARS = 600
META_HEADERS = ["From", "To", "Cc", "Subject", "Date", "List-Unsubscribe", "List-Id",
                "Precedence", "Auto-Submitted", ADVISOR_HEADER]
AUTOMATED_SENDER_RE = re.compile(r"(no-?reply|do-?not-?reply|notifications?@|mailer-daemon|bounce)", re.I)


# --- Gmail ----------------------------------------------------------------------
def gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    from ga4_client import TOKEN_FILE

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def header_map(headers: list[dict]) -> dict:
    return {h.get("name", "").lower(): h.get("value", "") for h in headers or []}


def extract_plain(payload: dict) -> str:
    """The text/plain body of a message with the quoted reply chain removed."""
    def walk(p):
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "replace")
        for sub in p.get("parts", []) or []:
            t = walk(sub)
            if t:
                return t
        return ""

    text = walk(payload or {}) or ""
    lines = []
    for ln in text.splitlines():
        if re.match(r"^\s*On .*wrote:\s*$", ln) or ln.strip().startswith(">"):
            break
        lines.append(ln)
    return "\n".join(lines).strip() or text.strip()


# --- classification (pure, unit-tested) ------------------------------------------
def is_bulk(h: dict) -> bool:
    """Newsletters, list mail and automated senders: not a conversation Igor is in."""
    if h.get("list-unsubscribe") or h.get("list-id"):
        return True
    if h.get("precedence", "").lower() in ("bulk", "list", "junk"):
        return True
    if h.get("auto-submitted", "").lower() not in ("", "no"):
        return True
    return bool(AUTOMATED_SENDER_RE.search(h.get("from", "")))


def direction(h: dict, labels: list[str]) -> str:
    if "SENT" in (labels or []) or OWN_ADDRESS in h.get("from", "").lower():
        return "sent"
    return "received"


def select_messages(metas: list[dict], max_messages: int = DEFAULT_MAX_MESSAGES) -> list[dict]:
    """Drop bulk + advisor mail; keep what Igor sent first, then newest received, capped."""
    keep = [m for m in metas if not m["bulk"] and not m["advisor"]]
    keep.sort(key=lambda m: (m["direction"] != "sent", -m["ts"]))
    return keep[:max_messages]


def _clean(s: str, n: int) -> str:
    return " ".join((s or "").split())[:n]


def render_threads(messages: list[dict]) -> str:
    """Group by thread (newest thread first), one compact line per message."""
    threads: dict[str, list[dict]] = {}
    for m in messages:
        threads.setdefault(m["thread"], []).append(m)
    ordered = sorted(threads.values(), key=lambda ms: -max(m["ts"] for m in ms))
    out = []
    for ms in ordered:
        ms.sort(key=lambda m: m["ts"])
        subject = _clean(ms[0].get("subject") or "(no subject)", 120)
        out.append(f"### {subject} ({len(ms)} message{'s' if len(ms) != 1 else ''})")
        for m in ms:
            day = datetime.fromtimestamp(m["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
            who = f"Igor -> {_clean(m.get('to'), 80)}" if m["direction"] == "sent" else f"{_clean(m.get('from'), 80)} -> Igor"
            body = _clean(m.get("body") or m.get("snippet") or "", BODY_CHARS)
            out.append(f"- {day} | {who}\n  {body}")
        out.append("")
    return "\n".join(out).strip()


# --- fetching -----------------------------------------------------------------------
def fetch_week(svc, days: int = DEFAULT_DAYS, max_messages: int = DEFAULT_MAX_MESSAGES) -> dict:
    q = f"newer_than:{days}d -category:promotions -category:social"
    ids: list[str] = []
    token = None
    while len(ids) < LIST_MAX:
        resp = svc.users().messages().list(userId="me", q=q, maxResults=100, pageToken=token).execute()
        ids.extend(m["id"] for m in resp.get("messages", []))
        token = resp.get("nextPageToken")
        if not token:
            break

    metas = []
    for mid in ids[:LIST_MAX]:
        msg = svc.users().messages().get(userId="me", id=mid, format="metadata", metadataHeaders=META_HEADERS).execute()
        h = header_map(msg.get("payload", {}).get("headers", []))
        labels = msg.get("labelIds", []) or []
        metas.append({
            "id": mid,
            "thread": msg.get("threadId", mid),
            "ts": int(msg.get("internalDate", "0")) // 1000,
            "from": h.get("from", ""),
            "to": h.get("to", ""),
            "subject": h.get("subject", ""),
            "snippet": msg.get("snippet", ""),
            "bulk": is_bulk(h),
            "advisor": bool(h.get(ADVISOR_HEADER.lower())),
            "direction": direction(h, labels),
        })

    selected = select_messages(metas, max_messages)
    for m in selected:
        try:
            full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
            m["body"] = extract_plain(full.get("payload", {}))
        except Exception as e:  # noqa: BLE001
            print(f"[inbox] body fetch failed for {m['id']}: {e}", file=sys.stderr)
            m["body"] = ""

    return {
        "days": days,
        "scanned": len(metas),
        "included": len(selected),
        "sent": sum(1 for m in selected if m["direction"] == "sent"),
        "received": sum(1 for m in selected if m["direction"] == "received"),
        "text": render_threads(selected),
    }


def weekly_inbox_digest(days: int = DEFAULT_DAYS, max_messages: int = DEFAULT_MAX_MESSAGES) -> dict:
    return fetch_week(gmail_service(), days, max_messages)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    d = weekly_inbox_digest()
    print(f"scanned {d['scanned']}, included {d['included']} ({d['sent']} sent, {d['received']} received)\n", file=sys.stderr)
    print(d["text"])
