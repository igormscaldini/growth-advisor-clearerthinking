"""Refresh data/ for analysis.py: beehiiv posts (slimmed), segments, GA4 newsletter clicks.

    python fetch_data.py            # live pull (needs .env: BEEHIIV_API_KEY, GA4 token)
    python fetch_data.py --from-raw DIR   # reuse raw pulls (posts_raw.json, ga4_campaign_hours.json,
                                          # ga4_newsletter.json) already saved in DIR
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
DATA = HERE / "data"
POST_KEYS = ["id", "title", "subtitle", "subject_line", "preview_text", "slug", "publish_date", "audience", "platform",
             "split_tested", "from_address", "send_targets", "content_tags", "authors", "web_url"]


def slim_post(p: dict) -> dict:
    d = {k: p.get(k) for k in POST_KEYS}
    st = p.get("stats") or {}
    d["email"] = st.get("email") or {}
    d["web"] = st.get("web") or {}
    clicks = sorted(st.get("clicks") or [], key=lambda c: -(c.get("total_unique_clicks") or 0))[:5]
    d["top_links"] = [{"url": c.get("base_url"), "unique_clicks": c.get("total_unique_clicks")} for c in clicks]
    return d


def timing_from_rows(posts: list[dict], rows: list) -> dict:
    from analysis import rel_hour_hist, tail_hour_hist
    by_slug = {p["slug"]: p for p in posts}
    camp: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (name, dh), (sess,) in rows:
        camp[name][dh] += int(sess)
    out = {}
    for slug, hours in camp.items():
        p = by_slug.get(slug)
        if not p:
            continue
        send = datetime.fromtimestamp(p["publish_date"], tz=timezone.utc)
        th, tw = tail_hour_hist(send, hours)
        out[slug] = {"send_utc": send.isoformat(), "total": sum(hours.values()),
                     "rel_hours": {str(k): v for k, v in rel_hour_hist(send, hours).items()},
                     "tail_hours": th, "tail_wdays": tw}
    return out


def live_pull() -> tuple[list, list, list]:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from data_layer import _beehiiv_get, BEEHIIV_BASE
    from ga4_client import get_client, property_path
    from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange, FilterExpression, Filter
    h = {"Authorization": f"Bearer {os.getenv('BEEHIIV_API_KEY').strip()}"}
    pub = os.getenv("BEEHIIV_PUB_CLEARER_THINKING").strip()
    posts, page = [], 1
    while True:
        r = _beehiiv_get(f"{BEEHIIV_BASE}/publications/{pub}/posts", headers=h,
                         params={"page": page, "limit": 100, "expand[]": "stats", "status": "confirmed"})
        r.raise_for_status()
        d = r.json()
        posts += d.get("data", [])
        if page >= d.get("total_pages", 1):
            break
        page += 1
    c, prop = get_client(), property_path()

    def run(dims, start, end, limit=10000):
        out, offset = [], 0
        while True:
            req = RunReportRequest(property=prop, dimensions=[Dimension(name=d) for d in dims], metrics=[Metric(name="sessions")],
                                   date_ranges=[DateRange(start_date=start, end_date=end)],
                                   dimension_filter=FilterExpression(filter=Filter(field_name="sessionSource",
                                                                                   string_filter=Filter.StringFilter(match_type="CONTAINS", value="beehiiv"))),
                                   limit=limit, offset=offset)
            r = c.run_report(req)
            out += [([d.value for d in row.dimension_values], [m.value for m in row.metric_values]) for row in r.rows]
            if len(r.rows) < limit:
                break
            offset += limit
        return out
    return posts, run(["sessionCampaignName", "dateHour"], "2026-01-01", "yesterday"), run(["country"], "120daysAgo", "yesterday")


def main():
    DATA.mkdir(exist_ok=True)
    if "--from-raw" in sys.argv:
        raw = Path(sys.argv[sys.argv.index("--from-raw") + 1])
        posts_raw = json.load(open(raw / "posts_raw.json"))
        rows = json.load(open(raw / "ga4_campaign_hours.json"))
        country = json.load(open(raw / "ga4_newsletter.json"))["by_country"]
    else:
        posts_raw, rows, country = live_pull()
    posts = [slim_post(p) for p in posts_raw]
    json.dump(posts, open(DATA / "posts.json", "w"), indent=0)
    json.dump(timing_from_rows(posts, rows), open(DATA / "ga4_timing.json", "w"))
    tot = sum(int(m[0]) for _, m in country)
    top = sorted(country, key=lambda x: -int(x[1][0]))[:15]
    json.dump({"total_sessions": tot, "window": "last 120 days", "top": [(d[0], int(m[0])) for d, m in top]},
              open(DATA / "ga4_country.json", "w"), indent=1)
    print("posts", len(posts), "timing campaigns", len(json.load(open(DATA / "ga4_timing.json"))), "country sessions", tot)


if __name__ == "__main__":
    main()
