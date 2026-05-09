"""Sanity-check report: confirm Stripe access works end-to-end."""
from collections import Counter
from datetime import datetime, timedelta, timezone

from stripe_client import get_client

# Cap iterations on the sanity check so we don't pull tens of thousands of objects.
MAX_ITEMS = 2000


def _to_monthly(unit_amount: int, interval: str, interval_count: int, quantity: int) -> float:
    """Normalize a Stripe price + interval to a monthly USD figure."""
    months_in_period = {"day": 1 / 30.4, "week": 1 / 4.33, "month": 1, "year": 12}.get(interval, 1)
    period_months = months_in_period * (interval_count or 1)
    if period_months == 0:
        return 0.0
    return (unit_amount / 100.0) * quantity / period_months


def main() -> None:
    s = get_client()
    now = datetime.now(timezone.utc)
    thirty_days_ago = int((now - timedelta(days=30)).timestamp())

    # --- Active subscriptions / MRR ---
    print("--- Active subscriptions ---")
    active_count = 0
    mrr = 0.0
    product_subs: Counter = Counter()  # keyed by product_id
    for i, sub in enumerate(
        s.Subscription.list(status="active", limit=100).auto_paging_iter()
    ):
        if i >= MAX_ITEMS:
            print(f"  (capped at {MAX_ITEMS}; there may be more)")
            break
        active_count += 1
        for item in sub["items"]["data"]:
            price = item.price
            recurring = getattr(price, "recurring", None)
            interval = recurring.interval if recurring else "month"
            interval_count = recurring.interval_count if recurring else 1
            mrr += _to_monthly(
                price.unit_amount or 0,
                interval,
                interval_count,
                item.quantity or 1,
            )
            product_subs[price.product] += 1

    print(f"  Active subscriptions: {active_count}")
    print(f"  Estimated MRR:        ${mrr:,.2f}")

    if product_subs:
        # Resolve product names lazily for just the top 5
        top = product_subs.most_common(5)
        names = {pid: s.Product.retrieve(pid)["name"] for pid, _ in top if pid}
        print("\n  Top 5 products by active subs:")
        for pid, count in top:
            print(f"    {count:>5}  {names.get(pid, pid)}")

    # --- New customers (last 30 days) ---
    new_customers = 0
    for i, _ in enumerate(s.Customer.list(created={"gte": thirty_days_ago}, limit=100).auto_paging_iter()):
        if i >= MAX_ITEMS:
            break
        new_customers += 1
    print(f"\n--- New customers (last 30d): {new_customers} ---")

    # --- Successful charges (last 30 days) ---
    print("\n--- Charges (last 30d) ---")
    charge_count = 0
    gross_cents = 0
    refund_cents = 0
    for i, ch in enumerate(s.Charge.list(created={"gte": thirty_days_ago}, limit=100).auto_paging_iter()):
        if i >= MAX_ITEMS:
            print(f"  (capped at {MAX_ITEMS})")
            break
        if ch.status != "succeeded":
            continue
        charge_count += 1
        gross_cents += ch.amount
        refund_cents += ch.amount_refunded or 0

    print(f"  Successful charges:   {charge_count}")
    print(f"  Gross:                ${gross_cents / 100:,.2f}")
    print(f"  Refunded:             ${refund_cents / 100:,.2f}")
    print(f"  Net:                  ${(gross_cents - refund_cents) / 100:,.2f}")

    # --- Churn: subs canceled in last 30 days ---
    canceled = 0
    for i, _ in enumerate(
        s.Subscription.list(status="canceled", limit=100).auto_paging_iter()
    ):
        if i >= MAX_ITEMS:
            break
        # API doesn't filter "canceled at" via list; we check ended_at after the fact
        # Reset loop body — we want a quick estimate, so we keep it simple:
        canceled += 1
    # Better: filter list by `canceled_at` via search API for accurate 30d window
    print(f"\n--- Total canceled subscriptions (all-time, capped {MAX_ITEMS}): {canceled} ---")
    print("  (For 30-day churn we'll use the Search API in a follow-up.)")

    print("\nStripe connection OK.")


if __name__ == "__main__":
    main()
