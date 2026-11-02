"""Refresh the newsletter block of datapoints.json from beehiiv: every confirmed send since --since,
grouped into editions (pricing.group_editions), filtered to the regular editions a sponsor box runs in,
summarised, plus the publication's active subscriber count.

    .venv/bin/python reports/sponsorship_price_sheet_2026-11-02_src/fetch_newsletter_stats.py [--since 2026-07-01]

Rerun before sending the sheet to a new sponsor, then build.py. Sends younger than 5 days are left out
because their opens are still accruing.

Gotcha found 2026-11-02: with order_by=publish_date&direction=desc, adding platform=email made the API drop every
post published after Oct 6, so this script filters on status only and ignores posts with no email stats.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
logging.disable(logging.WARNING)

import data_layer as dl  # noqa: E402
import pricing  # noqa: E402

DATAPOINTS = HERE / "datapoints.json"


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ['BEEHIIV_API_KEY'].strip()}", "Accept": "application/json"}


def fetch_posts(since: date) -> list[dict]:
    """Confirmed posts with email stats published on or after `since`, newest first from the API."""
    pub = os.environ["BEEHIIV_PUB_CLEARER_THINKING"].strip()
    posts: list[dict] = []
    page = 1
    floor = datetime(since.year, since.month, since.day, tzinfo=timezone.utc).timestamp()
    while True:
        r = dl._beehiiv_get(f"{dl.BEEHIIV_BASE}/publications/{pub}/posts", headers=_headers(),
                            params={"page": page, "limit": 100, "expand[]": "stats", "status": "confirmed",
                                    "order_by": "publish_date", "direction": "desc"})
        r.raise_for_status()
        data = r.json()
        batch = data.get("data", [])
        posts.extend(batch)
        oldest = min([p.get("publish_date") or 10**12 for p in batch] or [0])
        if page >= data.get("total_pages", 1) or oldest < floor:
            break
        page += 1
    out = []
    for p in posts:
        em = (p.get("stats") or {}).get("email") or {}
        ts = p.get("publish_date")
        if not ts or not em:
            continue
        d = datetime.fromtimestamp(ts, tz=timezone.utc)
        if d.timestamp() < floor:
            continue
        out.append({"date": d.strftime("%Y-%m-%d"), "subject": p.get("subject_line") or p.get("title") or "",
                    "recipients": em.get("recipients") or 0, "unique_opens": em.get("unique_opens") or 0,
                    "id": p.get("id")})
    return out


def active_subscriptions() -> int:
    pub = os.environ["BEEHIIV_PUB_CLEARER_THINKING"].strip()
    r = dl._beehiiv_get(f"{dl.BEEHIIV_BASE}/publications/{pub}", headers=_headers(), params={"expand[]": "stats"})
    r.raise_for_status()
    return int((r.json().get("data", {}).get("stats") or {}).get("active_subscriptions") or 0)


def newsletter_block(posts: list[dict], since: date, until: date, subs: int) -> dict:
    editions = pricing.group_editions(posts)
    regular = pricing.regular_editions(editions, until=until.isoformat())
    return {
        "source": ("beehiiv API, confirmed posts; same-day sends grouped into one edition; regular editions = "
                   "recipients >= 200,000, open rate >= 15%, not a tool, workshop or coaching promo"),
        "fetched": date.today().isoformat(),
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "active_subscriptions": subs,
        "stats": pricing.summarize(e["unique_opens"] for e in regular),
        "editions_per_week": pricing.editions_per_week(regular),
        "by_month": pricing.by_month(regular),
        "editions": [{k: e[k] for k in ("date", "weekday", "posts", "recipients", "unique_opens", "subject")}
                     for e in regular],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-07-01")
    ap.add_argument("--fresh-days", type=int, default=5, help="ignore sends younger than this many days")
    a = ap.parse_args()
    since = date.fromisoformat(a.since)
    until = date.today() - timedelta(days=a.fresh_days)
    posts = fetch_posts(since)
    block = newsletter_block(posts, since, until, active_subscriptions())
    dp = json.loads(DATAPOINTS.read_text()) if DATAPOINTS.exists() else {}
    dp["newsletter"] = block
    DATAPOINTS.write_text(json.dumps(dp, indent=1, ensure_ascii=False) + "\n")
    s = block["stats"]
    print(f"{len(posts)} sends since {since} -> {s['n']} regular editions to {until}; "
          f"median {s['median']:,} unique opens (p25 {s['p25']:,}, p75 {s['p75']:,}, min {s['min']:,}, max {s['max']:,}); "
          f"{block['editions_per_week']} editions/week; {block['active_subscriptions']:,} active subscribers")


if __name__ == "__main__":
    main()
