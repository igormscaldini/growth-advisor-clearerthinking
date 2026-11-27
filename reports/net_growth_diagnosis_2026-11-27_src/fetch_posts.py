"""Every beehiiv email sent since SINCE with its stats: recipients, opens, clicks, unsubscribes, spam reports.

    .venv/bin/python reports/net_growth_diagnosis_2026-11-27_src/fetch_posts.py

Writes posts.json next to this file (aggregate numbers per send, no personal data). The posts endpoint is
paged in full and filtered here: its default order is not publish date, and adding platform=email made it
drop recent posts (found 2026-11-02), so only `status=confirmed` is asked for.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import data_layer as dl  # noqa: E402

SINCE = datetime(2025, 7, 1, tzinfo=timezone.utc)
OUT = HERE / "posts.json"
EMAIL_STATS = ("recipients", "delivered", "opens", "unique_opens", "clicks", "unique_clicks",
               "unsubscribes", "spam_reports")


def main():
    api_key = os.environ["BEEHIIV_API_KEY"].strip()
    pub_id = os.environ["BEEHIIV_PUB_CLEARER_THINKING"].strip()
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    url = f"{dl.BEEHIIV_BASE}/publications/{pub_id}/posts"

    posts, page = [], 1
    while True:
        r = dl._beehiiv_get_page(url, headers=headers, timeout=(10, 90), params={
            "page": page, "limit": 100, "expand[]": "stats", "status": "confirmed"})
        r.raise_for_status()
        body = r.json()
        posts.extend(body.get("data") or [])
        print(f"page {page}/{body.get('total_pages')}: {len(posts)} posts", flush=True)
        if page >= (body.get("total_pages") or 1):
            break
        page += 1

    rows, seen = [], set()
    for p in posts:
        email = (p.get("stats") or {}).get("email") or {}
        ts = p.get("publish_date")
        if not ts or not email or p["id"] in seen or ts < SINCE.timestamp():
            continue
        seen.add(p["id"])
        row = {"id": p["id"], "publish_ts": int(ts), "title": p.get("title") or "",
               "subject": p.get("subject_line") or "", "audience": p.get("audience"),
               "platform": p.get("platform")}
        row.update({k: int(email.get(k) or 0) for k in EMAIL_STATS})
        rows.append(row)
    rows.sort(key=lambda r: r["publish_ts"])
    OUT.write_text(json.dumps({
        "pulled_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "since": SINCE.strftime("%Y-%m-%d"), "posts": rows}, indent=1))
    print(f"{len(rows)} emailed posts since {SINCE:%Y-%m-%d} -> {OUT}")


if __name__ == "__main__":
    main()
