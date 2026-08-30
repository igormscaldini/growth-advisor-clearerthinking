import csv
from datetime import date, timedelta
from urllib.parse import urlsplit
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
    Filter, FilterExpression, FilterExpressionList,
)
from ga4_client import get_client, property_path

client = get_client()
end = date.today()
DAYS = 365
start = end - timedelta(days=DAYS)

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

# Aggregate by normalized path (strip query/fragment, lowercase, strip trailing slash)
agg = {}
for row in resp.rows:
    raw = row.dimension_values[0].value
    ev = row.dimension_values[1].value
    c = int(row.metric_values[0].value)
    path = urlsplit(raw).path.rstrip("/").lower() or "/"
    d = agg.setdefault(path, {"started": 0, "submitted": 0})
    if ev == "Accepted Privacy Policy":
        d["started"] += c
    elif ev == "Submitted Email":
        d["submitted"] += c

rows = []
for path, d in agg.items():
    s, sub = d["started"], d["submitted"]
    if s == 0 and sub == 0:
        continue
    conv = (sub / s * 100) if s > 0 else None
    rows.append((path, s, sub, conv))

# Sort by started desc
rows.sort(key=lambda r: r[1], reverse=True)

with open("conv_by_tool.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["pagePath", "started_AcceptedPP", "submitted_email", "conversion_pct"])
    for path, s, sub, conv in rows:
        w.writerow([path, s, sub, f"{conv:.1f}" if conv is not None else ""])

print(f"Window: {start} to {end} ({DAYS} days)")
print(f"Total tool paths with data: {len(rows)}")
tot_s = sum(r[1] for r in rows)
tot_sub = sum(r[2] for r in rows)
print(f"Total Accepted Privacy Policy: {tot_s:,}")
print(f"Total Submitted Email:         {tot_sub:,}")
print(f"Overall conversion:            {tot_sub/tot_s*100:.1f}%")
print("\nAll paths with >=100 starts (sorted by starts):")
print(f"{'started':>8} {'submit':>7} {'conv%':>6}  path")
for path, s, sub, conv in rows:
    if s >= 100:
        print(f"{s:>8} {sub:>7} {conv:>5.1f}  {path}")
