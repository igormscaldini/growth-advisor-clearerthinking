"""Tests for reports/thoughtsaver_retention_cohorts_2026-11-11_src/analysis.py.

Layers: hand-worked unit cases; tiny synthetic cohorts whose rates are known by construction; and two
realistic synthetic pulls with the same structure as data/ga4_pull.json, one NULL (nobody returns) and one
POSITIVE (a known retention curve), run through build_datapoints end to end.
"""
import datetime as dt
import importlib.util
from pathlib import Path

import pytest

# Loaded under a unique name: other report tests also import a module called `analysis`.
_SRC = Path(__file__).resolve().parents[1] / "reports" / "thoughtsaver_retention_cohorts_2026-11-11_src" / "analysis.py"
_spec = importlib.util.spec_from_file_location("thoughtsaver_retention_analysis", _SRC)
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

EV = A.RETURN_EVENTS


def counts(created, returns):
    """Counts dict with `returns` = list of 10 user counts for 1d..10d."""
    return {"account_created": created, **dict(zip(EV, returns))}


# ------------------------------------------------------------------ hand-worked units
def test_week_days_and_mondays():
    assert A.week_days(dt.date(2026, 9, 14)) == [f"202609{d}" for d in range(14, 21)]
    # weeks must end on or before the end date: the week of Nov 9 ends Nov 15, so it is left out
    got = A.cohort_mondays(dt.date(2026, 10, 26), dt.date(2026, 11, 10))
    assert got == [dt.date(2026, 10, 26), dt.date(2026, 11, 2)]
    assert A.cohort_mondays(dt.date(2026, 11, 9), dt.date(2026, 11, 10)) == []


def test_is_mature_uses_last_day_of_week():
    monday = dt.date(2026, 11, 2)  # last sign-up day Sunday Nov 8
    assert A.is_mature(monday, 2, dt.date(2026, 11, 10))  # Nov 8 + 2 = Nov 10
    assert not A.is_mature(monday, 3, dt.date(2026, 11, 10))


def test_wilson_and_rate_textbook_values():
    assert A.wilson(5, 10) == (23.66, 76.34)
    assert A.wilson(0, 10) == (0.0, 27.75)  # upper = 3.8416 / 13.8416
    assert A.wilson(0, 0) == (None, None)
    assert A.rate(1, 4) == {"k": 1, "n": 4, "pct": 25.0, "lo": 4.56, "hi": 69.94}
    assert A.rate(0, 0)["pct"] is None


def test_parse_funnel_visualization_fills_missing_steps_with_zero():
    resp = {"funnelVisualization": {"rows": [
        {"dimensionValues": [{"value": "1. account_created"}], "metricValues": [{"value": "36"}]},
        {"dimensionValues": [{"value": "2. user_return_3d"}], "metricValues": [{"value": "2"}]},
    ]}}
    assert A.parse_funnel_visualization(resp, ["account_created", "user_return_3d"]) == \
        {"account_created": 36, "user_return_3d": 2}
    # GA4 returns no rows at all when nobody entered the funnel
    assert A.parse_funnel_visualization({}, ["account_created", "user_return_1d"]) == \
        {"account_created": 0, "user_return_1d": 0}


def test_combine_two_step():
    funnels = [{"account_created": 10, ev: 10 - i} for i, ev in enumerate(EV)]
    out = A.combine_two_step(funnels)
    assert out["account_created"] == 10 and out["user_return_1d"] == 10 and out["user_return_10d"] == 1
    with pytest.raises(ValueError):
        A.combine_two_step([{"account_created": 10, EV[0]: 1}, {"account_created": 9, EV[1]: 1}])
    with pytest.raises(ValueError):
        A.combine_two_step(funnels[:9])


def test_is_monotonic():
    assert A.is_monotonic(counts(10, [5, 3, 3, 1, 0, 0, 0, 0, 0, 0]))
    assert not A.is_monotonic(counts(10, [1, 2, 0, 0, 0, 0, 0, 0, 0, 0]))


# ------------------------------------------------------------------ small synthetic cohorts
END = dt.date(2026, 11, 10)
OLD = {"cohort": "2026-10-05", "to_date": counts(20, [10, 5, 4, 2, 2, 2, 1, 1, 1, 1]),
       "strict_to_date": counts(20, [10, 4, 3, 1, 1, 1, 0, 0, 0, 0]),
       "window": counts(20, [8, 4, 2, 1, 1, 0, 0, 0, 0, 0])}
