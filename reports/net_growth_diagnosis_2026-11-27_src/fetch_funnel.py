"""The inflow side: how many people reach the tools and how many of them hand over an email.

    .venv/bin/python reports/net_growth_diagnosis_2026-11-27_src/fetch_funnel.py

Writes funnel.json next to this file (aggregates only):
- GA4, one request per month (longer ranges time out): the tool funnel events on programs.clearerthinking.org
  by page and by paid (session medium cpc) vs not paid.
- Search Console, one request per month: clicks and impressions for the tools host and for the rest of the
  site, taken with the `date` dimension only (a page filter plus any other dimension drops anonymized
  queries), and the tools' clicks by page.
"""
import json
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

FIRST_MONTH = date(2025, 8, 1)
LAST_DAY = date(2026, 11, 26)
OUT = HERE / "funnel.json"
TOOLS_HOST = "programs.clearerthinking.org"
EVENTS = ("Viewed Privacy Policy", "Accepted Privacy Policy", "Reached Email Ask", "Submitted Email")


def months():
    m = FIRST_MONTH
    while m <= LAST_DAY:
        nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        yield m, min(nxt - timedelta(days=1), LAST_DAY)
        m = nxt


def ga4_month(client, prop, start, end):
    from google.analytics.data_v1beta.types import (DateRange, Dimension, Filter, FilterExpression,
                                                    FilterExpressionList, Metric, RunReportRequest)
    request = RunReportRequest(
        property=prop,
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="pagePath"), Dimension(name="eventName"), Dimension(name="sessionMedium")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(and_group=FilterExpressionList(expressions=[
            FilterExpression(filter=Filter(field_name="hostName",
                                           string_filter=Filter.StringFilter(value=TOOLS_HOST))),
            FilterExpression(or_group=FilterExpressionList(expressions=[
                FilterExpression(filter=Filter(field_name="eventName",
                                               string_filter=Filter.StringFilter(value=ev)))
                for ev in EVENTS])),
        ])),
        limit=250000,
    )
    for attempt in range(4):
        try:
            resp = client.run_report(request)
            break
        except Exception as exc:  # GA4 answers 429/502/504 in bursts; a pause is the only cure
            if attempt == 3:
                raise
            print(f"  GA4 retry after {type(exc).__name__}", flush=True)
            time.sleep(20 * (attempt + 1))
    rows = []
    for r in resp.rows:
        page, event, medium = (v.value for v in r.dimension_values)
        rows.append({"page": page, "event": event, "paid": medium == "cpc",
                     "count": int(r.metric_values[0].value)})
    return rows


def gsc_query(service, site, body):
    return service.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])


def gsc_month(service, site, start, end):
    base = {"startDate": str(start), "endDate": str(end), "rowLimit": 25000}
    tools_filter = [{"filters": [{"dimension": "page", "operator": "contains", "expression": TOOLS_HOST}]}]
    total = gsc_query(service, site, {**base, "dimensions": ["date"]})
    tools = gsc_query(service, site, {**base, "dimensions": ["date"], "dimensionFilterGroups": tools_filter})
    pages = gsc_query(service, site, {**base, "dimensions": ["page"], "dimensionFilterGroups": tools_filter})

    def tot(rows, key):
        return int(sum(r[key] for r in rows))

    return {
        "all_clicks": tot(total, "clicks"), "all_impressions": tot(total, "impressions"),
        "tools_clicks": tot(tools, "clicks"), "tools_impressions": tot(tools, "impressions"),
        "days": len(total),
        "tool_pages": sorted(({"page": r["keys"][0], "clicks": int(r["clicks"])} for r in pages),
                             key=lambda r: -r["clicks"])[:25],
    }


def main():
    from ga4_client import get_client as ga4_client, property_path
    from gsc_client import SITE_URL, get_client as gsc_client

    ga4, gsc = ga4_client(), gsc_client()
    out = {"window": [str(FIRST_MONTH), str(LAST_DAY)], "ga4": {}, "gsc": {}}
    for start, end in months():
        key = start.strftime("%Y-%m")
        rows = ga4_month(ga4, property_path(), start, end)
        totals = defaultdict(int)
        for r in rows:
            totals[r["event"]] += r["count"]
        out["ga4"][key] = rows
        out["gsc"][key] = gsc_month(gsc, SITE_URL, start, end)
        print(key, dict(totals), "GSC tools clicks", out["gsc"][key]["tools_clicks"], flush=True)
        OUT.write_text(json.dumps(out))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
