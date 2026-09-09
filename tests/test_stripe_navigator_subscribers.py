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
    sub = {"status": "active", "cancel_at_period_end": False, "created": 1767225600,
           "id": "sub_ada"}
    cust = {"name": "Ada Lovelace", "email": "ada@example.com"}
    assert ns.build_row(sub, cust, "Navigator ($99/mo)") == {
        "Name": "Ada Lovelace",
        "Email": "ada@example.com",
        "Status": "Active",
        "Created at": "2026-01-01T00:00:00Z",
        "Plan": "Navigator ($99/mo)",
        "Subscription ID": "sub_ada",
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
         "Created at": "2026-01-01T00:00:00Z", "Plan": "Navigator ($99/mo)",
         "Subscription ID": "sub_a"},
        {"Name": "B", "Email": "b@x.com", "Status": "Canceled",
         "Created at": "2026-02-01T00:00:00Z", "Plan": "Navigator + Coaching ($179/mo)",
         "Subscription ID": "sub_b"},
    ]
    path = ns.write_csv(rows, tmp_path / "sub" / "out.csv")
    with path.open(encoding="utf-8") as f:
        back = list(csv.DictReader(f))
    assert back == rows
    assert list(back[0].keys()) == ns.COLUMNS


# --- Google Sheet upsert planning -------------------------------------------------
# COLUMNS is [Name, Email, Status, Created at, Plan, Subscription ID].

def _row(name, email, status, created, plan, sub_id):
    return dict(zip(ns.COLUMNS, [name, email, status, created, plan, sub_id]))


HEADER = list(ns.COLUMNS)
ALICE = ["Alice", "a@x.com", "Active", "2026-01-02T00:00:00Z", "Navigator ($99/mo)", "sub_A"]
BOB = ["Bob", "b@x.com", "Active", "2026-01-01T00:00:00Z", "Navigator ($99/mo)", "sub_B"]


def test_plan_sheet_sync_no_changes_means_no_writes():
    updates, inserts = ns.plan_sheet_sync([HEADER, ALICE, BOB],
                                          [_row(*ALICE), _row(*BOB)])
    assert updates == []
    assert inserts == []


def test_plan_sheet_sync_detects_a_changed_status_on_the_right_row():
    # Bob cancels. He sits on sheet row 3 (header is row 1, Alice row 2).
    cancelled_bob = list(BOB)
    cancelled_bob[2] = "Canceled"
    updates, inserts = ns.plan_sheet_sync([HEADER, ALICE, BOB],
                                          [_row(*ALICE), _row(*cancelled_bob)])
    assert inserts == []
    assert updates == [(3, cancelled_bob)]


def test_plan_sheet_sync_queues_new_subscriptions_newest_first():
    carol = ["Carol", "c@x.com", "Active", "2026-01-03T00:00:00Z", "Navigator ($99/mo)", "sub_C"]
    dave = ["Dave", "d@x.com", "Active", "2026-01-04T00:00:00Z", "Navigator ($99/mo)", "sub_D"]
    # fetch_subscribers hands rows over newest first: Dave, Carol, Alice, Bob.
    updates, inserts = ns.plan_sheet_sync(
        [HEADER, ALICE, BOB],
        [_row(*dave), _row(*carol), _row(*ALICE), _row(*BOB)],
    )
    assert updates == []
    # Inserted as one block at row 2, so this order leaves Dave above Carol.
    assert inserts == [dave, carol]


def test_plan_sheet_sync_ignores_columns_it_does_not_own():
    # The user keeps notes in column G. Nothing about them should show up as a change.
    with_notes = ALICE + ["called her on Tuesday"]
    updates, inserts = ns.plan_sheet_sync([HEADER + ["Notes"], with_notes], [_row(*ALICE)])
    assert (updates, inserts) == ([], [])


def test_plan_sheet_sync_matches_on_id_not_position():
    # Same two people, manually re-sorted in the sheet. Bob is now row 2.
    cancelled_bob = list(BOB)
    cancelled_bob[2] = "Canceled"
    updates, inserts = ns.plan_sheet_sync([HEADER, BOB, ALICE],
                                          [_row(*ALICE), _row(*cancelled_bob)])
    assert inserts == []
    assert updates == [(2, cancelled_bob)]


def test_plan_sheet_sync_pads_rows_whose_trailing_cells_were_dropped():
    # The Sheets API omits trailing empty cells; a blank Plan must not shift the id.
    short = ["Eve", "e@x.com", "Active", "2026-01-05T00:00:00Z", "", "sub_E"]
    updates, inserts = ns.plan_sheet_sync([HEADER, short[:6]], [_row(*short)])
    assert (updates, inserts) == ([], [])


def test_plan_sheet_sync_rejects_an_unexpected_header():
    import pytest
    with pytest.raises(ValueError):
        ns.plan_sheet_sync([["Name", "Email", "Status", "Created at", "Plan"], ALICE[:5]],
                           [_row(*ALICE)])


def test_column_letter_boundaries():
    assert ns._column_letter(1) == "A"
    assert ns._column_letter(6) == "F"
    assert ns._column_letter(26) == "Z"
    assert ns._column_letter(27) == "AA"
