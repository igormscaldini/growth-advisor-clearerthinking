"""Pull the GA4 audience data behind the sponsor-facing audience page into ga4_datapoints.json.

    .venv/bin/python reports/ct_sponsor_audience_report_2026-10-06_src/fetch_data.py

Two populations, 12 full months (WINDOW):
  demographics  age bracket and gender of website visitors, by month and host. Only visitors Google can
                classify (signed in, ads personalisation on) have a value; GA4 thresholds the rest, so
                these rows are a sample of a few percent of users. Kept by month so the August 2026
                viral wave can be excluded downstream, and by host so the main site and the free tools
                (programs.clearerthinking.org) can be compared.
  newsletter    sessions whose source contains "beehiiv" (clicks from newsletter links) by country,
                device and language, with engaged sessions alongside raw sessions: email link scanners
                register sessions from data-centre locations but almost never engaged ones.
GA4 refuses to combine age/gender with any session-scoped filter, so the newsletter population has
no age or gender breakdown; the survey covers that side.
Survey and Paths figures are NOT pulled here: their single source stays
reports/ct_audience_personas_2026-09-25_src/datapoints.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
OUT = HERE / "ga4_datapoints.json"
WINDOW = ("2025-10-01", "2026-09-30")
HOSTS = ("www.clearerthinking.org", "programs.clearerthinking.org")


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest

    from ga4_client import get_client, property_path
    client, prop = get_client(), property_path()
    rng = [DateRange(start_date=WINDOW[0], end_date=WINDOW[1])]

    def report(dims, metrics, flt=None, limit=20000):
        r = client.run_report(RunReportRequest(property=prop, dimensions=[Dimension(name=d) for d in dims],
                                               metrics=[Metric(name=m) for m in metrics], date_ranges=rng,
                                               dimension_filter=flt, limit=limit))
        rows = [[d.value for d in x.dimension_values] + [int(m.value) for m in x.metric_values] for x in r.rows]
        return rows, r.metadata.subject_to_thresholding

    out = {"pulled": datetime.now(timezone.utc).isoformat(timespec="seconds"), "window": {"start": WINDOW[0], "end": WINDOW[1]},
           "demographics": {}, "newsletter": {}}
    for key, dim in (("age", "userAgeBracket"), ("gender", "userGender")):
        rows, th = report(["yearMonth", "hostName", dim], ["totalUsers"])
        out["demographics"][key] = [{"month": m, "host": h, "value": v, "users": u} for m, h, v, u in rows if h in HOSTS]
        out["demographics"][f"{key}_thresholded"] = th

    newsletter = FilterExpression(filter=Filter(field_name="sessionSource",
                                                string_filter=Filter.StringFilter(match_type="CONTAINS", value="beehiiv")))
    for key, dim in (("country", "country"), ("device", "deviceCategory"), ("language", "language")):
        rows, _ = report([dim], ["sessions", "engagedSessions"], newsletter)
        out["newsletter"][key] = sorted(({"value": v, "sessions": s, "engaged_sessions": e} for v, s, e in rows),
                                        key=lambda r: -r["engaged_sessions"])

    OUT.write_text(json.dumps(out, indent=1))
    nl = out["newsletter"]["country"]
    print(f"age rows {len(out['demographics']['age'])}, gender rows {len(out['demographics']['gender'])}, "
          f"newsletter sessions {sum(r['sessions'] for r in nl):,} (engaged {sum(r['engaged_sessions'] for r in nl):,})")


if __name__ == "__main__":
    main()
