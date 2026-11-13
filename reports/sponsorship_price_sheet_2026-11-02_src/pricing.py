"""Pure helpers for the sponsorship price sheet: reach statistics and CPM arithmetic, plus the edition
classifier re-exported from newsletter_editions.py. No I/O here, so tests/test_sponsorship_price_sheet.py
can exercise everything with synthetic data. fetch_newsletter_stats.py and build.py are the only callers.
"""
from __future__ import annotations

import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# The edition classifier (same-day grouping, promo detection, regular-edition rules) is shared with the
# "Average Unique Opens Per Campaign" goal in data_layer.py; it lives in newsletter_editions.py at the
# repo root and is re-exported here for fetch_newsletter_stats.py and the tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from newsletter_editions import PROMO, group_editions, is_promo, regular_editions  # noqa: E402,F401


def summarize(values) -> dict:
    """n, median, mean, p25, p75, min, max of a list of counts (quartiles with the inclusive method)."""
    vals = sorted(int(v) for v in values)
    if not vals:
        return {"n": 0}
    if len(vals) >= 2:
        q = statistics.quantiles(vals, n=4, method="inclusive")  # never extrapolates beyond min/max
        p25, p75 = q[0], q[2]
    else:
        p25 = p75 = vals[0]
    return {"n": len(vals), "median": round(statistics.median(vals)), "mean": round(statistics.mean(vals)),
            "p25": round(p25), "p75": round(p75), "min": vals[0], "max": vals[-1]}


def by_month(editions: list[dict]) -> list[dict]:
    months: dict[str, list[int]] = defaultdict(list)
    for e in editions:
        months[e["date"][:7]].append(e["unique_opens"])
    return [{"month": m, **summarize(v)} for m, v in sorted(months.items())]


def editions_per_week(editions: list[dict]) -> float:
    weeks = {datetime.strptime(e["date"], "%Y-%m-%d").strftime("%G-%V") for e in editions}
    return round(len(editions) / len(weeks), 2) if weeks else 0.0


def cost(impressions: float, cpm: float, step: int = 1) -> int:
    """CPM arithmetic: impressions / 1,000 x cpm, rounded to `step` dollars (step=50 gives 'about $2,200')."""
    raw = impressions / 1000 * cpm
    return int(round(raw / step) * step)


def round_up(x: float, step: int) -> int:
    return int(math.ceil(x / step - 1e-9) * step)


def suggested_cap(typical_cost: float, headroom: float = 0.25, step: int = 500) -> int:
    """A cap a sponsor can set so the invoice never exceeds it: `headroom` above the typical cost, rounded
    up to `step`. 80,000 Hours chose $6,000 on a $4,500 to $5,000 estimate, which is this rule."""
    return round_up(typical_cost * (1 + headroom), step)


def package_reach(unit_reach: dict, counts: dict) -> int:
    """Impressions of a package: sum over channels of unit reach x how many placements of that channel."""
    return int(sum(unit_reach[k] * n for k, n in counts.items()))


def fmt_money(x: float) -> str:
    return f"${x:,.0f}"


def fmt_int(x: float) -> str:
    return f"{x:,.0f}"
