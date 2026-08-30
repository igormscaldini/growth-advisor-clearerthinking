"""Weekly Stripe cancellations email for Clearer Thinking.

Every Friday this pulls every `customer.subscription.deleted` event from the past 7 days,
looks up who cancelled, which product, and why (Stripe's Customer Portal collects a
cancellation reason, but it's only populated when the customer cancels through the
self-serve portal — cancellations made directly in the Dashboard/API show no reason),
and emails the list via the Gmail API (SMTP fallback locally).

Run locally:   .venv/bin/python stripe_cancellations_report.py --dry-run   # print, don't send
               .venv/bin/python stripe_cancellations_report.py             # send for real
On CI:         .github/workflows/stripe-cancellations-email.yml (Fridays 11:10 UTC = 08:10 BRT)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent


def _materialize_ci_secrets() -> None:
    """On CI the OAuth JSON blobs arrive as env vars; write them where the clients expect."""
    blobs = {
        "OAUTH_CLIENT_JSON": ROOT / "secrets" / "oauth-client.json",
        "GOOGLE_TOKEN_JSON": ROOT / "secrets" / "ga4-token.json",
    }
    for env_var, target in blobs.items():
        blob = os.environ.get(env_var, "").strip()
        if not blob:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blob)


load_dotenv()
_materialize_ci_secrets()

import email_transport  # noqa: E402
from stripe_client import get_client  # noqa: E402

EMAIL_TO = os.getenv("ADVISOR_EMAIL_TO") or email_transport.EMAIL_FROM

FEEDBACK_LABELS = {
    "too_expensive": "too expensive",
    "switched_service": "switched to a different service",
    "unused": "wasn't using it",
    "customer_service": "customer service",
    "low_quality": "low quality",
    "missing_features": "missing features",
    "too_complex": "too complex",
    "other": "other",
}


def _product_name(stripe, subscription: dict) -> str:
    try:
        item = subscription["items"]["data"][0]
        price = stripe.Price.retrieve(item["price"]["id"], expand=["product"])
        return price["product"]["name"]
    except Exception:  # noqa: BLE001
        return "(unknown product)"


def _customer_label(stripe, customer_id: str) -> str:
    try:
        c = stripe.Customer.retrieve(customer_id)
        name = c["name"]
        email = c["email"]
        if name and email:
            return f"{name} <{email}>"
        return email or name or customer_id
    except Exception:  # noqa: BLE001
        return customer_id


def gather_cancellations(start: datetime, end: datetime) -> list[dict]:
    """Every subscription that fired `customer.subscription.deleted` in [start, end)."""
    stripe = get_client()
    rows = []
    events = stripe.Event.list(
        type="customer.subscription.deleted",
        created={"gte": int(start.timestamp()), "lt": int(end.timestamp())},
        limit=100,
    )
    for event in events.auto_paging_iter():
        sub = event["data"]["object"]
        details = sub["cancellation_details"] or {}
        mechanism = details["reason"] if details else None  # how it was cancelled
        feedback = details["feedback"] if details else None  # customer's stated why (Portal only)
        comment = details["comment"] if details else None

        reason_bits = []
        if feedback:
            reason_bits.append(FEEDBACK_LABELS.get(feedback, feedback))
        if comment:
            reason_bits.append(f'"{comment}"')
        if not reason_bits:
            # No customer-given feedback — fall back to *how* it was cancelled, when that's informative.
            if mechanism == "payment_failed":
                reason_bits.append("payment failed (no feedback given)")
            elif mechanism == "payment_disputed":
                reason_bits.append("payment disputed/charged back")
            else:
                reason_bits.append("no reason given")
        reason = " — ".join(reason_bits)

        canceled_at = sub["canceled_at"] or event["created"]
        rows.append({
            "customer": _customer_label(stripe, sub["customer"]),
            "product": _product_name(stripe, sub),
            "canceled_at": datetime.fromtimestamp(canceled_at, tz=timezone.utc),
            "reason": reason,
        })
    rows.sort(key=lambda r: r["canceled_at"])
    return rows


def build_email(start: datetime, end: datetime, rows: list[dict]) -> tuple[str, str]:
    period = f"{start.strftime('%b %-d')}–{end.strftime('%b %-d, %Y')}"
    subject = f"Stripe cancellations, {period} ({len(rows)})"

    if not rows:
        body = f"No subscriptions were cancelled between {period}."
        return subject, body

    lines = [f"{len(rows)} subscription(s) cancelled between {period}:\n"]
    for r in rows:
        date_str = r["canceled_at"].strftime("%a %b %-d")
        lines.append(f"- {r['customer']} — {r['product']} — cancelled {date_str} — reason: {r['reason']}")
    body = "\n".join(lines)
    return subject, body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print the email instead of sending it")
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    try:
        rows = gather_cancellations(start, end)
    except Exception as e:  # noqa: BLE001
        reason = f"Stripe query failed: {type(e).__name__}: {e}"
        print(f"[error] {reason}", file=sys.stderr)
        if args.dry_run:
            raise
        if not email_transport.slack_fallback(reason, "Weekly Stripe cancellations report",
                                               "Check STRIPE_SECRET_KEY in .env and the GitHub secret."):
            raise
        return

    subject, body = build_email(start, end, rows)

    if args.dry_run:
        print(f"Subject: {subject}\n\n{body}")
        return

    try:
        email_transport.send_email(subject, body, EMAIL_TO, header_tag="stripe-cancellations")
        print(f"Sent: {subject}")
    except Exception as e:  # noqa: BLE001
        reason = f"{type(e).__name__}: {e}"
        print(f"[error] send failed: {reason}", file=sys.stderr)
        if not email_transport.slack_fallback(reason, "Weekly Stripe cancellations report",
                                               email_transport.TRANSPORT_FIX):
            raise


if __name__ == "__main__":
    main()
