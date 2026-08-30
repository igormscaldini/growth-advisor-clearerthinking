from datetime import date, timedelta
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
    Filter, FilterExpression,
)
from ga4_client import get_client, property_path

client = get_client()
end = date.today()
start = end - timedelta(days=365)
dr = [DateRange(start_date=str(start), end_date=str(end))]

def report(dim, events):
    f = FilterExpression(filter=Filter(field_name="eventName",
        string_filter=Filter.StringFilter(value="email_",
        match_type=Filter.StringFilter.MatchType.BEGINS_WITH)))
    req = RunReportRequest(property=property_path(), date_ranges=dr,
        dimensions=[Dimension(name="eventName"), Dimension(name=dim)],
        metrics=[Metric(name="eventCount"), Metric(name="activeUsers")],
        dimension_filter=f, limit=100000)
    resp = client.run_report(req)
    out = {e: [] for e in events}
    for r in resp.rows:
        ev = r.dimension_values[0].value
        if ev not in out: continue
        out[ev].append((r.dimension_values[1].value,
                         int(r.metric_values[0].value),
                         int(r.metric_values[1].value)))
    return out

EVENTS = ["email_click", "email_visit"]

print(f"Window: {start} to {end}\n")

# Device — full
dev = report("deviceCategory", EVENTS)
for ev in EVENTS:
    rows = sorted(dev[ev], key=lambda x: -x[2])
    tu = sum(r[2] for r in rows)
    print(f"=== {ev} — device (users total={tu}) ===")
    for name, ec, u in rows:
        print(f"  {name:10} users={u:>6} ({u/tu*100:4.1f}%)  events={ec}")
    print()

# Country — full
ctry = report("country", EVENTS)
for ev in EVENTS:
    rows = sorted(ctry[ev], key=lambda x: -x[2])
    tu = sum(r[2] for r in rows)
    print(f"=== {ev} — country (users total={tu}, {len(rows)} countries) ===")
    cum = 0
    for name, ec, u in rows[:15]:
        cum += u
        print(f"  {name:22} users={u:>6} ({u/tu*100:4.1f}%)  events={ec}")
    print(f"  top15 = {cum/tu*100:.1f}% of users\n")
