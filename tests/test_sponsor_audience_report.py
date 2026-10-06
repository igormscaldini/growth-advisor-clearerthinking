"""Tests for the pure functions in reports/ct_sponsor_audience_report_2026-10-06_src/analysis.py."""
import importlib.util
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "ct_sponsor_audience_report_2026-10-06_src" / "analysis.py"
spec = importlib.util.spec_from_file_location("sponsor_analysis", SRC)
an = importlib.util.module_from_spec(spec)
sys.modules["sponsor_analysis"] = an
spec.loader.exec_module(an)


def ts(d: str) -> int:
    return int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())


def post(day, subject, recipients, opens, clicks=0, links=(), sender="a@x"):
    return {"subject_line": subject, "publish_date": ts(day), "from_address": sender,
            "email": {"recipients": recipients, "unique_opens": opens, "unique_verified_clicks": clicks},
            "links": [{"url": u, "unique_clicks": c} for u, c in links]}


# --------------------------------------------------------------------------- classification
def test_norm_subject_strips_tag_and_case():
    assert an.norm_subject("[Regular]  One Helpful Idea:  Foo ") == "one helpful idea: foo"
    assert an.norm_subject(None) == ""


@pytest.mark.parametrize("subject,kind", [
    ("One Helpful Idea: Sums vs Products", "ohi"),
    ("[No HTML] One Helpful Idea: X", "ohi"),
    ("New Tool: Who attracts you?", "promo"),
    ("Free tool: What's your type?", "promo"),
    ("What's next about our dating app", "promo"),
    ("Early access: Who attracts you?", "promo"),
    ("Where Marxists and capitalists actually agree", "main"),
    ("A new tool-free way to think", "main"),
])
def test_classify(subject, kind):
    assert an.classify(subject) == kind


# --------------------------------------------------------------------------- editions
def test_group_editions_merges_same_subject_within_three_days_and_sums_stats():
    posts = [
        post("2026-05-28", "An extract", 60_000, 20_000, 300, [("https://s.org/a", 10)], "ohi@x"),
        post("2026-05-29", "An extract", 10_000, 5_000, 50, [("https://s.org/b", 4)], "info@x"),
        post("2026-05-29", "Other subject", 1_000, 100, 1),
        post("2026-06-05", "An extract", 2_000, 200, 2),   # same subject, 8 days later: a new edition
    ]
    eds = an.group_editions(posts)
    assert [e["subject"] for e in eds] == ["An extract", "Other subject", "An extract"]
    first = eds[0]
    assert first["posts"] == 2
    assert first["date"] == date(2026, 5, 28)
    assert (first["recipients"], first["unique_opens"], first["unique_verified_clicks"]) == (70_000, 25_000, 350)
    assert first["senders"] == ["ohi@x", "info@x"]
    assert [l["url"] for l in first["links"]] == ["https://s.org/a", "https://s.org/b"]
    assert eds[2]["posts"] == 1


def test_edition_row_open_rate():
    e = an.group_editions([post("2026-07-01", "S", 200_000, 50_000, 500)])[0]
    row = an.edition_row(e)
    assert row["open_rate"] == pytest.approx(0.25)
    assert row["date"] == "2026-07-01"
    assert "links" not in row


# --------------------------------------------------------------------------- summaries
def test_summarize_by_hand():
    eds = an.group_editions([
        post("2026-07-01", "A", 100_000, 40_000, 400),
        post("2026-07-08", "B", 200_000, 50_000, 1_000),
        post("2026-07-15", "C", 300_000, 90_000, 900),
    ])
    s = an.summarize(eds)
    assert s["n"] == 3
    assert s["median_unique_opens"] == 50_000
    assert s["mean_unique_opens"] == 60_000
    assert (s["min_unique_opens"], s["max_unique_opens"]) == (40_000, 90_000)
    assert s["median_recipients"] == 200_000
    assert s["median_open_rate"] == pytest.approx(0.3)      # rates 0.4, 0.25, 0.3
    assert s["median_verified_clicks"] == 900
    assert s["median_click_to_open"] == pytest.approx(0.01)  # 0.01, 0.02, 0.01


def test_summarize_empty():
    assert an.summarize([]) == {"n": 0}


def test_sponsor_results_counts_matching_links_per_edition():
    eds = an.group_editions([
        post("2026-07-01", "A", 100_000, 50_000, 0, [("http://80000hours.org/clearerthinking", 300), ("https://ct.org/x", 900)]),
        post("2026-07-02", "A", 10_000, 10_000, 0, [("http://80000hours.org/clearerthinking", 60)]),
        post("2026-08-01", "B", 100_000, 50_000, 0, [("https://other.org", 5)]),
    ])
    placements = [{"date": "2026-07-01", "match": "80000hours.org/clearerthinking", "sponsor": "S", "format": "spot"},
                  {"date": "2026-09-01", "match": "nothing", "sponsor": "missing edition", "format": "spot"}]
    res = an.sponsor_results(eds, placements)
    assert len(res) == 1
    r = res[0]
    assert (r["unique_clicks"], r["links"], r["unique_opens"]) == (360, 2, 60_000)
    assert r["clicks_per_1000_opens"] == pytest.approx(6.0)


def test_country_shares_anglosphere():
    ga4 = {"window_days": 90, "pulled": "x", "total_sessions": 1000,
           "rows": [{"country": "United States", "sessions": 500, "users": 1}, {"country": "Germany", "sessions": 300, "users": 1},
                    {"country": "Ireland", "sessions": 150, "users": 1}, {"country": "Brazil", "sessions": 50, "users": 1}]}
    c = an.country_shares(ga4, top=2)
    assert [r["country"] for r in c["rows"]] == ["United States", "Germany"]
    assert c["rows"][0]["share"] == pytest.approx(0.5)
    assert c["anglosphere_share"] == pytest.approx(0.65)


def test_build_filters_window_and_counts_editions_per_week():
    posts = [
        post("2026-06-20", "Spring", 200_000, 90_000, 100),      # before the window: ytd only
        post("2026-07-02", "Main one", 200_000, 80_000, 800),
        post("2026-07-09", "One Helpful Idea: X", 200_000, 70_000, 700),
        post("2026-07-16", "New Tool: Y", 200_000, 10_000, 500),   # promo: shown, not counted as regular
        post("2026-07-20", "Small segment send", 50_000, 20_000, 50),  # below the full-list threshold
    ]
    engaged = {"engaged": 123, "segment_name": "seg", "last_calculated": ts("2026-06-08")}
    ga4 = {"window_days": 90, "pulled": "x", "total_sessions": 10, "rows": [{"country": "United States", "sessions": 10, "users": 1}]}
    dp = an.build(posts, engaged, ga4, "pulled-at", date(2026, 7, 29))  # 4 weeks after 1 July
    assert [e["kind"] for e in dp["editions_recent"]] == ["main", "ohi", "promo"]
    assert dp["stats_recent"]["regular"]["n"] == 2
    assert dp["stats_recent"]["regular"]["median_unique_opens"] == 75_000
    assert dp["stats_recent"]["promo"]["n"] == 1
    assert dp["stats_ytd"]["regular"]["n"] == 3
    assert dp["regular_editions_per_week"] == pytest.approx(0.5)
    assert dp["engaged"] == {"count": 123, "segment": "seg", "calculated": "2026-06-08"}
    assert dp["window"]["weeks"] == 4.0
