"""Pure functions for the Thought Saver day-by-day sign-up cohort analysis (no network).

data/ga4_pull.json (fetch_data.py) -> datapoints.json (this file's main()) -> build_report.py.

Scope (Igor, 2026-11-11): only the 13 events in Samar's sheet (EVENTS below), only data from
FIRST_DAY on (after Samar's Oct 8 event clean-up), one cohort per DAY.

Definitions
- Cohort of day D: users who fired account_created on app.thoughtsaver.com on day D.
- Completed onboarding / reached N return days: the user fired onboarding_completed / user_return_Nd at
  any time after that account_created (GA4 closed funnel, so earlier sign-ups cannot leak in). Return
  milestones are not required in order: a return on another device is a different GA4 user, so the
  earlier milestone can be missing even though the account (whose counter is server-side) passed it.
- Mature: day D can only have reached N return days if D + N <= the last day of data; immature cells are
  shown as "not yet" and left out of pooled rates.
- Entered onboarding (day D): users who fired onboarding_entered on D, and how many of them later fired
  account_created. This is a separate funnel from the sign-up cohort (same day, different people when a
  sign-up entered onboarding on an earlier day).
"""
import datetime as dt
import json
import math
from pathlib import Path

RETURN_EVENTS = [f"user_return_{n}d" for n in range(1, 11)]
AFTER_SIGNUP = ["onboarding_completed"] + RETURN_EVENTS
EVENTS = ["onboarding_entered", "account_created"] + AFTER_SIGNUP  # exactly the sheet's 13 events
FIRST_DAY = dt.date(2026, 10, 11)
HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------ dates
def ga_date(day):
    return day.strftime("%Y%m%d")


def cohort_days(first, end):
    """Every day from `first` to `end` inclusive."""
    return [first + dt.timedelta(days=i) for i in range((end - first).days + 1)]


def return_n(event):
    """user_return_7d -> 7; onboarding_completed -> 0 (it can happen on the sign-up day)."""
    return int(event[len("user_return_"):-1]) if event.startswith("user_return_") else 0


def is_mature(day, event, end):
    return day + dt.timedelta(days=return_n(event)) <= end


# ------------------------------------------------------------------ GA4 parsing
def parse_funnel_visualization(data, events):
    """{event: users} from a runFunnelReport response; steps GA4 omits (0 users) become 0."""
    rows = data.get("funnelVisualization", {}).get("rows", [])
    by_name = {}
    for r in rows:
        label = r["dimensionValues"][0]["value"]  # e.g. "3. user_return_2d"
        by_name[label.split(". ", 1)[1]] = int(r["metricValues"][0]["value"])
    return {e: by_name.get(e, 0) for e in events}


def combine_two_step(funnels):
    """Merge the (account_created, X) funnels of one cohort into {account_created: n, X: k, ...}."""
    created = {f["account_created"] for f in funnels}
    if len(created) != 1:
        raise ValueError(f"step 1 differs between funnels of the same cohort: {sorted(created)}")
    out = {"account_created": created.pop()}
    for f in funnels:
        out.update({k: v for k, v in f.items() if k != "account_created"})
    missing = [e for e in AFTER_SIGNUP if e not in out]
    if missing:
        raise ValueError(f"no funnel for {missing}")
    return out


def is_monotonic(counts):
    """An account at N+1 return days has passed N, so the counts should never rise with N.

    A rise is possible here when the Nth return happened on another device, so it is flagged, not fixed."""
    seq = [counts[e] for e in RETURN_EVENTS]
    return all(a >= b for a, b in zip(seq, seq[1:]))


# ------------------------------------------------------------------ statistics
def wilson(k, n, z=1.96):
    """95% Wilson score interval in percent, rounded to 2 dp; (None, None) when n == 0."""
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, centre - half) * 100, 2), round(min(1.0, centre + half) * 100, 2))


def rate(k, n):
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "lo": lo, "hi": hi}


# ------------------------------------------------------------------ tables
def cohort_table(cohorts, end):
    """One row per sign-up day; a cell is None when that day is not mature for the event."""
    rows = []
    for c in cohorts:
        day = dt.date.fromisoformat(c["day"])
        s = c["signup"]
        n = s["account_created"]
        cells = {ev: (rate(s[ev], n) if is_mature(day, ev, end) else None) for ev in AFTER_SIGNUP}
        rows.append({"day": c["day"], "entered": c["entered"]["onboarding_entered"],
                     "entered_created": c["entered"]["account_created"], "signups": n,
                     "monotonic": is_monotonic(s), "cells": cells})
    return rows


def pooled(cohorts, end):
    """Per event after sign-up: sum over the cohorts mature for it (the base shrinks as N grows)."""
    out = {}
    for ev in AFTER_SIGNUP:
        k = n = 0
        for c in cohorts:
            if is_mature(dt.date.fromisoformat(c["day"]), ev, end):
                k += c["signup"][ev]
                n += c["signup"]["account_created"]
        out[ev] = rate(k, n)
    return out


def onboarding_funnel(cohorts):
    entered = sum(c["entered"]["onboarding_entered"] for c in cohorts)
    created_from_entered = sum(c["entered"]["account_created"] for c in cohorts)
    return {"entered": entered, "created_from_entered": created_from_entered,
            "entered_to_created": rate(created_from_entered, entered)}


def cross_check(cohorts, pooled_pull):
    """Sum of the per-day funnels vs one funnel over all days at once: each user signs up (first fires
    account_created) once, so they must match unless a user fired account_created on two days."""
    out = {}
    for ev in AFTER_SIGNUP:
        out[ev] = {"per_day_sum": sum(c["signup"][ev] for c in cohorts), "pooled": pooled_pull[ev][ev]}
    out["account_created"] = {"per_day_sum": sum(c["signup"]["account_created"] for c in cohorts),
                              "pooled": pooled_pull[AFTER_SIGNUP[0]]["account_created"]}
    return out


def build_datapoints(pull):
    end = dt.date.fromisoformat(pull["end"])
    cohorts = pull["cohorts"]
    table = cohort_table(cohorts, end)
    return {
        "pulled_at": pull["pulled_at"], "first_day": pull["first_day"], "end": pull["end"],
        "cohorts": table,
        "non_monotonic_days": [r["day"] for r in table if not r["monotonic"]],
        "pooled": pooled(cohorts, end),
        "onboarding": onboarding_funnel(cohorts),
        "total_signups": sum(c["signup"]["account_created"] for c in cohorts),
        "cross_check": cross_check(cohorts, pull["pooled"]),
        "order_check": pull["order_check"],
        "naive": {e: int(u) for e, u in pull["naive"]},
    }


def main():
    pull = json.loads((HERE / "data" / "ga4_pull.json").read_text())
    dp = build_datapoints(pull)
    (HERE / "datapoints.json").write_text(json.dumps(dp, indent=1))
    print("wrote", HERE / "datapoints.json")
    for k, v in dp["cross_check"].items():
        flag = "" if v["per_day_sum"] == v["pooled"] else "  <-- MISMATCH"
        print(f"{k:22s} per-day {v['per_day_sum']:4d}  pooled {v['pooled']:4d}{flag}")


if __name__ == "__main__":
    main()
