"""Tests for reports/newsletter_send_strategy_2026-09-25_src/analysis.py (pure functions)."""
import importlib.util
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "reports" / "newsletter_send_strategy_2026-09-25_src" / "analysis.py"
spec = importlib.util.spec_from_file_location("nsa", SRC)
nsa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nsa)


def post(title, rec=200_000, tags=None, subject=None):
    return {"title": title, "recipients": rec, "content_tags": tags or [], "subject_line": subject or title}


# ---------------------------------------------------------------- classification
@pytest.mark.parametrize("title,rec,expected", [
    ("Self-Help Pyramid - Test Campaign", 3, "test"),
    ("One Helpful Idea: Small Addictions", 400_000, "ohi"),
    ("You're invited to a free coaching session (3)", 9_470, "coaching_outreach"),
    ("Productivity Workshop - 10min Reminder", 544, "event"),
    ("[Link Fixed] Spencer's #1 Self-Help Technique", 102_891, "event"),
    ("Discover your unusual traits with our new tool [Beta Tester Request]", 23_977, "recruitment"),
    ("Invitation to participate in a study (moral priorities)", 18_620, "recruitment"),
    ("The 12 Levers Book Launch - Email To All Subs", 154_261, "promo"),
    ("Introducing Clearer Thinking Plus", 440_918, "promo"),
    ("A Little Wiser Swap", 254_315, "promo"),
    ("Dating App - Email W/ Updates", 170_787, "promo"),
    ("Access your new personality report", 54_849, "transactional"),
    ("Monthly Debrief - July", 93_771, "wrapup"),
    ("Discover your unusual traits with our new tool [launch to supporters]", 75, "small"),
    ("What to know about sociopaths", 342_769, "core"),
    ("Launching Demystifying Meditation - ct-domain", 176_146, "core"),
    ("How (And When) To Learn From Crowds (1)", 158_574, "core"),
])
def test_classify(title, rec, expected):
    assert nsa.classify(post(title, rec)) == expected


def test_classify_coaching_tag():
    assert nsa.classify(post("A quick thought", 1154, tags=["coaching-outreach"])) == "coaching_outreach"


def test_core_subtype():
    assert nsa.core_subtype(post("Discover Your Moral Compass With Our Newest Free Tool")) == "tool_launch"
    assert nsa.core_subtype(post("Self-Help Pyramid")) == "tool_launch"
    assert nsa.core_subtype(post("What to know about sociopaths")) == "article"


@pytest.mark.parametrize("title,base", [
    ("How (And When) To Learn From Crowds (1)", "How (And When) To Learn From Crowds"),
    ("Launching Demystifying Meditation - ohi-domain", "Launching Demystifying Meditation"),
    ("Discover who attracts you - Everyone else", "Discover who attracts you"),
    ("Discover who attracts you - 50 - 100% OR", "Discover who attracts you"),
    ("Plain title", "Plain title"),
])
def test_base_title(title, base):
    assert nsa.base_title(title) == base


# ---------------------------------------------------------------- audiences
ENG = "ead5b83a-5655-44cf-82a4-e5d63f1b9c49"
NONE = "8c190f72-7019-4cd9-8ea4-339b147a3208"
HIGH = "0b1106c5-0e03-43e5-a2f0-17d50634e898"
ALL = "0f05394c-35e7-4a04-b790-a12f9a23231c"


def tgt(action, kind, rid=None):
    return {"action": action, "receiver_type": kind, "receiver_id": rid}


def test_audience_class():
    assert nsa.audience_class([tgt("include", "Publication")])[0] == "all"
    assert nsa.audience_class([tgt("include", "Publication"), tgt("exclude", "Segment", ENG)])[0] == "rest"
    assert nsa.audience_class([tgt("include", "Segment", ENG)])[0] == "engaged"
    assert nsa.audience_class([tgt("include", "Segment", ENG), tgt("exclude", "Segment", HIGH)])[0] == "engaged_minus_high"
    assert nsa.audience_class([tgt("include", "Segment", ALL), tgt("exclude", "Segment", NONE)])[0] == "all_minus_nonopeners"
    assert nsa.audience_class([tgt("include", "Segment", HIGH)])[0] == "high"
    assert nsa.audience_class([])[0] == "other"


# ---------------------------------------------------------------- rates (hand-worked)
def test_rates_hand_worked():
    r = nsa.rates({"recipients": 1000, "delivered": 800, "unique_opens": 200, "unique_clicks": 20,
                   "unique_verified_clicks": 16, "unsubscribes": 4, "spam_reports": 2})
    assert r["open_rate"] == pytest.approx(0.25)
    assert r["click_rate"] == pytest.approx(0.02)       # verified clicks / delivered
    assert r["raw_click_rate"] == pytest.approx(0.025)
    assert r["ctor"] == pytest.approx(0.08)
    assert r["unsub_rate"] == pytest.approx(0.005)
    assert r["spam_rate"] == pytest.approx(0.0025)


