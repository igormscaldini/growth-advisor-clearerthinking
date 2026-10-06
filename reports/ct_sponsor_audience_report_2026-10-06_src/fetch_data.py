"""Refresh data/ for the sponsor-facing audience report.

    .venv/bin/python reports/ct_sponsor_audience_report_2026-10-06_src/fetch_data.py

Pulls (needs .env: BEEHIIV_API_KEY, BEEHIIV_PUB_CLEARER_THINKING, GA4 token):
  data/posts.json         every confirmed beehiiv email send with its email stats and the
                          top links by unique clicks, plus any link on a known sponsor domain
  data/engaged.json       size of beehiiv's "Engaged Reades - Open > 40%" segment
  data/ga4_country.json   GA4 sessions from newsletter links (sessionSource contains "beehiiv")
                          by country, last 90 days
Survey and Paths figures are NOT pulled here: the single source for those stays
reports/ct_audience_personas_2026-09-25_src/datapoints.json.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
DATA = HERE / "data"
POST_KEYS = ["id", "title", "subject_line", "slug", "publish_date", "audience", "platform",
             "split_tested", "from_address", "web_url"]
# Links on these domains are sponsor or partner links; keep every one of them, not just the top links.
SPONSOR_DOMAINS = ("80000hours.org", "kickstarter.com", "animalcharityevaluators.org", "farmkind.giving",
                   "hive", "givingwhatwecan.org", "givewell.org")
TOP_LINKS = 15


def slim_post(p: dict) -> dict:
    d = {k: p.get(k) for k in POST_KEYS}
    st = p.get("stats") or {}
    d["email"] = st.get("email") or {}
    clicks = sorted(st.get("clicks") or [], key=lambda c: -(c.get("total_unique_clicks") or 0))
    keep = clicks[:TOP_LINKS] + [c for c in clicks[TOP_LINKS:]
                                 if any(dom in (c.get("base_url") or "") for dom in SPONSOR_DOMAINS)]
    d["links"] = [{"url": c.get("base_url"), "unique_clicks": c.get("total_unique_clicks"),
                   "clicks": c.get("total_clicks")} for c in keep]
    return d


def pull_posts() -> list[dict]:
    from data_layer import BEEHIIV_BASE, _beehiiv_get
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
    return posts


def pull_ga4_country(days: int = 90) -> dict:
    from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest

    from ga4_client import get_client, property_path
    req = RunReportRequest(
        property=property_path(), dimensions=[Dimension(name="country")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="yesterday")],
        dimension_filter=FilterExpression(filter=Filter(
            field_name="sessionSource", string_filter=Filter.StringFilter(match_type="CONTAINS", value="beehiiv"))),
        limit=250)
    rows = [(r.dimension_values[0].value, int(r.metric_values[0].value), int(r.metric_values[1].value))
            for r in get_client().run_report(req).rows]
    rows.sort(key=lambda x: -x[1])
    return {"window_days": days, "pulled": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total_sessions": sum(r[1] for r in rows), "total_users": sum(r[2] for r in rows),
            "rows": [{"country": c, "sessions": s, "users": u} for c, s, u in rows]}


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from data_layer import beehiiv_engaged_readers
    DATA.mkdir(exist_ok=True)

    posts = [slim_post(p) for p in pull_posts()]
    posts.sort(key=lambda p: p.get("publish_date") or 0)
    json.dump({"pulled": datetime.now(timezone.utc).isoformat(timespec="seconds"), "posts": posts},
              open(DATA / "posts.json", "w"), indent=0)
    json.dump(beehiiv_engaged_readers(), open(DATA / "engaged.json", "w"), indent=1)
    json.dump(pull_ga4_country(), open(DATA / "ga4_country.json", "w"), indent=1)
    print("posts", len(posts), "| engaged", json.load(open(DATA / "engaged.json")),
          "| ga4 sessions", json.load(open(DATA / "ga4_country.json"))["total_sessions"])


if __name__ == "__main__":
    main()
