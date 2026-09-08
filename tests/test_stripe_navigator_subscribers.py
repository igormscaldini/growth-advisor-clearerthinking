import csv

import stripe_navigator_subscribers as ns


def test_status_label_humanises_stripe_statuses():
    assert ns.status_label("active") == "Active"
    assert ns.status_label("canceled") == "Canceled"
    assert ns.status_label("past_due") == "Past due"
    assert ns.status_label("incomplete_expired") == "Incomplete expired"


def test_status_label_flags_active_subs_that_are_winding_down():
    assert ns.status_label("active", True) == "Active (cancels at period end)"
    # cancel_at_period_end is meaningless once the sub has actually ended
    assert ns.status_label("canceled", True) == "Canceled"


def test_build_row_maps_stripe_fields_to_columns():
    # 1767225600 == 2026-01-01T00:00:00Z, worked out from the epoch by hand
    sub = {"status": "active", "cancel_at_period_end": False, "created": 1767225600}
    cust = {"name": "Ada Lovelace", "email": "ada@example.com"}
    assert ns.build_row(sub, cust, "Navigator ($99/mo)") == {
        "Name": "Ada Lovelace",
        "Email": "ada@example.com",
        "Status": "Active",
        "Created at": "2026-01-01T00:00:00Z",
        "Plan": "Navigator ($99/mo)",
    }


def test_build_row_tolerates_missing_name_and_email():
    sub = {"status": "canceled", "cancel_at_period_end": False, "created": 1767225600}
    row = ns.build_row(sub, {}, "Navigator + Coaching ($179/mo)")
    assert row["Name"] == "" and row["Email"] == ""
    assert row["Status"] == "Canceled"


def test_build_row_timestamp_is_utc_not_local():
    # 1767312000 is exactly 24h after 2026-01-01T00:00:00Z
    sub = {"status": "active", "cancel_at_period_end": False, "created": 1767312000}
    assert ns.build_row(sub, {}, "p")["Created at"] == "2026-01-02T00:00:00Z"


def test_write_csv_round_trips_every_column(tmp_path):
    rows = [
        {"Name": "A, with comma", "Email": "a@x.com", "Status": "Active",
         "Created at": "2026-01-01T00:00:00Z", "Plan": "Navigator ($99/mo)"},
        {"Name": "B", "Email": "b@x.com", "Status": "Canceled",
         "Created at": "2026-02-01T00:00:00Z", "Plan": "Navigator + Coaching ($179/mo)"},
    ]
    path = ns.write_csv(rows, tmp_path / "sub" / "out.csv")
    with path.open(encoding="utf-8") as f:
        back = list(csv.DictReader(f))
    assert back == rows
    assert list(back[0].keys()) == ns.COLUMNS
