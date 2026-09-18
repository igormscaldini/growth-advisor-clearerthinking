"""Subscription churn measured as left-truncated exposure.

Why not "cancellations this month / subscribers at the start of the month": with a
base this small (tens of subscribers) that estimator swings wildly month to month and
silently mixes people who are one day old with people who are one year old.

The estimator here counts, for a set of subscription spells:

  * exposure: for each spell, the days it survived BEYOND `min_days`, capped at today
  * events:   spells that ended after `min_days`

and divides events by exposure expressed in months. Spells that never got past
`min_days` contribute nothing at all, neither an event nor a day of exposure. That is
what "ignore people who cancelled in their first month" has to mean if the rate is to
stay honest: you cannot drop their cancellations while keeping everyone else's first
month in the denominator.

Note that excluding early cancellations usually RAISES the measured rate, because the
first month is the calmest one (people rarely quit days after paying), so removing it
removes mostly event-free exposure.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

DAYS_PER_MONTH = 30.4375  # 365.25 / 12


@dataclass(frozen=True)
class Spell:
    """One subscription: when it started and, if it is over, when it ended."""
    start: dt.date
    ended: Optional[dt.date] = None

    def tenure_days(self, today: dt.date) -> int:
        return ((self.ended or today) - self.start).days


@dataclass(frozen=True)
class ChurnResult:
    events: int
    exposure_months: float
    at_risk: int
    excluded_early_cancels: int
    excluded_too_young: int

    @property
    def monthly_rate(self) -> float:
        return self.events / self.exposure_months if self.exposure_months else float("nan")

    @property
    def ci95(self) -> tuple[float, float]:
        """Poisson (Byar) interval on the event count, expressed as a monthly rate."""
        if not self.exposure_months:
            return (float("nan"), float("nan"))
        k = self.events
        lo = 0.0 if k == 0 else k * (1 - 1 / (9 * k) - 1.96 / (3 * math.sqrt(k))) ** 3
        hi = (k + 1) * (1 - 1 / (9 * (k + 1)) + 1.96 / (3 * math.sqrt(k + 1))) ** 3
        return (lo / self.exposure_months, hi / self.exposure_months)

    @property
    def median_lifetime_months(self) -> float:
        """Median remaining lifetime past min_days, assuming a constant hazard."""
        r = self.monthly_rate
        if not 0 < r < 1:
            return float("inf") if r == 0 else float("nan")
        return math.log(2) / -math.log(1 - r)


def monthly_churn(spells: Iterable[Spell], today: dt.date, min_days: int = 30) -> ChurnResult:
    """Monthly churn among spells that survived longer than `min_days`."""
    events = exposure_days = at_risk = early = young = 0
    for sp in spells:
        if sp.ended is not None and sp.ended < sp.start:
            raise ValueError(f"spell ends before it starts: {sp}")
        tenure = sp.tenure_days(today)
        if tenure <= min_days:
            if sp.ended is None:
                young += 1
            else:
                early += 1
            continue
        at_risk += 1
        exposure_days += tenure - min_days
        if sp.ended is not None:
            events += 1
    return ChurnResult(
        events=events,
        exposure_months=exposure_days / DAYS_PER_MONTH,
        at_risk=at_risk,
        excluded_early_cancels=early,
        excluded_too_young=young,
    )


def calendar_month_churn(spells: Sequence[Spell], months: Sequence[tuple[int, int]],
                         min_days: int = 30) -> tuple[int, int]:
    """Independent cross-check: (cancellations, subscriber-months) over calendar months.

    A spell counts toward a month if it was already past `min_days` on the 1st and had
    not ended before the 1st. Returns raw counts so the caller can pool them.
    """
    lost = base = 0
    for year, month in months:
        first = dt.date(year, month, 1)
        nxt = dt.date(year + (month == 12), (month % 12) + 1, 1)
        for sp in spells:
            if sp.start + dt.timedelta(days=min_days) > first:
                continue
            if sp.ended is not None and sp.ended < first:
                continue
            base += 1
            if sp.ended is not None and first <= sp.ended < nxt:
                lost += 1
    return lost, base
