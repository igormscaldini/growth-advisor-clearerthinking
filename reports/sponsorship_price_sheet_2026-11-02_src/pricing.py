"""Pure helpers for the sponsorship price sheet: grouping beehiiv sends into editions, reach statistics
and CPM arithmetic. No I/O here, so tests/test_sponsorship_price_sheet.py can exercise everything with
synthetic data. fetch_newsletter_stats.py and build.py are the only callers.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from datetime import datetime

# Sends that are Clearer Thinking's own promotions (tool launches, workshops, coaching, the monthly
# debrief, book launch asks, tests). A sponsor box runs in the regular article and One Helpful Idea editions,
# not in these. Anchored at the start of the subject on purpose: "Debunking meditation myths (and a new tool
# for meditation)" is a regular article, "New Tool: Who attracts you?" is a launch blast.
PROMO = re.compile(
    r"^\s*(\[[^\]]*\]\s*)?(free tool|new tool|early access|you['\u2019]re invited|our most important ideas|"
    r"limited spots|a personal ask|what['\u2019]s next|stuck with|we['\u2019]re about to start|free live workshop|"
    r"missed our workshop|details about your workshop|career change workshop|quick note|igor testing|"
    r"\[(real )?test\]|\[regular\]|\[no html\]|\[fixed\])",
    re.I,
)


def group_editions(posts: list[dict], min_post_recipients: int = 20_000) -> list[dict]:
    """Group same-day sends (segment splits, A/B variants, re-sends) into one edition.

    beehiiv stores one edition as two or three posts when it is split by segment or variant, so counting
    posts understates both recipients and unique opens of the edition a sponsor box appears in. Test sends,
    workshop reminders and other posts under `min_post_recipients`, and our own promo blasts (PROMO), are
    dropped per post first, so a small promo sent the same day cannot swallow a real edition.
    Each post needs date (YYYY-MM-DD), recipients, unique_opens and subject.
    """
    by_day: dict[str, list[dict]] = defaultdict(list)
    for p in posts:
        if int(p.get("recipients") or 0) < min_post_recipients or is_promo(p.get("subject") or ""):
            continue
        by_day[p["date"]].append(p)
    out = []
    for day, ps in sorted(by_day.items()):
        recipients = sum(int(p.get("recipients") or 0) for p in ps)
        opens = sum(int(p.get("unique_opens") or 0) for p in ps)
        subjects = sorted({(p.get("subject") or "").strip() for p in ps if (p.get("subject") or "").strip()})
        out.append({
            "date": day,
            "weekday": datetime.strptime(day, "%Y-%m-%d").strftime("%a"),
            "posts": len(ps),
            "recipients": recipients,
            "unique_opens": opens,
            "open_rate": (opens / recipients) if recipients else 0.0,
            "subject": " | ".join(subjects),
        })
    return out


def is_promo(subject: str) -> bool:
    return bool(PROMO.search(subject or ""))


def regular_editions(editions: list[dict], min_recipients: int = 200_000, min_open_rate: float = 0.15,
                     until: str | None = None) -> list[dict]:
    """The editions a sponsor box would run in: an article or One Helpful Idea send to the engaged list
    (recipients >= min_recipients), with a normal open rate (a reactivation blast to dormant readers opens
    under 10%), not one of our own promos, and old enough for its opens to have accrued (`until`)."""
    out = []
    for e in editions:
        if until and e["date"] > until:
            continue
        if e["recipients"] < min_recipients or e["open_rate"] < min_open_rate or is_promo(e["subject"]):
            continue
        out.append(e)
    return out


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
