"""Re-walk every beehiiv subscription created in 2026, with each subscriber's engagement stats.

    .venv/bin/python reports/net_growth_diagnosis_2026-11-27_src/fetch_subscriptions.py

Writes data/subscriptions_now.jsonl (gitignored, no emails) next to this file. It is the second
snapshot of the same people as reports/subscribers_by_month_2026-11-18_src/data/subscriptions.jsonl
(walked Nov 18, 2026), so the two can be diffed to see exactly who left in between.

beehiiv list cursors are unpadded urlsafe base64 of {"value": "<ISO time>", "type": "time"}, so a
`created desc` walk can start at any timestamp. The year is cut into segments of about equal size
(using the Nov 18 snapshot's timestamps) and ten threads walk them behind ONE shared throttle
(about 2.2 requests a second, the rate verified on 2026-11-27). Each finished segment is saved, so
an interrupted run resumes where it stopped. Delete data/parts/ to start over.
"""
import base64
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import data_layer as dl  # noqa: E402

OLD = ROOT / "reports" / "subscribers_by_month_2026-11-18_src" / "data" / "subscriptions.jsonl"
DATA = HERE / "data"
PARTS = DATA / "parts"
OUT = DATA / "subscriptions_now.jsonl"
META = DATA / "walk_meta.json"

FLOOR_TS = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
SEGMENT_ROWS = 2500
THREADS = 10
THROTTLE_SECONDS = 0.45

NATIVE_FIELDS = ("id", "status", "created", "utm_source", "utm_medium", "utm_channel", "utm_campaign",
                 "referring_site", "subscription_tier")
STAT_FIELDS = ("total_sent", "total_received", "total_unique_opened", "total_unique_clicked")
# Custom fields that can hold a person's name, address or free text are never written to disk.
PII_HINTS = ("name", "email", "phone", "address")

_throttle_lock = threading.Lock()
_next_slot = [0.0]


def wait_for_slot():
    """One shared queue for every thread: requests leave THROTTLE_SECONDS apart."""
    with _throttle_lock:
        now = time.monotonic()
        slot = max(now, _next_slot[0])
        _next_slot[0] = slot + THROTTLE_SECONDS
    delay = slot - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def forge_cursor(ts: int) -> str:
    """The cursor beehiiv would hand out for `ts` (records created before it come next)."""
    iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    raw = json.dumps({"value": iso, "type": "time"}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def slim(sub: dict) -> dict:
    """The fields the analysis needs, without the email or any personal custom field."""
    row = {k: sub.get(k) for k in NATIVE_FIELDS}
    row["created"] = dl._sub_created_ts(sub)
    stats = sub.get("stats") or {}
    row["st"] = [stats.get(k) or 0 for k in STAT_FIELDS]
    row["cf"] = {
        cf["name"]: cf["value"]
        for cf in sub.get("custom_fields") or []
        if cf.get("value") not in (None, "", False)
        and not any(h in (cf.get("name") or "").lower() for h in PII_HINTS)
    }
    return row


def segments(now_ts: int) -> list:
    """(lower, upper) second bounds, inclusive on both ends, about SEGMENT_ROWS records each."""
    stamps = []
    if OLD.exists():
        with OLD.open() as f:
            for line in f:
                stamps.append(json.loads(line)["created"])
        stamps.sort()
    cuts = [FLOOR_TS] + [stamps[i] for i in range(SEGMENT_ROWS, len(stamps), SEGMENT_ROWS)]
    last_known = stamps[-1] if stamps else FLOOR_TS
    day = 86400
    t = last_known
    while t < now_ts:  # the days since the old snapshot, one segment each
        cuts.append(t)
        t += day
    cuts.append(now_ts)
    cuts = sorted(set(cuts))
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]


def walk_segment(index: int, lower: int, upper: int, url: str, headers: dict) -> int:
    part = PARTS / f"seg_{index:04d}.jsonl"
    if part.exists():
        return sum(1 for _ in part.open())
    rows, cursor = [], forge_cursor(upper + 1)
    while True:
        wait_for_slot()
        r = dl._beehiiv_get_page(url, headers=headers, timeout=(10, 90), params=[
            ("limit", 100), ("order_by", "created"), ("direction", "desc"),
            ("expand[]", "custom_fields"), ("expand[]", "stats"), ("cursor", cursor)])
        r.raise_for_status()
        body = r.json()
        subs = body.get("data") or []
        oldest = None
        for s in subs:
            ts = dl._sub_created_ts(s) or 0
            oldest = ts if oldest is None else min(oldest, ts)
            if lower <= ts <= upper:
                rows.append(slim(s))
        cursor = body.get("next_cursor") or ""
        if not subs or not body.get("has_more") or not cursor or oldest < lower:
            break
    tmp = part.with_suffix(".tmp")
    with tmp.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    tmp.rename(part)
    return len(rows)


def main():
    api_key = os.environ["BEEHIIV_API_KEY"].strip()
    pub_id = os.environ["BEEHIIV_PUB_CLEARER_THINKING"].strip()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{dl.BEEHIIV_BASE}/publications/{pub_id}/subscriptions"

    PARTS.mkdir(parents=True, exist_ok=True)
    if META.exists():
        meta = json.loads(META.read_text())
    else:
        meta = {"as_of_ts": int(time.time())}
        meta["segments"] = segments(meta["as_of_ts"])
        META.write_text(json.dumps(meta))
    segs = [tuple(s) for s in meta["segments"]]
    print(f"{len(segs)} segments, as of {datetime.fromtimestamp(meta['as_of_ts'], tz=timezone.utc):%Y-%m-%d %H:%M} UTC",
          flush=True)

    done = [0]
    started = time.time()

    def run(job):
        index, (lower, upper) = job
        n = walk_segment(index, lower, upper, url, headers)
        done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(segs):
            print(f"{done[0]}/{len(segs)} segments, {time.time() - started:.0f}s", flush=True)
        return n

    with ThreadPoolExecutor(THREADS) as pool:
        counts = list(pool.map(run, enumerate(segs)))

    seen, kept = set(), 0
    with OUT.open("w") as out:
        for index in range(len(segs)):
            with (PARTS / f"seg_{index:04d}.jsonl").open() as f:
                for line in f:
                    sub_id = json.loads(line)["id"]
                    if sub_id in seen:
                        continue
                    seen.add(sub_id)
                    out.write(line)
                    kept += 1
    meta.update({"rows_with_edge_duplicates": sum(counts), "rows": kept, "done": True})
    META.write_text(json.dumps(meta))
    print(f"done: {kept} unique rows ({sum(counts) - kept} edge duplicates dropped) -> {OUT}")


if __name__ == "__main__":
    main()
