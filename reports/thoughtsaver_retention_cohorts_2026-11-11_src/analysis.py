"""Pure functions for the Thought Saver sign-up cohort retention analysis (no network).

data/ga4_pull.json (fetch_data.py) -> datapoints.json (this file's main()) -> build_report.py.

Definitions
- Cohort: users whose first visit (GA4 firstSessionDate) falls in a Monday-Sunday week AND who fired
  account_created on app.thoughtsaver.com. 97% of sign-ups happen on the first-visit day.
- Reached N: the user fired user_return_Nd at any time after account_created, i.e. the account came
  back on at least N distinct days after the sign-up day (Samar's definition; days need not be
  consecutive). Order of the earlier milestones is not required (see fetch_data.py for why).
- "to_date": every return up to the end of the data. A cell is MATURE only if even the last sign-up day of
  the week has had N full days since, otherwise it is shown as partial and left out of pooled rates.
- "window": returns within WINDOW_DAYS after the end of the cohort week (14-20 days after sign-up), which
  gives every cohort the same amount of time and so is the fair comparison across weeks.
"""
import datetime as dt
import json
import math
from pathlib import Path

RETURN_EVENTS = [f"user_return_{n}d" for n in range(1, 11)]
WINDOW_DAYS = 14
HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------ dates
def week_days(monday):
    """The seven GA4 date strings (YYYYMMDD) of the week starting on `monday`."""
    return [(monday + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]


def cohort_mondays(first, end):
    """Mondays from `first` whose whole week (Mon-Sun) ends on or before `end`."""
    out, m = [], first
    while m + dt.timedelta(days=6) <= end:
        out.append(m)
        m += dt.timedelta(days=7)
    return out


def is_mature(monday, n, end):
    """True when the LAST sign-up day of the cohort week has had at least n later days by `end`."""
    return monday + dt.timedelta(days=6 + n) <= end


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
    """Merge the ten (account_created, user_return_Nd) funnels of one cohort into one counts dict."""
    created = {f["account_created"] for f in funnels}
    if len(created) != 1:
        raise ValueError(f"step 1 differs between funnels of the same cohort: {sorted(created)}")
    out = {"account_created": created.pop()}
    for f in funnels:
        out.update({k: v for k, v in f.items() if k != "account_created"})
    missing = [e for e in RETURN_EVENTS if e not in out]
    if missing:
        raise ValueError(f"no funnel for {missing}")
    return out


def is_monotonic(counts):
    """An account at N+1 return days has passed N, so counts should never rise with N.

    With the any-order measure a rise is still possible when the Nth return happened on another
    device; a rise is therefore flagged, not corrected."""
    seq = [counts["account_created"]] + [counts[e] for e in RETURN_EVENTS]
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
    """Per-cohort rows: sign-ups plus, for each N, the to-date rate (None if immature) and window rate."""
    rows = []
    for c in cohorts:
        monday = dt.date.fromisoformat(c["cohort"])
        td, win = c["to_date"], c["window"]
        n = td["account_created"]
        row = {"cohort": c["cohort"], "signups": n, "monotonic": is_monotonic(td),
               "to_date": {}, "window": {}}
        for i, ev in enumerate(RETURN_EVENTS, start=1):
            row["to_date"][i] = rate(td[ev], n) if is_mature(monday, i, end) else None
            row["window"][i] = rate(win[ev], win["account_created"]) if win else None
        row["window_signups"] = win["account_created"] if win else None
        rows.append(row)
    return rows


def pooled(cohorts, end, view):
    """Pooled rate per N over every cohort usable for that N.

    view="to_date" / "strict_to_date": cohorts mature for N (so the denominator shrinks as N grows);
    view="window": cohorts with a complete window (same set for every N).
    """
    out = {}
    for i, ev in enumerate(RETURN_EVENTS, start=1):
        k = n = 0
        for c in cohorts:
            monday = dt.date.fromisoformat(c["cohort"])
            if view == "window":
                if not c["window"]:
                    continue
            elif not is_mature(monday, i, end):
                continue
            src = c[view]
            k += src[ev]
            n += src["account_created"]
        out[i] = rate(k, n)
    return out


def first_visit_cohorts(rows, start, end):
    """Weekly users per event from firstSessionDate x eventName rows (NO funnel: the contaminated view)."""
    weeks = {}
    for fsd, event, users in rows:
        if fsd in ("(not set)", ""):
            continue
        d = dt.datetime.strptime(fsd, "%Y%m%d").date()
        if d < start or d > end:
            continue
        monday = (d - dt.timedelta(days=d.weekday())).isoformat()
        weeks.setdefault(monday, {}).setdefault(event, 0)
        weeks[monday][event] += int(users)
    return dict(sorted(weeks.items()))


def weekly_events(rows):
    """{iso week: {event: [users, events]}} from isoYearIsoWeek x eventName rows."""
    out = {}
    for week, event, users, count in rows:
        out.setdefault(week, {})[event] = [int(users), int(count)]
    return dict(sorted(out.items()))


def naive_counts(rows):
    return {e: int(u) for e, u in rows}


def cross_check(cohorts, pooled_two_step):
    """Sum of the per-cohort funnels (one query per week and N) vs one funnel per N over all cohort days.

    Each user has exactly one firstSessionDate, so the two must agree exactly; a gap means the cohort
    split or the per-cohort date ranges lose or double-count users."""
    out = {}
    for ev in RETURN_EVENTS:
        summed = sum(c["to_date"][ev] for c in cohorts)
        out[ev] = {"per_cohort_sum": summed, "pooled_two_step": pooled_two_step[ev][ev]}
    out["account_created"] = {"per_cohort_sum": sum(c["to_date"]["account_created"] for c in cohorts),
                              "pooled_two_step": pooled_two_step[RETURN_EVENTS[0]]["account_created"]}
    return out


def build_datapoints(pull):
    end = dt.date.fromisoformat(pull["end"])
    cohorts = pull["cohorts"]
    return {
        "pulled_at": pull["pulled_at"], "end": pull["end"], "window_days": pull["window_days"],
        "cohorts": cohort_table(cohorts, end),
        "pooled_to_date": pooled(cohorts, end, "to_date"),
        "pooled_window": pooled(cohorts, end, "window"),
        "pooled_strict_to_date": pooled(cohorts, end, "strict_to_date"),
        "total_signups": sum(c["to_date"]["account_created"] for c in cohorts),
        "window_signups": sum(c["window"]["account_created"] for c in cohorts if c["window"]),
        "window_cohorts": [c["cohort"] for c in cohorts if c["window"]],
        "cross_check": cross_check(cohorts, pull["pooled_two_step"]),
        "naive_last_28d": naive_counts(pull["naive_last_28d"]),
        "first_visit_cohorts": first_visit_cohorts(pull["first_visit_cohorts"], dt.date(2026, 7, 6), end),
        "weekly_events": weekly_events(pull["weekly_events"]),
    }


def main():
    pull = json.loads((HERE / "data" / "ga4_pull.json").read_text())
    dp = build_datapoints(pull)
    (HERE / "datapoints.json").write_text(json.dumps(dp, indent=1))
    print("wrote", HERE / "datapoints.json")
    for k, v in dp["cross_check"].items():
        flag = "" if v["per_cohort_sum"] == v["pooled_two_step"] else "  <-- MISMATCH"
        print(f"{k:22s} per-cohort {v['per_cohort_sum']:4d}  pooled 2-step {v['pooled_two_step']:4d}{flag}")


if __name__ == "__main__":
    main()
