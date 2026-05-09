"""Sanity-check report: confirm GA4 access works end-to-end."""
from datetime import date, timedelta

from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)

from ga4_client import PROPERTY_ID, get_client, property_path


def main() -> None:
    client = get_client()
    end = date.today()
    start = end - timedelta(days=7)
    window = f"{start} to {end}"

    print(f"GA4 property: {PROPERTY_ID}")
    print(f"Window:       last 7 days ({window})")

    # Top-line totals
    print("\n--- Top-line metrics ---")
    totals_req = RunReportRequest(
        property=property_path(),
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        metrics=[
            Metric(name="totalUsers"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="engagementRate"),
        ],
    )
    totals = client.run_report(totals_req)
    headers = [m.name for m in totals.metric_headers]
    if totals.rows:
        values = [v.value for v in totals.rows[0].metric_values]
        for h, v in zip(headers, values):
            print(f"  {h:<26} {v}")
    else:
        print("  (no data returned)")

    # Top pages
    print("\n--- Top 10 pages by pageviews ---")
    pages_req = RunReportRequest(
        property=property_path(),
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews"), Metric(name="totalUsers")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
        limit=10,
    )
    pages = client.run_report(pages_req)
    print(f"  {'views':>8}  {'users':>8}  path")
    for row in pages.rows:
        path = row.dimension_values[0].value
        views = row.metric_values[0].value
        users = row.metric_values[1].value
        print(f"  {views:>8}  {users:>8}  {path}")

    # Top traffic sources
    print("\n--- Top 5 traffic sources ---")
    src_req = RunReportRequest(
        property=property_path(),
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=5,
    )
    sources = client.run_report(src_req)
    print(f"  {'sessions':>10}  {'users':>8}  channel")
    for row in sources.rows:
        ch = row.dimension_values[0].value
        sessions = row.metric_values[0].value
        users = row.metric_values[1].value
        print(f"  {sessions:>10}  {users:>8}  {ch}")

    print("\nGA4 connection OK.")


if __name__ == "__main__":
    main()
