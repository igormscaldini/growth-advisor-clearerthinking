"""Send the "UQP researcher outreach" Gmail drafts in daily batches (Unanswered Questions in
Psychology Prize, Nov 2026).

Igor's plan (2026-11-12): 10 drafts per weekday from Fri 2026-11-13, at 9:30am US Eastern,
skipping US Thanksgiving (Nov 26-27), so the 100 drafts go out over 10 sending days ending
Mon 2026-11-30. Drafts are sent oldest-first; they were created in rank order (podcast guests
first), so creation time IS the rank.

Run by `.github/workflows/uqp-outreach-send.yml` several times each weekday afternoon because
GitHub throttles `schedule` events on this repo: every run counts what the label already sent
today and tops up to the daily batch, so extra runs are harmless and a late run still sends.
A day whose runs all land outside the window sends nothing; the remaining drafts simply roll
on to the next sending day.

The repo and its Actions logs are PUBLIC: never print recipient addresses or names here.

Local dry run:  python uqp_draft_sender.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LABEL_NAME = "UQP researcher outreach"
FROM_ALIAS = "igor@clearerthinking.org"
DAILY_BATCH = 10
START = date(2026, 11, 13)
SKIP_DAYS = {date(2026, 11, 26), date(2026, 11, 27)}  # US Thanksgiving + the Friday after
ET = ZoneInfo("America/New_York")
WINDOW_START = time(9, 30)
WINDOW_END = time(17, 0)


def is_send_day(d: date) -> bool:
    """Weekday on or after START and not a skipped holiday. Pure, tested."""
    return d >= START and d.weekday() < 5 and d not in SKIP_DAYS


def in_window(now_et: datetime) -> bool:
    """True between 9:30am and 5:00pm US Eastern. Pure, tested."""
    return WINDOW_START <= now_et.time() < WINDOW_END


def batch_size(sent_today: int, remaining: int, daily: int = DAILY_BATCH) -> int:
    """How many drafts this run should send. Pure, tested."""
    return max(0, min(daily - sent_today, remaining))


def pick_batch(drafts: list[dict], n: int) -> list[dict]:
    """Oldest `n` drafts by creation time (= rank order). Pure, tested.

    Each draft dict needs `internalDate` (ms since epoch, as Gmail returns it, a string)."""
    return sorted(drafts, key=lambda d: int(d["internalDate"]))[:n]


def et_midnight_epoch(now_et: datetime) -> int:
    """Unix seconds of today's midnight US Eastern, for Gmail's `after:` query. Pure, tested."""
    midnight = datetime.combine(now_et.date(), time(0, 0), tzinfo=ET)
    return int(midnight.timestamp())


def gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    from ga4_client import TOKEN_FILE

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def label_id(svc) -> str:
    for lab in svc.users().labels().list(userId="me").execute()["labels"]:
        if lab["name"] == LABEL_NAME:
            return lab["id"]
    raise SystemExit(f"Gmail label {LABEL_NAME!r} not found")


def count_sent_today(svc, now_et: datetime) -> int:
    q = f'label:"{LABEL_NAME}" in:sent after:{et_midnight_epoch(now_et)}'
    total, page = 0, None
    while True:
        res = svc.users().messages().list(userId="me", q=q, maxResults=500, pageToken=page).execute()
        total += len(res.get("messages", []))
        page = res.get("nextPageToken")
        if not page:
            return total


def pending_drafts(svc, lab: str) -> list[dict]:
    """Every draft carrying the label, with internalDate and From for ordering and a safety check."""
    out, page = [], None
    while True:
        res = svc.users().drafts().list(userId="me", maxResults=500, pageToken=page).execute()
        for d in res.get("drafts", []):
            # drafts.get takes no metadataHeaders; messages.get on the draft's message does.
            m = svc.users().messages().get(userId="me", id=d["message"]["id"], format="metadata",
                                           metadataHeaders=["From"]).execute()
            if lab not in m.get("labelIds", []):
                continue
            frm = next((h["value"] for h in m["payload"].get("headers", []) if h["name"] == "From"), "")
            out.append({"id": d["id"], "internalDate": m["internalDate"], "from": frm})
        page = res.get("nextPageToken")
        if not page:
            return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report what would be sent, send nothing")
    ap.add_argument("--ignore-window", action="store_true", help="send outside 9:30am-5pm ET (manual catch-up)")
    args = ap.parse_args()

    now_et = datetime.now(ET)
    print(f"now (ET): {now_et:%Y-%m-%d %H:%M}")
    if not is_send_day(now_et.date()) and not args.dry_run:
        print("not a sending day; nothing to do")
        return 0
    if not in_window(now_et) and not args.ignore_window:
        print("outside the 9:30am-5pm ET window; nothing to do")
        return 0

    from secrets_loader import materialize_ci_secrets
    materialize_ci_secrets()
    svc = gmail_service()
    lab = label_id(svc)
    drafts = pending_drafts(svc, lab)
    sent_today = count_sent_today(svc, now_et)
    n = batch_size(sent_today, len(drafts))
    print(f"drafts left: {len(drafts)}, sent today: {sent_today}, to send now: {n}")

    failures = 0
    for d in pick_batch(drafts, n):
        if FROM_ALIAS not in d["from"]:
            print(f"skip draft {d['id']}: From is not {FROM_ALIAS}")
            failures += 1
            continue
        if args.dry_run:
            print(f"would send draft {d['id']}")
            continue
        try:
            sent = svc.users().drafts().send(userId="me", body={"id": d["id"]}).execute()
            # Keep the label on the sent copy: count_sent_today relies on it.
            svc.users().messages().modify(userId="me", id=sent["id"],
                                          body={"addLabelIds": [lab]}).execute()
            print(f"sent draft {d['id']}")
        except Exception as e:  # noqa: BLE001 - report and carry on with the rest of the batch
            print(f"FAILED draft {d['id']}: {type(e).__name__}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
