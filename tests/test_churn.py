"""Tests for churn.py.

The first group uses datasets small enough to work the answer out by hand; the second
group uses larger synthetic sets built to be a known null and a known positive.
"""
import datetime as dt

import pytest

from churn import DAYS_PER_MONTH, Spell, calendar_month_churn, monthly_churn

JAN1 = dt.date(2026, 1, 1)


def d(base, days):
    return base + dt.timedelta(days=days)


# --------------------------------------------------------------------------
# Hand-worked cases
# --------------------------------------------------------------------------

def test_two_spells_worked_by_hand():
    """A churns on day 60, B is still alive on day 90. Both started Jan 1, 2026.

    Past day 30, A contributed 30 days and one event, B contributed 60 days and none.
    So 1 event over 90 days = 90/30.4375 = 2.956878 months -> 0.338195 per month.
    """
    spells = [Spell(JAN1, d(JAN1, 60)), Spell(JAN1)]
    r = monthly_churn(spells, today=d(JAN1, 90))
    assert r.events == 1
    assert r.at_risk == 2
    assert r.exposure_months == pytest.approx(90 / DAYS_PER_MONTH)
    assert r.monthly_rate == pytest.approx(0.3381954, abs=1e-6)


def test_early_cancels_and_newcomers_contribute_nothing():
    """Adding a day-10 cancellation and a 12-day-old subscriber cannot move the rate."""
    base = [Spell(JAN1, d(JAN1, 60)), Spell(JAN1)]
    noise = [Spell(d(JAN1, 74), d(JAN1, 84)), Spell(d(JAN1, 78))]
    today = d(JAN1, 90)
    plain = monthly_churn(base, today=today)
    noisy = monthly_churn(base + noise, today=today)
    assert noisy.monthly_rate == pytest.approx(plain.monthly_rate)
    assert noisy.exposure_months == pytest.approx(plain.exposure_months)
    assert noisy.excluded_early_cancels == 1
    assert noisy.excluded_too_young == 1
    assert noisy.at_risk == 2


def test_boundary_at_exactly_min_days():
    """Cancelling on day 30 is "within 30 days" and drops out; day 31 counts."""
    on_30 = monthly_churn([Spell(JAN1, d(JAN1, 30))], today=d(JAN1, 90))
    assert on_30.events == 0 and on_30.at_risk == 0
    assert on_30.excluded_early_cancels == 1

    on_31 = monthly_churn([Spell(JAN1, d(JAN1, 31))], today=d(JAN1, 90))
    assert on_31.events == 1 and on_31.at_risk == 1
    assert on_31.exposure_months == pytest.approx(1 / DAYS_PER_MONTH)


def test_no_churn_gives_zero_rate_and_zero_lower_bound():
    r = monthly_churn([Spell(JAN1), Spell(JAN1)], today=d(JAN1, 365))
    assert r.events == 0
    assert r.monthly_rate == 0.0
    assert r.ci95[0] == 0.0
    assert r.ci95[1] > 0
    assert r.median_lifetime_months == float("inf")


def test_confidence_interval_brackets_the_estimate():
    r = monthly_churn([Spell(JAN1, d(JAN1, 60)), Spell(JAN1)], today=d(JAN1, 90))
    lo, hi = r.ci95
    assert lo < r.monthly_rate < hi


def test_median_lifetime_matches_constant_hazard_formula():
    """At 50% monthly churn the median remaining lifetime is exactly one month."""
    # One spell alive for 30 days past the cutoff, one event in that window.
    r = monthly_churn([Spell(JAN1, d(JAN1, 30 + round(2 * DAYS_PER_MONTH)))],
                      today=d(JAN1, 400))
    assert r.monthly_rate == pytest.approx(0.5, abs=0.01)
    assert r.median_lifetime_months == pytest.approx(1.0, abs=0.05)


def test_calendar_cross_check_worked_by_hand():
    """A runs Jan 1 to Apr 10, B is open-ended. Checking March and April.

    March 1: both are past day 30 and alive -> base 2, nobody lost.
    April 1: both -> base 2, A ends Apr 10 -> 1 lost. Totals: 1 of 4.
    """
    spells = [Spell(JAN1, dt.date(2026, 4, 10)), Spell(JAN1)]
    assert calendar_month_churn(spells, [(2026, 3), (2026, 4)]) == (1, 4)


def test_spell_ending_before_it_starts_is_rejected():
    with pytest.raises(ValueError):
        monthly_churn([Spell(JAN1, d(JAN1, -5))], today=d(JAN1, 90))


# --------------------------------------------------------------------------
# Synthetic datasets shaped like the real one: a known null and a known positive
# --------------------------------------------------------------------------

def test_null_dataset_nobody_ever_leaves():
    spells = [Spell(d(JAN1, i * 3)) for i in range(20)]
    r = monthly_churn(spells, today=d(JAN1, 300))
    assert r.at_risk == 20
    assert r.events == 0
    assert r.monthly_rate == 0.0


def test_positive_dataset_every_subscriber_leaves_on_day_120():
    """12 spells, each 90 days of exposure past the cutoff and one event.

    12 events / (1080/30.4375 = 35.4846 months) = 0.338195 per month, the same
    hazard as the hand-worked two-spell case.
    """
    spells = [Spell(d(JAN1, i), d(JAN1, i + 120)) for i in range(12)]
    r = monthly_churn(spells, today=d(JAN1, 400))
    assert r.at_risk == 12
    assert r.events == 12
    assert r.exposure_months == pytest.approx(1080 / DAYS_PER_MONTH)
    assert r.monthly_rate == pytest.approx(0.3381954, abs=1e-6)


def test_two_methods_agree_on_a_clean_synthetic_cohort():
    """Exposure and calendar-month methods should land close on the same data."""
    spells = [Spell(JAN1, d(JAN1, 120)) for _ in range(6)] + [Spell(JAN1) for _ in range(6)]
    exposure = monthly_churn(spells, today=dt.date(2026, 7, 1)).monthly_rate
    lost, base = calendar_month_churn(spells, [(2026, m) for m in range(3, 7)])
    assert lost / base == pytest.approx(exposure, abs=0.05)


def test_excluding_early_cancels_raises_the_rate_when_month_one_is_calm():
    """The counter-intuitive property the module docstring warns about."""
    spells = [Spell(JAN1, d(JAN1, 120)) for _ in range(5)] + [Spell(JAN1) for _ in range(5)]
    today = d(JAN1, 200)
    with_cutoff = monthly_churn(spells, today=today, min_days=30).monthly_rate
    no_cutoff = monthly_churn(spells, today=today, min_days=0).monthly_rate
    assert with_cutoff > no_cutoff
