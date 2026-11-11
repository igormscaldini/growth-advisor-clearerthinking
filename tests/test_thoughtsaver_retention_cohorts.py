"""Tests for reports/thoughtsaver_retention_cohorts_2026-11-11_src/analysis.py (day-by-day cohorts).

Layers: hand-worked unit cases; tiny synthetic cohorts whose rates are known by construction; and two
realistic synthetic pulls with the same structure as data/ga4_pull.json, one NULL (nobody completes or
returns) and one POSITIVE (a known curve), run through build_datapoints end to end.
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
END = dt.date(2026, 11, 10)


def signup(created, completed, returns):
    return {"account_created": created, "onboarding_completed": completed, **dict(zip(EV, returns))}


def cohort(day, created, completed, returns, entered=(0, 0)):
    return {"day": day, "signup": signup(created, completed, returns),
            "entered": {"onboarding_entered": entered[0], "account_created": entered[1]}}


# ------------------------------------------------------------------ hand-worked units
def test_events_are_exactly_the_sheet():
    assert A.EVENTS == ["onboarding_entered", "account_created", "onboarding_completed"] + \
        [f"user_return_{n}d" for n in range(1, 11)]
    assert len(A.EVENTS) == 13


def test_days_and_maturity():
    assert A.cohort_days(dt.date(2026, 11, 8), END) == [dt.date(2026, 11, 8), dt.date(2026, 11, 9), END]
    assert A.ga_date(dt.date(2026, 10, 11)) == "20261011"
    assert A.return_n("user_return_10d") == 10 and A.return_n("onboarding_completed") == 0
    assert A.is_mature(dt.date(2026, 11, 8), "user_return_2d", END)  # Nov 8 + 2 = Nov 10
    assert not A.is_mature(dt.date(2026, 11, 8), "user_return_3d", END)
    assert A.is_mature(END, "onboarding_completed", END)  # same-day event: always counted


def test_wilson_and_rate_textbook_values():
    assert A.wilson(5, 10) == (23.66, 76.34)
    assert A.wilson(0, 10) == (0.0, 27.75)  # upper = 3.8416 / 13.8416
    assert A.wilson(0, 0) == (None, None)
    assert A.rate(1, 4) == {"k": 1, "n": 4, "pct": 25.0, "lo": 4.56, "hi": 69.94}
    assert A.rate(0, 0)["pct"] is None


def test_parse_funnel_visualization_fills_missing_steps_with_zero():
    resp = {"funnelVisualization": {"rows": [
        {"dimensionValues": [{"value": "1. account_created"}], "metricValues": [{"value": "6"}]},
        {"dimensionValues": [{"value": "2. user_return_3d"}], "metricValues": [{"value": "2"}]},
    ]}}
    assert A.parse_funnel_visualization(resp, ["account_created", "user_return_3d"]) == \
        {"account_created": 6, "user_return_3d": 2}
    assert A.parse_funnel_visualization({}, ["account_created", "user_return_1d"]) == \
        {"account_created": 0, "user_return_1d": 0}


def test_combine_two_step():
    funnels = [{"account_created": 10, ev: 10 - i} for i, ev in enumerate(A.AFTER_SIGNUP)]
    out = A.combine_two_step(funnels)
    assert out["account_created"] == 10 and out["onboarding_completed"] == 10 and out["user_return_10d"] == 0
    with pytest.raises(ValueError):
        A.combine_two_step([{"account_created": 10, EV[0]: 1}, {"account_created": 9, EV[1]: 1}])
    with pytest.raises(ValueError):
        A.combine_two_step(funnels[:10])


def test_is_monotonic_ignores_completion():
    assert A.is_monotonic(signup(10, 9, [5, 3, 3, 1, 0, 0, 0, 0, 0, 0]))
    assert not A.is_monotonic(signup(10, 9, [1, 2, 0, 0, 0, 0, 0, 0, 0, 0]))


# ------------------------------------------------------------------ small synthetic cohorts
OLD = cohort("2026-10-20", 10, 6, [4, 2, 2, 1, 1, 1, 1, 0, 0, 0], entered=(20, 5))
NEW = cohort("2026-11-09", 5, 2, [1, 0, 0, 0, 0, 0, 0, 0, 0, 0], entered=(10, 1))


def test_cohort_table_blanks_immature_cells():
    old, new = A.cohort_table([OLD, NEW], END)
    assert old["cells"]["onboarding_completed"]["pct"] == 60.0
    assert old["cells"]["user_return_1d"]["pct"] == 40.0 and old["cells"]["user_return_10d"]["pct"] == 0.0
    assert (old["entered"], old["entered_created"], old["signups"]) == (20, 5, 10)
    assert new["cells"]["user_return_1d"]["pct"] == 20.0  # Nov 9 + 1 = Nov 10: mature
    assert new["cells"]["user_return_2d"] is None


def test_pooled_drops_immature_days_from_denominator():
    p = A.pooled([OLD, NEW], END)
    assert (p["onboarding_completed"]["k"], p["onboarding_completed"]["n"]) == (8, 15)
    assert (p["user_return_1d"]["k"], p["user_return_1d"]["n"]) == (5, 15)
    assert (p["user_return_2d"]["k"], p["user_return_2d"]["n"]) == (2, 10)


def test_onboarding_funnel_and_cross_check():
    f = A.onboarding_funnel([OLD, NEW])
    assert (f["entered"], f["created_from_entered"], f["entered_to_created"]["pct"]) == (30, 6, 20.0)
    pooled_pull = {ev: {"account_created": 15, ev: OLD["signup"][ev] + NEW["signup"][ev]} for ev in A.AFTER_SIGNUP}
    cc = A.cross_check([OLD, NEW], pooled_pull)
    assert all(v["per_day_sum"] == v["pooled"] for v in cc.values())


# ------------------------------------------------------------------ realistic synthetic pulls
def synthetic_pull(completion, curve, n=20):
    days = A.cohort_days(A.FIRST_DAY, END)
    cohorts = [cohort(d.isoformat(), n, round(n * completion), [round(n * s) for s in curve], entered=(4 * n, n))
               for d in days]
    pooled = {ev: {"account_created": n * len(days), ev: sum(c["signup"][ev] for c in cohorts)}
              for ev in A.AFTER_SIGNUP}
    return {"pulled_at": "2026-11-11T12:00", "first_day": A.FIRST_DAY.isoformat(), "end": END.isoformat(),
            "cohorts": cohorts, "pooled": pooled,
            "order_check": {"created_then_2d": {}, "created_then_1d_then_2d": {}},
            "naive": [["account_created", str(n * len(days))]]}


def test_null_pull_gives_zero_everywhere():
    dp = A.build_datapoints(synthetic_pull(0, [0] * 10))
    assert dp["total_signups"] == 20 * 31  # Oct 11 to Nov 10 = 31 days
    assert all(r["pct"] == 0.0 and r["lo"] == 0.0 for r in dp["pooled"].values())
    assert dp["non_monotonic_days"] == []


def test_positive_pull_recovers_the_known_curve():
    curve = [0.5, 0.3, 0.2, 0.15, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05]
    dp = A.build_datapoints(synthetic_pull(0.65, curve))
    assert dp["pooled"]["onboarding_completed"]["pct"] == 65.0
    for i, share in enumerate(curve, start=1):
        assert dp["pooled"][f"user_return_{i}d"]["pct"] == round(share * 100, 1)
    # maturity: N return days needs day + N <= Nov 10, so 31 - N days count
    assert dp["pooled"]["onboarding_completed"]["n"] == 20 * 31
    assert dp["pooled"]["user_return_1d"]["n"] == 20 * 30
    assert dp["pooled"]["user_return_10d"]["n"] == 20 * 21
    assert dp["onboarding"]["entered_to_created"]["pct"] == 25.0
    assert all(v["per_day_sum"] == v["pooled"] for v in dp["cross_check"].values())
