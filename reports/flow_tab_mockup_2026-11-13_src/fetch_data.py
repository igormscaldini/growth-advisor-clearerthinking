"""Pull the Flow mockup's data: GA4 users by first-user channel x landing page (and the outcome events
by the same split) for the last 7, 30 and 90 days, plus Stripe sale counts for the same windows.
Writes data.json beside this file (aggregates only).

    .venv/bin/python reports/flow_tab_mockup_2026-11-13_src/fetch_data.py
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
logging.disable(logging.WARNING)

import data_layer as dl  # noqa: E402
from fetch_snapshot import COG_AMOUNTS, PERSONALITY_AMOUNTS  # noqa: E402
from flow_model import CHANNEL_KEY, group_landing, group_outcomes  # noqa: E402

WINDOWS = {"30d": 30, "7d": 7, "90d": 90}  # 30d first: the review window
OUTCOME_EVENTS = {"Submitted Email": "Email Submitted", "plus_sign_up": "CT+ Sign Up"}


def ga4_rows(start: date, end: date, dims: list[str], metrics: list[str], event_names: list[str] | None = None) -> list[dict]:
    from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest
    from ga4_client import get_client, property_path

    filt = None
    if event_names:
        filt = FilterExpression(filter=Filter(field_name="eventName", in_list_filter=Filter.InListFilter(values=event_names)))
    req = RunReportRequest(property=property_path(), date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
                           dimensions=[Dimension(name=d) for d in dims], metrics=[Metric(name=m) for m in metrics],
                           limit=100_000, dimension_filter=filt)
    for attempt in range(8):
        try:
            resp = get_client().run_report(req, timeout=240)
            return [dict(zip(dims, [v.value for v in r.dimension_values]),
                         **dict(zip(metrics, [float(v.value) for v in r.metric_values]))) for r in resp.rows]
        except Exception as e:  # 429s and deadline errors: back off and retry
            print(f"  GA4 attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:100]}", file=sys.stderr)
            time.sleep(300)
    raise RuntimeError("GA4 query failed after 8 attempts")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default=",".join(WINDOWS), help="comma-separated subset of 30d,7d,90d")
    a = ap.parse_args()
    today = date.today()
    end = today - timedelta(days=1)
    existing = json.loads((HERE / "data.json").read_text()) if (HERE / "data.json").exists() else {}
    raw = json.loads((HERE / "data_raw.json").read_text()) if (HERE / "data_raw.json").exists() else {}
    out = {"fetched": today.isoformat(), "windows": existing.get("windows", {}), "channel_key": CHANNEL_KEY}
    for key in a.windows.split(","):
        days = WINDOWS[key]
        start = end - timedelta(days=days - 1)
        print(f"[{key}] {start} to {end}")
        landing = ga4_rows(start, end, [CHANNEL_KEY, "hostName", "landingPage"], ["totalUsers"])
        time.sleep(5)
        outcomes = ga4_rows(start, end, [CHANNEL_KEY, "hostName", "landingPage", "eventName"],
                            ["totalUsers"], list(OUTCOME_EVENTS))
        time.sleep(5)
        raw[key] = {"start": start.isoformat(), "end": end.isoformat(), "landing": landing, "outcomes": outcomes}
        grouped, dropped = group_landing(landing)
        oc = group_outcomes(outcomes, OUTCOME_EVENTS)
        cog = dl.stripe_charges_daily_by_amounts(start, end, COG_AMOUNTS, False)
        pdf = dl.stripe_charges_daily_by_amounts(start, end, PERSONALITY_AMOUNTS, True)
        subs = dl.stripe_new_subscribers_daily(start, end)
        out["windows"][key] = {
            "start": start.isoformat(), "end": end.isoformat(), "days": days,
            "landing": [{"source": s, "page": p, "users": u} for (s, p), u in sorted(grouped.items(), key=lambda kv: -kv[1])],
            "outcomes": [{"source": s, "page": p, "outcome": o, "users": u} for (s, p, o), u in sorted(oc.items(), key=lambda kv: -kv[1])],
            "dropped_no_landing_page": dropped,
            "stripe": {"cognitive_sales": cog.get("total", 0), "pdf_sales": pdf.get("total", 0),
                       "new_subscriptions": subs.get("total", 0)},
            "top_pages": sorted(
                ({"host": r["hostName"], "path": r["landingPage"], "users": int(r["totalUsers"])} for r in landing),
                key=lambda r: -r["users"])[:40],
        }
        (HERE / "data.json").write_text(json.dumps(out, indent=1))
        (HERE / "data_raw.json").write_text(json.dumps(raw, indent=0))
        w = out["windows"][key]
        print(f"  users {sum(r['users'] for r in w['landing']):,} (dropped {dropped:,} with no landing page); "
              f"email {sum(r['users'] for r in w['outcomes'] if r['outcome'] == 'Email Submitted'):,}; "
              f"plus_sign_up {sum(r['users'] for r in w['outcomes'] if r['outcome'] == 'CT+ Sign Up'):,}; "
              f"stripe {w['stripe']}")
    print("saved", HERE / "data.json", "and data_raw.json")


if __name__ == "__main__":
    main()
