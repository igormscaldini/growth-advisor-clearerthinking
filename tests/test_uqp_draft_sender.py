from datetime import date, datetime

from uqp_draft_sender import ET, batch_size, et_midnight_epoch, in_window, is_send_day, pick_batch


def test_send_days_cover_exactly_ten_days_through_nov_30():
    days = [date(2026, 11, d) for d in range(12, 31) if is_send_day(date(2026, 11, d))]
    assert days == [date(2026, 11, d) for d in (13, 16, 17, 18, 19, 20, 23, 24, 25, 30)]


def test_weekends_holidays_and_before_start_are_off():
    assert not is_send_day(date(2026, 11, 12))  # before start
    assert not is_send_day(date(2026, 11, 14))  # Saturday
    assert not is_send_day(date(2026, 11, 26))  # Thanksgiving
    assert not is_send_day(date(2026, 11, 27))  # Friday after
    assert is_send_day(date(2026, 12, 1))       # leftovers roll on to later weekdays


def test_window_edges():
    assert not in_window(datetime(2026, 11, 13, 9, 29, tzinfo=ET))
    assert in_window(datetime(2026, 11, 13, 9, 30, tzinfo=ET))
    assert in_window(datetime(2026, 11, 13, 16, 59, tzinfo=ET))
    assert not in_window(datetime(2026, 11, 13, 17, 0, tzinfo=ET))


def test_batch_size_tops_up_and_never_exceeds_remaining():
    assert batch_size(0, 100) == 10
    assert batch_size(4, 100) == 6
    assert batch_size(10, 100) == 0
    assert batch_size(12, 100) == 0
    assert batch_size(0, 3) == 3
    assert batch_size(0, 0) == 0


def test_pick_batch_is_oldest_first():
    drafts = [{"id": "c", "internalDate": "300"}, {"id": "a", "internalDate": "100"},
              {"id": "b", "internalDate": "1000"}, {"id": "d", "internalDate": "200"}]
    assert [d["id"] for d in pick_batch(drafts, 3)] == ["a", "d", "c"]
    assert pick_batch(drafts, 0) == []


def test_et_midnight_epoch_is_utc_minus_5_in_november():
    # 2026-11-13 00:00 EST = 05:00 UTC = 1794546000
    assert et_midnight_epoch(datetime(2026, 11, 13, 14, 0, tzinfo=ET)) == 1794546000
