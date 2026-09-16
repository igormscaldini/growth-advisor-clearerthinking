"""Pure-function tests for workshop_signups_sheet.py (no network)."""
from workshop_signups_sheet import HEADER, is_test_signup, normalize_email, plan_changes, real_signups, to_row


def row(run, email, first="", question="", src="", finished="2026-09-20 10:00:00", local="Sep 20th, 2026, 7:00 AM"):
    return {"Run": str(run), "Time Started (UTC)": "2026-09-20 09:59:00", "Time Finished (UTC)": finished,
            "src": src, "signupEmail": email, "signupFirstName": first, "questionForSession": question, "signedUpAt": local}


def test_normalize_email():
    assert normalize_email("  Ann@Example.COM ") == "ann@example.com"
    assert normalize_email(None) == ""


def test_test_signups_are_excluded():
    assert is_test_signup(row(1, "a@b.co", src="test"))
    assert is_test_signup(row(1, "a@b.co", src="E2ETEST"))
    assert is_test_signup(row(1, "igor+gtprobe@x.io"))
    assert not is_test_signup(row(1, "a@b.co", src="newsletter"))
    assert not is_test_signup(row(1, "a@b.co"))


def test_real_signups_keeps_latest_run_per_email_and_skips_empty():
    rows = [
        row(10, "ann@x.io", first="Ann", question="first try", src="newsletter"),
        row(12, "ANN@x.io", first="Ann", question="second try", src="referral", finished="2026-09-21 08:00:00"),
        row(11, "", first="nobody"),
        row(13, "bob@x.io", src="test"),
        row(14, "cat@x.io", finished=""),  # unfinished run that still gave an email
    ]
    out = real_signups(rows)
    assert list(out) == ["ann@x.io", "cat@x.io"]
    assert out["ann@x.io"]["question"] == "second try"
    assert out["ann@x.io"]["src"] == "referral"
    assert out["ann@x.io"]["signed_up_utc"] == "2026-09-21 08:00:00"
    assert out["cat@x.io"]["signed_up_utc"] == "2026-09-20 09:59:00"  # falls back to start time


def test_to_row_matches_header_layout():
    rec = real_signups([row(1, "ann@x.io", first="Ann", question="Q?", src="newsletter")])["ann@x.io"]
    r = to_row(rec)
    assert len(r) == len(HEADER)
    assert r == ["2026-09-20 10:00:00", "ann@x.io", "Ann", "Q?", "newsletter", "Sep 20th, 2026, 7:00 AM", "sync"]


def test_plan_changes_appends_missing_updates_changed_keeps_live_rows():
    sheet = [
        HEADER,
        ["2026-09-19 12:00:00", "ann@x.io", "Ann", "old question", "newsletter", "local", "live"],
        ["2026-09-19 13:00:00", "bob@x.io", "Bob", "", "", "", "live"],
    ]
    signups = real_signups([
        row(1, "ann@x.io", first="Ann", question="new question", src="newsletter"),
        row(2, "bob@x.io", first="Bob"),
        row(3, "cat@x.io", first="Cat", question="Hi", src="overcome"),
    ])
    appends, updates = plan_changes(sheet, signups)
    assert appends == [["2026-09-20 10:00:00", "cat@x.io", "Cat", "Hi", "overcome", "Sep 20th, 2026, 7:00 AM", "sync"]]
    # Ann's question changed: row 2 is refreshed but keeps its timestamp and "live" marker.
    assert updates == {2: ["2026-09-19 12:00:00", "ann@x.io", "Ann", "new question", "newsletter", "local", "live"]}


def test_plan_changes_on_header_only_sheet_and_short_rows():
    signups = real_signups([row(1, "ann@x.io")])
    appends, updates = plan_changes([HEADER], signups)
    assert len(appends) == 1 and updates == {}
    # A sheet row shorter than the header (trailing blanks dropped by the API) is handled.
    appends, updates = plan_changes([HEADER, ["t", "ann@x.io"]], signups)
    assert appends == [] and updates == {}
