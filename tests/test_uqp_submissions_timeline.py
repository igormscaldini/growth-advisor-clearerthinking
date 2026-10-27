"""Tests for reports/uqp_daily_runs_src/submissions_timeline.py (pure aggregation, no network)."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reports" / "uqp_daily_runs_src"))
from build import is_test_question  # noqa: E402
from submissions_timeline import submissions, timeline  # noqa: E402

Q_NEW = "Please submit your question here (h808ylh)"
Q_OLD = "What do you see as the biggest open question? (ozwgip)"
MAIL_NEW = "What is your email address? (itxzlya)"


def _runs(rows):
    cols = ["Time Started (UTC)", Q_NEW, Q_OLD, MAIL_NEW, "email"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows])


def test_submissions_filters_tests_blanks_and_keeps_last_answer():
    runs = _runs([
        ("2026-09-14 20:24:14", "Why?", None, "A@x.org", None),            # real, new version
        ("2026-09-15 08:00:00", None, "test", None, "test"),               # old-version test entry
        ("2026-09-16 08:00:00", None, None, None, None),                   # opened, never submitted
        ("2026-09-17 09:00:00", "v1 | v2", None, "b@x.org | b@x.org", None),  # re-answered: keep v2
        ("2026-09-18 09:00:00", None, "How?", None, "c@x.org"),            # real, old version
    ])
    sub = submissions(runs)
    assert len(sub) == 3
    assert list(sub["day"]) == [date(2026, 9, 14), date(2026, 9, 17), date(2026, 9, 18)]
    assert list(sub["responder"]) == ["a@x.org", "b@x.org", "c@x.org"]  # lower-cased, final answer only


def test_timeline_daily_and_cumulative_counts_by_hand():
    # Day 1: A submits twice (2 submissions, 1 responder). Day 2: nothing. Day 3: A again + B (2 subs, 1 new).
    sub = pd.DataFrame({
        "day": [date(2026, 10, 1), date(2026, 10, 1), date(2026, 10, 3), date(2026, 10, 3)],
        "responder": ["a@x.org", "a@x.org", "a@x.org", "b@x.org"],
    })
    out = timeline(sub, start=date(2026, 10, 1), end=date(2026, 10, 4))
    assert [d["date"] for d in out] == ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]
    assert [d["submissions"] for d in out] == [2, 0, 2, 0]
    assert [d["new_responders"] for d in out] == [1, 0, 1, 0]
    assert [d["cum_submissions"] for d in out] == [2, 2, 4, 4]
    assert [d["cum_responders"] for d in out] == [1, 1, 2, 2]


def test_timeline_counts_each_anonymous_submission_as_its_own_responder():
    sub = pd.DataFrame({"day": [date(2026, 10, 1)] * 2, "responder": [pd.NA, pd.NA]})
    out = timeline(sub, start=date(2026, 10, 1), end=date(2026, 10, 1))
    assert out[0]["submissions"] == 2 and out[0]["cum_responders"] == 2


def test_is_test_question_matches_team_entries_only():
    q = pd.Series(["test", "Testing", "Igor testing", "test 2", " TEST ",
                   "Why do personality tests predict so little?", "Is testing a skill?", None, ""])
    assert list(is_test_question(q)) == [True, True, True, True, True, False, False, False, False]


def test_submissions_drops_igor_testing_entry():
    runs = _runs([
        ("2026-10-21 10:00:00", "Igor testing", None, "igor@x.org", None),
        ("2026-10-21 11:00:00", "What is attention?", None, "d@x.org", None),
    ])
    sub = submissions(runs)
    assert len(sub) == 1 and list(sub["responder"]) == ["d@x.org"]
