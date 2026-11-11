"""Pull Thought Saver sign-up cohort retention from GA4 (property 253193728) into data/ga4_pull.json.

Method agreed with Samar (email "clarification on user events", Oct 9-13, 2026): measure retention per
sign-up cohort instead of event totals, so returns from people who signed up long ago stop leaking into
the counts (which is why user_return_8d could exceed user_return_7d).

GA4 identity is per browser, so a cohort defined by first-visit date alone is still contaminated (an old
user on a new device gets a fresh first-visit date). The fix is a CLOSED FUNNEL, which is user-level:
step 1 = account_created on app.thoughtsaver.com by a user whose firstSessionDate falls in the cohort
week (97% of sign-ups happen on the first-visit day), step 2 = user_return_Nd at any later time, one
funnel per N. A user only counts for N if they created the account first.

Requiring the returns IN ORDER (1d, 2d, ...) was tried and undercounts: 13 sign-ups fired 2d but only 9
of them fired 1d first, because a return made on another browser/device belongs to a different GA4
user. The app's counter is per account, so any user_return_Nd after sign-up means the account reached N.
The in-order version is kept as `strict_to_date`, a lower bound.

Limits found: the Funnel API caps a funnel at 10 steps and a breakdown at 15 values (hence the
firstSessionDate step filter instead of a breakdown), and the property's event-data retention is TWO
MONTHS, so user-level queries return nothing before 2026-09-11. Everything written here is aggregate
counts (no user ids), safe to commit.

Usage: .venv/bin/python reports/thoughtsaver_retention_cohorts_2026-11-11_src/fetch_data.py [--end YYYY-MM-DD]
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import analysis as A  # noqa: E402

PROPERTY = "properties/253193728"  # "Thought Saver - App And Landing Page"
HOST = "app.thoughtsaver.com"  # excludes localhost and Vercel preview deploys (developer traffic)
FIRST_COHORT = dt.date(2026, 9, 14)  # first full Monday week after the 2026-09-11 retention edge
NAIVE_START = dt.date(2026, 7, 6)  # user_return_* events start 2026-07-01


def _headers():
    creds = Credentials.from_authorized_user_file(str(ROOT / "secrets" / "ga4-token.json"))
    creds.refresh(Request())
    return {"Authorization": "Bearer " + creds.token}


def _post(url, headers, body):
    for attempt in range(4):
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        try:
            data = resp.json()
        except ValueError:
            data = {"error": {"message": resp.text[:300]}}
        if "error" not in data:
            return data
        if attempt == 3:
            raise SystemExit(f"GA4 error: {data['error']}")
        time.sleep(3 * (attempt + 1))


def _step(event, first_days=None):
    exprs = [
        {"funnelEventFilter": {"eventName": event}},
        {"funnelFieldFilter": {"fieldName": "hostName", "stringFilter": {"value": HOST}}},
    ]
    if first_days:
        exprs.append({"funnelFieldFilter": {"fieldName": "firstSessionDate",
                                            "inListFilter": {"values": first_days}}})
    return {"name": event, "filterExpression": {"andGroup": {"expressions": exprs}}}


def funnel_counts(headers, events, first_days, start, end):
    """Users reaching each step of a closed funnel whose first step is limited to `first_days`."""
    steps = [_step(events[0], first_days)] + [_step(e) for e in events[1:]]
    body = {"dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
            "funnel": {"isOpenFunnel": False, "steps": steps}}
    data = _post(f"https://analyticsdata.googleapis.com/v1alpha/{PROPERTY}:runFunnelReport", headers, body)
    return A.parse_funnel_visualization(data, events)


def cohort_counts(headers, monday, start, end):
    """MAIN measure: one 2-step funnel per N (account_created, then user_return_Nd at any later time)."""
    days = A.week_days(monday)
    return A.combine_two_step([funnel_counts(headers, ["account_created", ev], days, start, end)
                               for ev in A.RETURN_EVENTS])


def cohort_counts_strict(headers, monday, start, end):
    """Lower bound: returns must appear in order 1d, 2d, ... (10-step cap, so 10d is a separate funnel).

    Undercounts accounts whose earlier return happened on another browser/device (GA4 sees a different
    user there), which is why it is only a sensitivity check.
    """
    days = A.week_days(monday)
    a = funnel_counts(headers, ["account_created"] + A.RETURN_EVENTS[:9], days, start, end)
    b = funnel_counts(headers, ["account_created"] + A.RETURN_EVENTS[:8] + [A.RETURN_EVENTS[9]],
                      days, start, end)
    out = dict(a)
    out[A.RETURN_EVENTS[9]] = b[A.RETURN_EVENTS[9]]
    return out


def run_report(headers, body):
    rows, offset = [], 0
    while True:
        data = _post(f"https://analyticsdata.googleapis.com/v1beta/{PROPERTY}:runReport", headers,
                     dict(body, limit=100000, offset=offset))
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
    headers = _headers()

    cohorts = []
    for monday in A.cohort_mondays(FIRST_COHORT, end):
        row = {"cohort": monday.isoformat(),
               "to_date": cohort_counts(headers, monday, monday, end),
               "strict_to_date": cohort_counts_strict(headers, monday, monday, end)}
        window_end = monday + dt.timedelta(days=6 + A.WINDOW_DAYS)
        row["window"] = cohort_counts(headers, monday, monday, window_end) if window_end <= end else None
        cohorts.append(row)
        print(row["cohort"], row["to_date"], row["window"])

    # Independent cross-check input: one 2-step funnel per N over ALL cohort days in a single query.
    all_days = [d for m in A.cohort_mondays(FIRST_COHORT, end) for d in A.week_days(m)]
    pooled_two_step = {}
    for ev in A.RETURN_EVENTS:
        pooled_two_step[ev] = funnel_counts(headers, ["account_created", ev], all_days, FIRST_COHORT, end)
    print("pooled 2-step", pooled_two_step)

    host = {"filter": {"fieldName": "hostName", "stringFilter": {"value": HOST}}}
    events = ["onboarding_entered", "account_created", "onboarding_completed"] + A.RETURN_EVENTS
    ev_filter = {"filter": {"fieldName": "eventName", "inListFilter": {"values": events}}}
    # The naive view (what produced 8d > 7d): users per event in a calendar window, no cohort.
    naive = run_report(headers, {
        "dateRanges": [{"startDate": (end - dt.timedelta(days=27)).isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": "eventName"}], "metrics": [{"name": "totalUsers"}],
        "dimensionFilter": {"andGroup": {"expressions": [host, ev_filter]}}})
    # First-visit cohorts WITHOUT the funnel (contaminated by old users on new devices), for contrast.
    first_visit = run_report(headers, {
        "dateRanges": [{"startDate": NAIVE_START.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": "firstSessionDate"}, {"name": "eventName"}], "metrics": [{"name": "totalUsers"}],
        "dimensionFilter": {"andGroup": {"expressions": [host, ev_filter]}}})
    # Weekly onboarding volume (users and events), to show the account_created tracking history.
    weekly = run_report(headers, {
        "dateRanges": [{"startDate": NAIVE_START.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": "isoYearIsoWeek"}, {"name": "eventName"}],
        "metrics": [{"name": "totalUsers"}, {"name": "eventCount"}],
        "dimensionFilter": {"andGroup": {"expressions": [host, ev_filter]}}})

    out = {"pulled_at": dt.datetime.now().isoformat(timespec="minutes"), "end": end.isoformat(),
           "property": PROPERTY, "host": HOST, "window_days": A.WINDOW_DAYS,
           "cohorts": cohorts, "pooled_two_step": pooled_two_step,
           "naive_last_28d": naive, "first_visit_cohorts": first_visit, "weekly_events": weekly}
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "ga4_pull.json").write_text(json.dumps(out, indent=1))
    print("wrote", HERE / "data" / "ga4_pull.json")


if __name__ == "__main__":
    main()
