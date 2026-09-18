"""CT+ churn per tier, straight from Stripe.

    python ctplus_churn.py            # all tiers, 30-day cutoff
    python ctplus_churn.py --min-days 0

Excludes the team's test subscriptions (same-day cancel), staff accounts and
`incomplete_expired` subs that never paid. The churn maths lives in churn.py, which
is unit tested; this file only fetches and filters. See churn.py for why the rate is
exposure based rather than cancellations-over-subscribers.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from dotenv import load_dotenv

from churn import Spell, calendar_month_churn, monthly_churn

load_dotenv()

from stripe_client import get_client  # noqa: E402

TIERS = {
    "Navigator ($99/$179)": ["price_1SQvhxAoBs2tgN9p7Hp5KuC0",
                             "price_1TC1fNAoBs2tgN9poVlnyrY7"],
    "Explorer ($29)": ["price_1SQvihAoBs2tgN9pG94Fk24f"],
    "Supporter ($9)": ["price_1SQvk9AoBs2tgN9pW2ZlZEDG"],
}
# Igor's and Maria Belen's own subscriptions, used to test the payment flow.
STAFF_EMAILS = {
    "igormscaldini@gmail.com", "igor@positly.com", "igor@clearerthinking.org",
    "bvethnag4q@dev.nondon.store", "bogon28383@homuno.com", "b.cobeta@gmail.com",
}


def _g(obj, key, default=None):
    """Stripe objects raise KeyError instead of returning None for absent keys."""
    try:
        value = obj[key]
    except (KeyError, TypeError):
        return default
    return default if value is None else value


def _date(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).date() if epoch else None


def fetch_tier(stripe, price_ids: list[str]) -> list[dict]:
    """Every subscription ever created on these prices, deduped."""
    rows, seen = [], set()
    for price_id in price_ids:
        for sub in stripe.Subscription.list(price=price_id, status="all", limit=100,
                                            expand=["data.customer"]).auto_paging_iter():
            if sub["id"] in seen:
                continue
            seen.add(sub["id"])
            customer = _g(sub, "customer") or {}
            rows.append({
                "id": sub["id"],
                "status": sub["status"],
                "name": (_g(customer, "name") or "").strip(),
                "email": (_g(customer, "email") or "").strip().lower(),
                "start": _date(_g(sub, "start_date")),
                "ended": _date(_g(sub, "ended_at")),
                "reason": _g(_g(sub, "cancellation_details") or {}, "reason") or "",
            })
    return rows


def drop_tests(rows: list[dict], today: dt.date) -> tuple[list[dict], dict]:
    """Remove staff subs, never-paid subs and the same-day test subscriptions."""
    kept, dropped = [], {"staff": 0, "incomplete_expired": 0, "same_day_test": 0}
    for row in rows:
        if row["email"] in STAFF_EMAILS:
            dropped["staff"] += 1
        elif row["status"] == "incomplete_expired":
            dropped["incomplete_expired"] += 1
        elif row["ended"] is not None and (row["ended"] - row["start"]).days <= 1:
            dropped["same_day_test"] += 1
        else:
            kept.append(row)
    return kept, dropped


def report(label: str, rows: list[dict], today: dt.date, min_days: int) -> None:
    spells = [Spell(r["start"], r["ended"]) for r in rows]
    result = monthly_churn(spells, today=today, min_days=min_days)
    involuntary = sum(1 for r in rows
                      if r["ended"] and (r["ended"] - r["start"]).days > min_days
                      and r["reason"] == "payment_failed")
    lo, hi = result.ci95

    print(f"\n### {label}")
    print(f"  real subscriptions ever            : {len(rows)}")
    print(f"  cancelled within {min_days} days (excluded) : {result.excluded_early_cancels}")
    print(f"  active but under {min_days} days (excluded) : {result.excluded_too_young}")
    print(f"  in the risk set                    : {result.at_risk}")
    print(f"  churn events                       : {result.events}"
          f"  ({involuntary} involuntary)")
    print(f"  exposure                           : {result.exposure_months:.1f} subscriber-months")
    print(f"  MONTHLY CHURN                      : {result.monthly_rate * 100:.1f}%"
          f"   95% CI {lo * 100:.0f}-{hi * 100:.0f}%")
    if result.events:
        voluntary = (result.events - involuntary) / result.exposure_months
        print(f"  voluntary only                     : {voluntary * 100:.1f}%")
    print(f"  median lifetime past day {min_days}        : "
          f"{result.median_lifetime_months:.1f} months")

    months = [(2026, m) for m in range(1, today.month)]
    lost, base = calendar_month_churn(spells, months, min_days=min_days)
    if base:
        print(f"  cross-check (calendar months)      : {lost}/{base} = {lost / base * 100:.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-days", type=int, default=30,
                    help="ignore subscriptions that did not survive this long (default 30)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for reproducible runs")
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    stripe = get_client()
    everything = []
    for label, price_ids in TIERS.items():
        rows, dropped = drop_tests(fetch_tier(stripe, price_ids), today)
        print(f"\n{label}: dropped {dropped}", file=sys.stderr)
        report(label, rows, today, args.min_days)
        everything.extend(rows)

    seen, combined = set(), []
    for row in everything:
        if row["id"] not in seen:
            seen.add(row["id"])
            combined.append(row)
    print("\n" + "=" * 60)
    report("ALL CT+ TIERS COMBINED", combined, today, args.min_days)


if __name__ == "__main__":
    main()
