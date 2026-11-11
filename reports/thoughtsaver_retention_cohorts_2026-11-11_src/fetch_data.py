"""Pull Thought Saver day-by-day sign-up cohorts from GA4 (property 253193728) into data/ga4_pull.json.

Method agreed with Samar (email "clarification on user events", Oct 9-13, 2026): follow each sign-up
cohort instead of counting events, so returns from people who signed up long ago stop leaking into the
counts (which is why user_return_8d could exceed user_return_7d). Scope set by Igor on 2026-11-11: only the
13 events in Samar's sheet, data from 2026-10-11 on, one cohort per day. Definitions: analysis.py.

How: GA4 CLOSED FUNNELS (Data API v1alpha runFunnelReport), which follow each user. Step 1 =
account_created on app.thoughtsaver.com with a `date` field filter = the cohort day; step 2 = the later
event, one 2-step funnel per event (a funnel caps at 10 steps; and requiring the returns in order
undercounts, see `order_check`). onboarding_entered gets its own funnel per day (entered on D, then
account_created).

Property limits found: event-data retention is TWO MONTHS (funnels return nothing before ~Sep 11, 2026);
localhost and Vercel preview deploys report to it (filtered out by hostName). Output is aggregate counts
only (no user ids).

Usage: .venv/bin/python reports/thoughtsaver_retention_cohorts_2026-11-11_src/fetch_data.py [--end YYYY-MM-DD]
"""
import argparse
import datetime as dt
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import analysis as A  # noqa: E402

PROPERTY = "properties/253193728"  # "Thought Saver - App And Landing Page"
HOST = "app.thoughtsaver.com"
API = "https://analyticsdata.googleapis.com"


def _headers():
    creds = Credentials.from_authorized_user_file(str(ROOT / "secrets" / "ga4-token.json"))
    creds.refresh(Request())
    return {"Authorization": "Bearer " + creds.token}


def _post(url, headers, body):
    for attempt in range(6):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=120)
            data = resp.json()
        except (ValueError, requests.RequestException) as exc:
            data = {"error": {"message": str(exc)[:300]}}
        if "error" not in data:
            return data
        if attempt == 5:
            raise SystemExit(f"GA4 error: {data['error']}")
        time.sleep(4 * (attempt + 1))


def _step(event, days=None):
    exprs = [{"funnelEventFilter": {"eventName": event}},
             {"funnelFieldFilter": {"fieldName": "hostName", "stringFilter": {"value": HOST}}}]
    if days:
        exprs.append({"funnelFieldFilter": {"fieldName": "date", "inListFilter": {"values": days}}})
    return {"name": event, "filterExpression": {"andGroup": {"expressions": exprs}}}


def funnel_counts(headers, events, days, start, end):
    """Users reaching each step of a closed funnel whose FIRST step must happen on one of `days`."""
    steps = [_step(events[0], days)] + [_step(e) for e in events[1:]]
    body = {"dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
            "funnel": {"isOpenFunnel": False, "steps": steps}}
    return A.parse_funnel_visualization(_post(f"{API}/v1alpha/{PROPERTY}:runFunnelReport", headers, body), events)


def day_cohort(headers, day, end):
    d = [A.ga_date(day)]
    signup = A.combine_two_step([funnel_counts(headers, ["account_created", ev], d, day, end)
                                 for ev in A.AFTER_SIGNUP])
    entered = funnel_counts(headers, ["onboarding_entered", "account_created"], d, day, end)
    return {"day": day.isoformat(), "signup": signup, "entered": entered}


def run_report(headers, body):
    rows, offset = [], 0
    while True:
        data = _post(f"{API}/v1beta/{PROPERTY}:runReport", headers, dict(body, limit=100000, offset=offset))
        got = data.get("rows", [])
        rows += [[v["value"] for v in r["dimensionValues"] + r["metricValues"]] for r in got]
        offset += len(got)
        if not got or offset >= data.get("rowCount", 0):
            return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=(dt.date.today() - dt.timedelta(days=1)).isoformat(),
                    help="last complete day of data (default: yesterday)")
    end = dt.date.fromisoformat(ap.parse_args().end)
    first = A.FIRST_DAY
    headers = _headers()
    days = A.cohort_days(first, end)

    with ThreadPoolExecutor(max_workers=4) as pool:  # GA4 allows 10 concurrent requests per property
        cohorts = list(pool.map(lambda day: day_cohort(headers, day, end), days))
        all_days = [A.ga_date(d) for d in days]
        # Independent cross-check: one funnel per event over ALL cohort days in a single query.
        pooled = dict(zip(A.AFTER_SIGNUP, pool.map(
            lambda ev: funnel_counts(headers, ["account_created", ev], all_days, first, end), A.AFTER_SIGNUP)))
    for c in cohorts:
        print(c["day"], c["entered"], c["signup"])

    # Why the returns are not required in order: people with 2d after sign-up vs those with 1d then 2d.
    order_check = {
        "created_then_2d": funnel_counts(headers, ["account_created", "user_return_2d"], all_days, first, end),
        "created_then_1d_then_2d": funnel_counts(headers, ["account_created", "user_return_1d", "user_return_2d"],
                                                 all_days, first, end),
    }
    # The naive view (what produced 8d > 7d): users per event over the same period, no cohort.
    naive = run_report(headers, {
        "dateRanges": [{"startDate": first.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": "eventName"}], "metrics": [{"name": "totalUsers"}],
        "dimensionFilter": {"andGroup": {"expressions": [
            {"filter": {"fieldName": "hostName", "stringFilter": {"value": HOST}}},
            {"filter": {"fieldName": "eventName", "inListFilter": {"values": A.EVENTS}}}]}}})

    out = {"pulled_at": dt.datetime.now().isoformat(timespec="minutes"), "first_day": first.isoformat(),
           "end": end.isoformat(), "property": PROPERTY, "host": HOST, "cohorts": cohorts,
           "pooled": pooled, "order_check": order_check, "naive": naive}
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "ga4_pull.json").write_text(json.dumps(out, indent=1))
    print("wrote", HERE / "data" / "ga4_pull.json")


if __name__ == "__main__":
    main()
