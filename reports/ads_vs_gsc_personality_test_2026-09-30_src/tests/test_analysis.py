import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import analysis as A  # noqa: E402


def _spend(days_on, start="2025-01-01", n=20):
    idx = pd.date_range(start, periods=n).strftime("%Y-%m-%d")
    return pd.Series([50.0 if i in days_on else 0.0 for i in range(n)], index=idx)


# ------------------------------------------------------------------ hand-computed cases

def test_on_flag_merges_one_day_gap_but_not_long_gap():
    # ON days 2-4, a 1-day pause on 5, ON 6-7, then a 5-day gap, ON 13
    s = _spend({2, 3, 4, 6, 7, 13})
    on = A.on_flag(s, "2025-01-01", "2025-01-20")
    assert on.tolist() == [0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    assert A.on_periods(s, "2025-01-01", "2025-01-20") == [
        ("2025-01-03", "2025-01-08"), ("2025-01-14", "2025-01-14")]


def test_on_flag_ignores_sub_dollar_spend():
    s = _spend({3})
    s.iloc[5] = 0.5
    assert A.on_flag(s, "2025-01-01", "2025-01-20").sum() == 1


def test_gsc_daily_weights_position_by_impressions():
    g = pd.DataFrame({"date": ["2025-01-01"] * 2, "device": ["MOBILE", "DESKTOP"],
                      "clicks": [10, 20], "impressions": [100, 300], "position": [2.0, 6.0]})
    d = A.gsc_daily(g)
    assert d["position"].iloc[0] == pytest.approx(5.0)  # (2*100 + 6*300) / 400
    assert d["ctr"].iloc[0] == pytest.approx(30 / 400)
    assert A.gsc_daily(g, ["MOBILE"])["position"].iloc[0] == pytest.approx(2.0)


def test_switch_effects_signed_so_positive_means_on_is_higher():
    idx = pd.date_range("2025-01-01", periods=30)
    on = pd.Series([0] * 10 + [1] * 10 + [0] * 10, index=idx)
    y = pd.Series(np.where(on == 1, 12.0, 10.0), index=idx)
    e = A.switch_effects(y, on, window=5, min_days=5)
    assert e["direction"].tolist() == ["OFF->ON", "ON->OFF"]
    assert e["on_minus_off"].tolist() == pytest.approx([2.0, 2.0])
    assert e["pct"].tolist() == pytest.approx([20.0, 20.0])


def test_switch_effects_drops_switch_without_enough_days():
    idx = pd.date_range("2025-01-01", periods=12)
    on = pd.Series([0] * 3 + [1] * 9, index=idx)  # only 3 days before the switch
    assert A.switch_effects(pd.Series(1.0, index=idx), on, window=5, min_days=5).empty


def test_regress_on_flag_recovers_exact_effect():
    idx = pd.date_range("2025-01-01", periods=70)
    on = pd.Series((np.arange(70) // 10) % 2, index=idx)
    y = 5 + 3 * on + 0.001 * np.sin(np.arange(70))
    r = A.regress_on_flag(y, on)
    assert r["coef"] == pytest.approx(3.0, abs=0.01)
    assert r["n"] == 70


def test_sign_test_p_values():
    assert A.sign_test_p(pd.Series([1, 2, 3, 4, 5])) == pytest.approx(0.0625)  # 2 * 0.5**5
    assert A.sign_test_p(pd.Series([1, -1])) == pytest.approx(1.0)
    assert np.isnan(A.sign_test_p(pd.Series([0.0])))


def test_period_means_blocks():
    idx = pd.date_range("2025-01-01", periods=6)
    on = pd.Series([1, 1, 0, 0, 0, 1], index=idx)
    y = pd.Series([2.0, 4.0, 1.0, 1.0, 4.0, 9.0], index=idx)
    p = A.period_means(y, on)
    assert p["mean"].tolist() == pytest.approx([3.0, 2.0, 9.0])
    assert p["days"].tolist() == [2, 3, 1]
    assert p["on"].tolist() == [1, 0, 1]


def test_shift_null_flags_a_perfect_effect():
    idx = pd.date_range("2025-01-01", periods=200)
    on = pd.Series(((np.arange(200) // 25) % 2), index=idx)
    y = pd.Series(10 + 5 * on, index=idx, dtype=float)
    r = A.shift_null(y, on, min_shift=10)
    assert r["coef"] == pytest.approx(5.0)
    # only the rotations that are whole cycles (multiples of 50 days) match exactly
    assert r["p_value"] < 0.05


# ------------------------------------------------------ realistic synthetic data sets
# Same shape as the real data: the real ON schedule, a slowly drifting rank that moves
# clicks, weekly seasonality and noise. The null has no ad effect; the positive has +50% (+25% sits at the edge of detectability).

REAL_ON = [("2025-05-18", "2025-06-10"), ("2025-09-01", "2025-12-21"), ("2026-04-16", "2026-09-15")]


def _realistic(seed, effect):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-05-18", "2026-09-27")
    on = pd.Series(0, index=idx)
    for a, b in REAL_ON:
        on[a:b] = 1
    n = len(idx)
    # slow drift in position: smoothed random walk around 8
    drift = pd.Series(rng.normal(0, 0.08, n)).cumsum().rolling(30, min_periods=1).mean().to_numpy()
    position = 8 + drift - drift.mean() + rng.normal(0, 0.3, n)
    dow = 1 + 0.1 * np.sin(2 * np.pi * idx.dayofweek / 7)
    base = 60 * np.exp(-(position - 8) * 0.3) * dow
    clicks = rng.poisson(base * (1 + effect * on.to_numpy()))
    return pd.Series(clicks.astype(float), index=idx), on


def test_realistic_null_rarely_rejects():
    rejections = [A.shift_null(*_realistic(seed, 0.0))["p_value"] < 0.05 for seed in range(20)]
    assert sum(rejections) <= 3  # nominal 5% of 20 = 1; allow sampling slack


def test_realistic_positive_is_detected_with_right_size():
    # A single draw's coefficient is pulled around by the drift (that confounding is the
    # point of the shift test), so check detection per draw and unbiasedness on average.
    ratios, detected = [], []
    for seed in range(20):
        y, on = _realistic(seed, 0.5)
        r = A.shift_null(y, on)
        ratios.append(r["coef"] / y[on == 0].mean())
        detected.append(r["p_value"] < 0.05)
    assert sum(detected) >= 16
    assert np.mean(ratios) == pytest.approx(0.5, abs=0.1)
