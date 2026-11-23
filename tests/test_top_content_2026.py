import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reports" / "top_content_2026_src"))
from rules import article_reach, rank  # noqa: E402


def test_reach_sums_every_send_plus_web():
    # 100 + 50 opens over two sends, 7 web users -> 157
    assert article_reach([100, 50], 7) == 157


def test_reach_single_send_no_web():
    assert article_reach([42], 0) == 42


def test_reach_no_sends():
    assert article_reach([], 5) == 5


def test_rank_orders_desc_and_cuts():
    rows = [{"title": t, "reach": r} for t, r in [("a", 1), ("b", 5), ("c", 3), ("d", 4)]]
    assert [r["title"] for r in rank(rows, n=2)] == ["b", "d"]


def test_rank_ties_broken_by_title():
    rows = [{"title": "zeta", "reach": 9}, {"title": "alpha", "reach": 9}]
    assert [r["title"] for r in rank(rows)] == ["alpha", "zeta"]


def test_rank_other_key():
    rows = [{"title": "x", "users": 2}, {"title": "y", "users": 3}]
    assert rank(rows, key="users")[0]["title"] == "y"