NEW = {"cohort": "2026-11-02", "to_date": counts(10, [5, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
       "strict_to_date": counts(10, [5, 1, 0, 0, 0, 0, 0, 0, 0, 0]), "window": None}


def test_cohort_table_blanks_immature_cells():
    old, new = A.cohort_table([OLD, NEW], END)
    assert old["to_date"][1]["pct"] == 50.0 and old["to_date"][10]["pct"] == 5.0
    assert old["window"][2]["pct"] == 20.0 and old["window_signups"] == 20
    assert new["to_date"][2]["pct"] == 10.0  # Nov 8 + 2 days = Nov 10: mature
    assert new["to_date"][3] is None  # not enough days yet
    assert new["window"][1] is None and new["window_signups"] is None


def test_pooled_drops_immature_cohorts_from_denominator():
    p = A.pooled([OLD, NEW], END, "to_date")
    assert (p[1]["k"], p[1]["n"]) == (15, 30)  # both cohorts mature for N=1
    assert (p[2]["k"], p[2]["n"]) == (6, 30)
    assert (p[3]["k"], p[3]["n"]) == (4, 20)  # only the old cohort
    w = A.pooled([OLD, NEW], END, "window")
    assert (w[1]["k"], w[1]["n"]) == (8, 20)
    s = A.pooled([OLD, NEW], END, "strict_to_date")
    assert (s[2]["k"], s[2]["n"]) == (5, 30)


def test_cross_check_sums_cohorts():
    pooled_two_step = {ev: {"account_created": 30, ev: OLD["to_date"][ev] + NEW["to_date"][ev]} for ev in EV}
    cc = A.cross_check([OLD, NEW], pooled_two_step)
    assert all(v["per_cohort_sum"] == v["pooled_two_step"] for v in cc.values())
    assert cc["account_created"]["per_cohort_sum"] == 30


def test_first_visit_cohorts_buckets_by_monday_and_skips_not_set():
    rows = [["20261005", "account_created", "3"], ["20261011", "account_created", "2"],
            ["20261012", "user_return_1d", "4"], ["(not set)", "user_return_1d", "9"],
            ["20260601", "user_return_1d", "7"]]
    got = A.first_visit_cohorts(rows, dt.date(2026, 7, 6), END)
    assert got == {"2026-10-05": {"account_created": 5}, "2026-10-12": {"user_return_1d": 4}}


# ------------------------------------------------------------------ realistic synthetic pulls
def synthetic_pull(curve):
    """A pull shaped like data/ga4_pull.json; `curve` = share of sign-ups reaching 1d..10d."""
    cohorts = []
    for monday in A.cohort_mondays(dt.date(2026, 9, 14), END):
        n = 100
        c = counts(n, [round(n * s) for s in curve])
        win_end = monday + dt.timedelta(days=6 + A.WINDOW_DAYS)
        cohorts.append({"cohort": monday.isoformat(), "to_date": c, "strict_to_date": c,
                        "window": c if win_end <= END else None})
    total = 100 * len(cohorts)
    return {"pulled_at": "2026-11-11T12:00", "end": END.isoformat(), "window_days": A.WINDOW_DAYS,
            "cohorts": cohorts,
            "pooled_two_step": {ev: {"account_created": total, ev: sum(c["to_date"][ev] for c in cohorts)}
                                for ev in EV},
            "naive_last_28d": [["account_created", "50"]],
            "first_visit_cohorts": [["20261005", "account_created", "40"]],
            "weekly_events": [["202641", "account_created", "36", "37"]]}


def test_null_pull_gives_zero_retention_everywhere():
    dp = A.build_datapoints(synthetic_pull([0] * 10))
    assert dp["total_signups"] == 800 and dp["window_signups"] == 600
    for view in ("pooled_to_date", "pooled_window", "pooled_strict_to_date"):
        assert all(r["pct"] == 0.0 and r["lo"] == 0.0 for r in dp[view].values())
    assert all(c["monotonic"] for c in dp["cohorts"])


def test_positive_pull_recovers_the_known_curve():
    curve = [0.5, 0.3, 0.2, 0.15, 0.1, 0.08, 0.06, 0.05, 0.04, 0.03]
    dp = A.build_datapoints(synthetic_pull(curve))
    for i, share in enumerate(curve, start=1):
        assert dp["pooled_to_date"][i]["pct"] == round(share * 100, 1)
        assert dp["pooled_window"][i]["pct"] == round(share * 100, 1)
    # maturity: the Nov 2 cohort (last day Nov 8) is in N=1..2 only, Oct 26 in N<=9, so n falls with N
    assert dp["pooled_to_date"][2]["n"] == 800
    assert dp["pooled_to_date"][3]["n"] == 700
    assert dp["pooled_to_date"][10]["n"] == 600
    assert dp["window_cohorts"] == ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05",
                                    "2026-10-12", "2026-10-19"]
    assert all(v["per_cohort_sum"] == v["pooled_two_step"] for v in dp["cross_check"].values())
