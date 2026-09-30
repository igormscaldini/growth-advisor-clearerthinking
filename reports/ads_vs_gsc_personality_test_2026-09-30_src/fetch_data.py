"""Fetch the raw data for the Ads-vs-GSC "personality test" analysis into data/.

- data/ads_daily.csv: daily spend/impressions/clicks per Google Ads campaign (all campaigns).
- data/gsc_query_device_daily.csv: GSC daily x device for the exact query "personality test".
- data/gsc_control_daily.csv: GSC daily x device for every query EXCEPT ones containing
  "personality" / "mbti" / "test" (a control series the UPT campaign cannot plausibly touch).
- data/ads_search_terms.csv: search-term insight categories for the UPT campaign per ON period.

Run from the repo root: .venv/bin/python reports/ads_vs_gsc_personality_test_2026-09-30_src/fetch_data.py
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
DATA = HERE / "data"

from analysis import UPT_CAMPAIGN_ID, QUERY, on_periods  # noqa: E402

START, END = "2025-05-01", "2026-09-29"


def fetch_ads() -> pd.DataFrame:
    from google_ads_client import CUSTOMER_ID, get_client
    svc = get_client().get_service("GoogleAdsService")
    q = f"""SELECT campaign.id, campaign.name, segments.date, metrics.cost_micros,
            metrics.impressions, metrics.clicks FROM campaign
            WHERE segments.date BETWEEN '2023-01-01' AND '{END}' AND metrics.impressions > 0"""
    rows = []
    for b in svc.search_stream(customer_id=CUSTOMER_ID, query=q):
        for r in b.results:
            rows.append(dict(campaign_id=r.campaign.id, campaign=r.campaign.name, date=r.segments.date,
                             spend=r.metrics.cost_micros / 1e6, impressions=r.metrics.impressions,
                             clicks=r.metrics.clicks))
    return pd.DataFrame(rows).sort_values(["date", "campaign_id"])


def fetch_search_terms(ads: pd.DataFrame) -> pd.DataFrame:
    from google_ads_client import CUSTOMER_ID, get_client
    svc = get_client().get_service("GoogleAdsService")
    u = ads[ads.campaign_id == UPT_CAMPAIGN_ID].set_index("date")["spend"]
    rows = []
    for start, end in on_periods(u, START, END):
        q = f"""SELECT campaign_search_term_insight.category_label, metrics.impressions, metrics.clicks
                FROM campaign_search_term_insight
                WHERE campaign_search_term_insight.campaign_id = '{UPT_CAMPAIGN_ID}'
                AND segments.date BETWEEN '{start}' AND '{end}'"""
        for b in svc.search_stream(customer_id=CUSTOMER_ID, query=q):
            for r in b.results:
                rows.append(dict(period_start=start, period_end=end,
                                 category=r.campaign_search_term_insight.category_label,
                                 impressions=r.metrics.impressions, clicks=r.metrics.clicks))
    return pd.DataFrame(rows)


def _gsc(dims, filters) -> pd.DataFrame:
    from gsc_client import SITE_URL, get_client
    svc = get_client()
    out, start_row = [], 0
    while True:
        body = {"startDate": START, "endDate": END, "dimensions": dims, "rowLimit": 25000,
                "startRow": start_row, "dataState": "final",
                "dimensionFilterGroups": [{"filters": filters}]}
        rows = svc.searchanalytics().query(siteUrl=SITE_URL, body=body).execute().get("rows", [])
        out += [dict(zip(dims, r["keys"]), clicks=r["clicks"], impressions=r["impressions"],
                     position=r["position"]) for r in rows]
        if len(rows) < 25000:
            return pd.DataFrame(out)
        start_row += 25000


def main():
    DATA.mkdir(exist_ok=True)
    ads = fetch_ads()
    ads.to_csv(DATA / "ads_daily.csv", index=False)
    fetch_search_terms(ads).to_csv(DATA / "ads_search_terms.csv", index=False)
    _gsc(["date", "device"], [{"dimension": "query", "operator": "equals", "expression": QUERY}]) \
        .to_csv(DATA / "gsc_query_device_daily.csv", index=False)
    # Control: everything not about personality / MBTI / tests (anonymised queries are
    # excluded by any query filter, which is fine for a control).
    _gsc(["date", "device"], [
        {"dimension": "query", "operator": "excludingRegex", "expression": "(?i)personality|mbti|test|quiz"},
    ]).to_csv(DATA / "gsc_control_daily.csv", index=False)
    print("wrote", sorted(p.name for p in DATA.iterdir()))


if __name__ == "__main__":
    main()
