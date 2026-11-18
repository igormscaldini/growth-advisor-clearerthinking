"""Independent monthly series to sanity-check the beehiiv count: Google Ads spend and GA4 email submissions.

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/fetch_cross_checks.py

Writes cross_checks.json (aggregates only) next to this file.
- Google Ads: cost, clicks and "Submitted Email" conversions per month and campaign. Shows in which months
  ads could have produced subscribers at all.
- GA4: "Submitted Email" events and users per month, split by session medium (cpc or not) and by page
  (the Who Attracts You study or any other tool). Events are not new subscribers (an existing reader
  submitting an email fires one too), so only the SHAPE across months is comparable.
"""
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

START, END = date(2026, 1, 1), date(2026, 11, 17)
STUDY_PATH = "who_attracts_you"


def google_ads_monthly() -> dict:
    import google_ads_client as gac

    client = gac.get_client()
    svc = client.get_service("GoogleAdsService")
    cid = gac.CUSTOMER_ID.replace("-", "")
    where = f"segments.date BETWEEN '{START}' AND '{END}'"
    out = defaultdict(lambda: defaultdict(lambda: {"cost": 0.0, "clicks": 0, "submitted_email": 0.0}))
    for row in svc.search(customer_id=cid, query=(
            "SELECT segments.month, campaign.name, metrics.cost_micros, metrics.clicks "
            f"FROM campaign WHERE {where}")):
        cell = out[row.segments.month[:7]][row.campaign.name]
        cell["cost"] += row.metrics.cost_micros / 1e6
        cell["clicks"] += row.metrics.clicks
    for row in svc.search(customer_id=cid, query=(
            "SELECT segments.month, campaign.name, segments.conversion_action_name, metrics.all_conversions "
            f"FROM campaign WHERE {where}")):
        if "submitted email" in row.segments.conversion_action_name.lower():
            out[row.segments.month[:7]][row.campaign.name]["submitted_email"] += row.metrics.all_conversions
    return {m: {c: {k: round(v, 2) for k, v in cell.items()} for c, cell in camps.items() if cell["cost"] or cell["clicks"]}
            for m, camps in sorted(out.items())}


def ga4_submitted_email_monthly() -> list:
    from google.analytics.data_v1beta.types import (DateRange, Dimension, Filter, FilterExpression,
                                                    FilterExpressionList, Metric, RunReportRequest)
    from ga4_client import get_client, property_path

    # The page lives in the FILTER only: reports that return a page dimension over a long window time out.
    event = FilterExpression(
        filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value="Submitted Email")))
    on_study = FilterExpression(filter=Filter(field_name="pagePath", string_filter=Filter.StringFilter(
        value=STUDY_PATH, match_type=Filter.StringFilter.MatchType.CONTAINS, case_sensitive=False)))
    # One month per request: the same report over the whole year times out (504).
    pages = {"study": on_study, "other_tools": FilterExpression(not_expression=on_study)}
    client = get_client()
    agg = defaultdict(int)
    for first, last in month_ranges(START, END):
        for page, page_filter in pages.items():
            resp = client.run_report(RunReportRequest(
                property=property_path(),
                date_ranges=[DateRange(start_date=str(first), end_date=str(last))],
                dimensions=[Dimension(name="sessionMedium")],
                metrics=[Metric(name="eventCount")],
                dimension_filter=FilterExpression(and_group=FilterExpressionList(expressions=[event, page_filter])),
                limit=1000,
            ), timeout=120)
            for row in resp.rows:
                medium = "cpc" if row.dimension_values[0].value == "cpc" else "not_cpc"
                agg[(first.strftime("%Y-%m"), medium, page)] += int(row.metric_values[0].value)
    return [{"month": m, "medium": med, "page": pg, "events": n} for (m, med, pg), n in sorted(agg.items())]


def ga4_cpc_daily() -> dict:
    """Submitted Email events per day (GA4 property clock, US Eastern) in sessions whose medium is cpc, on
    CT's own tool pages (the partner-branded /p/ pages are left out: their sign-ups carry an MLA tag in
    beehiiv and are counted from the records). Used to estimate ad sign-ups before 2026-03-27, when the
    tools did not yet write UTM tags into beehiiv."""
    from google.analytics.data_v1beta.types import (DateRange, Dimension, Filter, FilterExpression,
                                                    FilterExpressionList, Metric, RunReportRequest)
    from ga4_client import get_client, property_path

    def text(field, value, match="EXACT"):
        return FilterExpression(filter=Filter(field_name=field, string_filter=Filter.StringFilter(
            value=value, match_type=getattr(Filter.StringFilter.MatchType, match))))

    where = FilterExpression(and_group=FilterExpressionList(expressions=[
        text("eventName", "Submitted Email"), text("sessionMedium", "cpc"),
        FilterExpression(not_expression=text("pagePath", "/p/", "BEGINS_WITH"))]))
    client, out = get_client(), {}
    for first, last in month_ranges(START, END):
        resp = client.run_report(RunReportRequest(
            property=property_path(), date_ranges=[DateRange(start_date=str(first), end_date=str(last))],
            dimensions=[Dimension(name="date")], metrics=[Metric(name="eventCount")],
            dimension_filter=where, limit=1000), timeout=120)
        for row in resp.rows:
            d = row.dimension_values[0].value
            out[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = int(row.metric_values[0].value)
    return dict(sorted(out.items()))


def month_ranges(start: date, end: date) -> list:
    """[(first_day, last_day)] for each calendar month touched by [start, end], clipped to it."""
    out, cur = [], start
    while cur <= end:
        nxt = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
        out.append((cur, min(end, nxt - timedelta(days=1))))
        cur = nxt
    return out


def main():
    out = {"window": [str(START), str(END)]}
    for name, fn in (("google_ads", google_ads_monthly), ("ga4_submitted_email", ga4_submitted_email_monthly),
                     ("ga4_cpc_daily", ga4_cpc_daily)):
        try:
            out[name] = fn()
        except Exception as e:  # keep whatever the other source returned
            out[name] = {"error": f"{type(e).__name__}: {e}"[:500]}
            print(f"[warn] {name} failed: {out[name]['error']}")
    (HERE / "cross_checks.json").write_text(json.dumps(out, indent=1))
    print("wrote cross_checks.json")


if __name__ == "__main__":
    main()