def test_rates_fallbacks():
    r = nsa.rates({"recipients": 500, "unique_opens": 50, "unique_clicks": 5})
    assert r["delivered"] == 500 and r["click_rate"] == pytest.approx(0.01)
    assert nsa.rates({})["open_rate"] == 0.0


# ---------------------------------------------------------------- neighbour index
def test_neighbour_index_flat_series_is_one():
    assert nsa.neighbour_index([2.0] * 6) == [1.0] * 6


def test_neighbour_index_hand_worked():
    # values 1,1,4,1,1 with k=1: middle value / median(1,1) = 4; its neighbours / median(1,4) = 0.4
    idx = nsa.neighbour_index([1.0, 1.0, 4.0, 1.0, 1.0], k=1)
    assert idx[2] == pytest.approx(4.0)
    assert idx[1] == pytest.approx(1 / 2.5)
    assert idx[0] == pytest.approx(1.0)      # only neighbour is 1.0


def test_neighbour_index_removes_drift():
    # a series doubling every step, k=1: value / median(prev, next) = 2^i / ((2^(i-1) + 2^(i+1)) / 2) = 0.8
    vals = [2.0 ** i for i in range(9)]
    idx = nsa.neighbour_index(vals, k=1)
    for v in idx[1:-1]:
        assert v == pytest.approx(0.8)
    assert idx[0] == pytest.approx(0.5) and idx[-1] == pytest.approx(2.0)


# ---------------------------------------------------------------- subject features
def test_subject_features():
    f = nsa.subject_features("[New Tool] What really guides your sense of right and wrong?", "Discover Your Moral Compass",
                             preview="custom", subtitle="default")
    assert f["question"] and f["bracket_tag"] and f["personal"] and f["tool"] and f["rewritten"] and f["custom_preview"]
    assert not f["number"] and not f["evidence"]
    assert f["words"] == 11 and not f["short"]
    g = nsa.subject_features("Stop getting fooled by this common statistics trick", "Stop getting fooled by this common statistics trick")
    assert g["negative"] and not g["rewritten"] and not g["question"]
    assert nsa.subject_features("How to form habits that actually stick")["question_word"]


# ---------------------------------------------------------------- effects & permutation test
def test_mean_log_ratio_hand_worked():
    assert nsa.mean_log_ratio([2.0, 8.0], [1.0, 1.0]) == pytest.approx(2.0)   # geometric mean 4 vs 1 -> log2 = 2
    assert nsa.mean_log_ratio([], [1.0]) == 0.0


def test_permutation_p_null_and_positive():
    rng_null = [1.0, 1.1, 0.9, 1.05, 0.95, 1.02]
    p_null = nsa.permutation_p(rng_null[:3], rng_null[3:], n_perm=2000)
    assert p_null > 0.2
    p_pos = nsa.permutation_p([4.0, 4.2, 3.9, 4.1, 4.3], [1.0, 1.1, 0.9, 1.05, 0.95], n_perm=2000)
    assert p_pos < 0.02


def test_feature_effects():
    rows = [{"click_index": 2.0, "features": {"q": True}}, {"click_index": 2.0, "features": {"q": True}},
            {"click_index": 1.0, "features": {"q": False}}, {"click_index": 1.0, "features": {"q": False}}]
    e = nsa.feature_effects(rows, "click_index", ["q"])[0]
    assert e["n_with"] == 2 and e["n_without"] == 2 and e["ratio"] == pytest.approx(2.0)


# ---------------------------------------------------------------- timing
def test_rel_hour_hist_and_tail():
    send = datetime(2026, 9, 18, 23, 0, tzinfo=timezone.utc)          # Fri 7pm ET
    hours = {"2026091819": 10, "2026091820": 5, "2026091908": 3, "2026092010": 2}   # ET dateHours
    rel = nsa.rel_hour_hist(send, hours)
    assert rel == {0: 10, 1: 5, 13: 3, 39: 2}
    th, tw = nsa.tail_hour_hist(send, hours, min_hours=24)
    assert th[10] == 2 and sum(th) == 2
    assert tw[6] == 2                                                  # 2026-09-20 is a Sunday
    shares = nsa.bucket_shares(rel, 20)
    assert shares[1] == pytest.approx(0.5) and shares[2] == pytest.approx(0.25) and shares[6] == pytest.approx(0.1)
    assert sum(shares) == pytest.approx(1.0)
