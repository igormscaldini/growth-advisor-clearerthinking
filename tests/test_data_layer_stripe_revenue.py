"""Stripe revenue bucketing (data_layer._charge_bucket and the functions built on it).

Stripe is replaced by a fake client injected as the `stripe_client` module, so these run without
credentials. Every expected number is worked out by hand in the comments.
"""
import sys
import types
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

import data_layer as dl

SPONSOR_ID = next(iter(dl.SPONSORSHIP_CHARGE_IDS))


def charge(amount, *, id="ch_x", status="succeeded", refunded=0, description="", invoice=None, day="2026-09-01"):
    created = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()) + 3600
    return SimpleNamespace(
        id=id, amount=amount, status=status, amount_refunded=refunded, description=description,
        invoice=invoice, created=created,
    )


class _Listing:
    def __init__(self, items):
        self._items = items

    def auto_paging_iter(self):
        return iter(self._items)


def fake_stripe(monkeypatch, charges, invoices=()):
    client = SimpleNamespace(
        Charge=SimpleNamespace(list=lambda **kw: _Listing(charges)),
        Invoice=SimpleNamespace(list=lambda **kw: _Listing(invoices)),
    )
    monkeypatch.setitem(sys.modules, "stripe_client", types.SimpleNamespace(get_client=lambda: client))
    for fn in (dl.stripe_revenue_by_category, dl.stripe_revenue_by_category_daily, dl.stripe_metrics):
        fn.clear()  # streamlit cache keys on the dates only, so drop anything from earlier tests


# --- _charge_bucket: one rule per case -------------------------------------------------------

def test_bucket_subscription_by_invoice_or_description():
    assert dl._charge_bucket(charge(2000, invoice="in_1")) == ("subscriptions", 2000)
    assert dl._charge_bucket(charge(900, description="Subscription update")) == ("subscriptions", 900)
    assert dl._charge_bucket(charge(900, description="  subscription creation")) == ("subscriptions", 900)


def test_bucket_pdf_cognitive_other_by_amount():
    assert dl._charge_bucket(charge(900)) == ("pdf", 900)
    assert dl._charge_bucket(charge(3500)) == ("cognitive", 3500)
    assert dl._charge_bucket(charge(1750)) == ("cognitive", 1750)
    assert dl._charge_bucket(charge(10000)) == ("other", 10000)
    assert dl._charge_bucket(charge(901)) == ("other", 901)


def test_bucket_is_net_of_refunds_and_skips_fully_refunded():
    assert dl._charge_bucket(charge(5000, refunded=1000)) == ("other", 4000)
    assert dl._charge_bucket(charge(900, refunded=900)) is None
    assert dl._charge_bucket(charge(900, refunded=1200)) is None


def test_bucket_skips_failed_and_sponsorship_charges():
    assert dl._charge_bucket(charge(900, status="failed")) is None
    assert dl._charge_bucket(charge(900, status="pending")) is None
    assert dl._charge_bucket(charge(150000, id=SPONSOR_ID)) is None
    # same amount, any other id: an ordinary one-off payment
    assert dl._charge_bucket(charge(150000, id="ch_not_a_sponsor")) == ("other", 150000)


def test_bucket_tolerates_missing_fields():
    bare = SimpleNamespace(id="ch_b", status="succeeded", amount=None)
    assert dl._charge_bucket(bare) is None  # amount None -> net 0 -> skipped
    bare = SimpleNamespace(id="ch_b", status="succeeded", amount=1234)
    assert dl._charge_bucket(bare) == ("other", 1234)


# --- the window and daily functions on a small hand-built ledger -----------------------------

LEDGER = [
    charge(2000, id="c1", invoice="in_1", day="2026-09-01"),                 # subs 20.00
    charge(900, id="c2", description="Subscription update", day="2026-09-01"),  # subs 9.00
    charge(900, id="c3", day="2026-09-01"),                                  # pdf 9.00
    charge(3500, id="c4", day="2026-09-02"),                                 # cognitive 35.00
    charge(1750, id="c5", day="2026-09-02"),                                 # cognitive 17.50
    charge(10000, id="c6", day="2026-09-02"),                                # other 100.00
    charge(5000, id="c7", refunded=1000, day="2026-09-03"),                  # other 40.00
    charge(150000, id=SPONSOR_ID, day="2026-09-03"),                         # sponsorship: skipped
    charge(900, id="c8", status="failed", day="2026-09-03"),                 # failed: skipped
    charge(900, id="c9", refunded=900, day="2026-09-03"),                    # fully refunded: skipped
]


def test_revenue_by_category_window(monkeypatch):
    fake_stripe(monkeypatch, LEDGER)
    out = dl.stripe_revenue_by_category(date(2026, 9, 1), date(2026, 9, 3))
    assert out == {"subscriptions": 29.0, "pdf": 9.0, "cognitive": 52.5, "other": 140.0}


def test_revenue_by_category_daily_matches_window_and_zero_fills(monkeypatch):
    fake_stripe(monkeypatch, LEDGER)
    rows = dl.stripe_revenue_by_category_daily(date(2026, 9, 1), date(2026, 9, 4))
    assert [r["date"] for r in rows] == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
    assert rows[0] == {"date": "2026-09-01", "subscriptions": 29.0, "pdf": 9.0, "cognitive": 0.0, "other": 0.0}
    assert rows[1] == {"date": "2026-09-02", "subscriptions": 0.0, "pdf": 0.0, "cognitive": 52.5, "other": 100.0}
    assert rows[2] == {"date": "2026-09-03", "subscriptions": 0.0, "pdf": 0.0, "cognitive": 0.0, "other": 40.0}
    assert rows[3] == {"date": "2026-09-04", "subscriptions": 0.0, "pdf": 0.0, "cognitive": 0.0, "other": 0.0}
    # the daily series sums to the window totals
    window = dl.stripe_revenue_by_category(date(2026, 9, 1), date(2026, 9, 4))
    for cat in dl.REVENUE_CATEGORIES:
        assert sum(r[cat] for r in rows) == pytest.approx(window[cat])


def test_stripe_metrics_gross_excludes_sponsorship(monkeypatch):
    # succeeded charges: c1 20 + c2 9 + c3 9 + c4 35 + c5 17.5 + c6 100 + c7 50 + c9 9 = 249.50 gross
    # (the $1,500 sponsorship and the failed charge are out); refunds: c7 10 + c9 9 = 19.00
    fake_stripe(monkeypatch, LEDGER)
    m = dl.stripe_metrics(date(2026, 9, 1), date(2026, 9, 3))
    assert m["gross_usd"] == pytest.approx(249.50)
    assert m["refunded_usd"] == pytest.approx(19.00)
    assert m["revenue_usd"] == pytest.approx(230.50)
    by_day = {r["date"]: r["revenue"] for r in m["daily"]}
    assert by_day == {"2026-09-01": pytest.approx(38.0), "2026-09-02": pytest.approx(152.5), "2026-09-03": pytest.approx(40.0)}
