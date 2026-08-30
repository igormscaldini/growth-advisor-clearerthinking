from datetime import date, timedelta
from urllib.parse import urlsplit
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
    Filter, FilterExpression, FilterExpressionList,
)
from ga4_client import get_client, property_path

client = get_client()
end = date.today()
start = end - timedelta(days=365)

req = RunReportRequest(
    property=property_path(),
    date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
    dimensions=[Dimension(name="pagePath"), Dimension(name="eventName")],
    metrics=[Metric(name="eventCount")],
    dimension_filter=FilterExpression(or_group=FilterExpressionList(expressions=[
        FilterExpression(filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value="Accepted Privacy Policy"))),
        FilterExpression(filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value="Submitted Email"))),
    ])),
    limit=100000,
)
resp = client.run_report(req)

agg = {}
for row in resp.rows:
    path = urlsplit(row.dimension_values[0].value).path.rstrip("/").lower() or "/"
    ev = row.dimension_values[1].value
    c = int(row.metric_values[0].value)
    d = agg.setdefault(path, {"started": 0, "submitted": 0})
    if ev == "Accepted Privacy Policy":
        d["started"] += c
    elif ev == "Submitted Email":
        d["submitted"] += c

rows = []
for path, d in agg.items():
    s, sub = d["started"], d["submitted"]
    if s == 0:
        continue
    rows.append((path, s, sub, sub / s * 100))

rows.sort(key=lambda r: r[3], reverse=True)
print(f"Window: {start} to {end}  |  {len(rows)} tools with >=1 start\n")
print(f"{'conv%':>6} {'start':>6} {'submit':>6}  path")
for path, s, sub, conv in rows:
    print(f"{conv:>6.1f} {s:>6} {sub:>6}  {path}")
