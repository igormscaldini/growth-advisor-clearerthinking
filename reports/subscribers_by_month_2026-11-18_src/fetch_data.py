"""Walk every beehiiv subscription created since FLOOR and save a slim, email-free copy.

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/fetch_data.py

Writes data/subscriptions.jsonl (gitignored) next to this file: one JSON object per subscription with the
fields `analysis.py` classifies on. The list endpoint has no created-date filter and offset paging caps at
10k, so this cursor-pages `created desc` and stops at the first page that is entirely older than FLOOR
(about 370k records and an hour for all of 2026). The walk resumes from data/checkpoint.json if interrupted;
delete data/ to start over.
"""
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import data_layer as dl  # noqa: E402

FLOOR = date(2026, 1, 1)
DATA = HERE / "data"
OUT = DATA / "subscriptions.jsonl"
CHECKPOINT = DATA / "checkpoint.json"

NATIVE_FIELDS = ("id", "status", "created", "utm_source", "utm_medium", "utm_channel", "utm_campaign",
                 "referring_site", "subscription_tier")
# Custom fields that can hold a person's name, address or free text are never written to disk.
PII_HINTS = ("name", "email", "phone", "address")


def slim(sub: dict) -> dict:
    """The fields the analysis needs, without the email or any personal custom field."""
    row = {k: sub.get(k) for k in NATIVE_FIELDS}
    row["cf"] = {
        cf["name"]: cf["value"]
        for cf in sub.get("custom_fields") or []
        if cf.get("value") not in (None, "", False)
        and not any(h in (cf.get("name") or "").lower() for h in PII_HINTS)
    }
    return row


def main():
    api_key = os.environ["BEEHIIV_API_KEY"].strip()
    pub_id = os.environ["BEEHIIV_PUB_CLEARER_THINKING"].strip()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{dl.BEEHIIV_BASE}/publications/{pub_id}/subscriptions"
    floor_ts = int(datetime(FLOOR.year, FLOOR.month, FLOOR.day, tzinfo=timezone.utc).timestamp())

    DATA.mkdir(exist_ok=True)
    state = {"cursor": "", "pages": 0, "rows": 0, "done": False}
    if CHECKPOINT.exists() and OUT.exists():
        state = json.loads(CHECKPOINT.read_text())
        if state["done"]:
            print(f"already complete: {state['rows']} rows in {OUT}")
            return
        # Drop anything written after the last checkpoint so a resume never duplicates rows.
        with OUT.open("rb+") as f:
            f.truncate(state["bytes"])
        print(f"resuming at page {state['pages']} ({state['rows']} rows)")
    else:
        OUT.write_text("")

    with OUT.open("a") as out:
        while True:
            r = dl._beehiiv_get_page(url, headers=headers, timeout=(10, 90), params={
                "limit": 100, "order_by": "created", "direction": "desc",
                "expand[]": "custom_fields", "cursor": state["cursor"]})
            r.raise_for_status()
            body = r.json()
            subs = body.get("data") or []
            kept = [s for s in subs if (dl._sub_created_ts(s) or 0) >= floor_ts]
            for s in kept:
                out.write(json.dumps(slim(s), separators=(",", ":")) + "\n")
            state["pages"] += 1
            state["rows"] += len(kept)
            state["cursor"] = body.get("next_cursor") or ""
            finished = not subs or not kept or not body.get("has_more") or not state["cursor"]
            if finished or state["pages"] % 25 == 0:
                out.flush()
                os.fsync(out.fileno())
                state["bytes"] = out.tell()
                state["done"] = finished
                CHECKPOINT.write_text(json.dumps(state))
                oldest = datetime.fromtimestamp(dl._sub_created_ts(subs[-1]), tz=timezone.utc) if subs else None
                print(f"page {state['pages']}: {state['rows']} rows, oldest {oldest:%Y-%m-%d %H:%M}" if oldest
                      else f"page {state['pages']}: empty", flush=True)
            if finished:
                break
    print(f"done: {state['rows']} rows -> {OUT}")


if __name__ == "__main__":
    main()
