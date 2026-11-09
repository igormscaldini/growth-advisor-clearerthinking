"""Tests for reports/large_newsletter_list_management_2026-11-09_src/build.py (score parsing, badges, glance table)."""
import importlib.util
from pathlib import Path

import pytest

REPORTS = Path(__file__).resolve().parents[1] / "reports"
spec = importlib.util.spec_from_file_location(
    "lnl_build", REPORTS / "large_newsletter_list_management_2026-11-09_src" / "build.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

TINY = """# Title

Intro.

## Ranked recommendations

Lead-in.

### 1. Mail engaged readers only

- **What to do.** X.
- **Score: 9/10.**

### 2. Buy a new domain

- **What to do.** Do not.
- **Score: 3/10.**

## Evidence

### A theme heading without a number

Text mentioning Score: 5/10 in passing, not as a score line.
"""


def test_recommendations_reads_number_name_and_score_in_order():
    assert b.recommendations(TINY) == [(1, "Mail engaged readers only", 9), (2, "Buy a new domain", 3)]


def test_unnumbered_headings_are_not_recommendations():
    assert all(name != "A theme heading without a number" for _, name, _ in b.recommendations(TINY))


def test_a_recommendation_without_a_score_is_an_error():
    with pytest.raises(ValueError):
        b.recommendations("### 1. No score here\n\n- **What to do.** X.\n\n## Next\n")


def test_a_score_in_the_next_section_is_not_borrowed():
    md = "### 1. No score here\n\nText.\n\n### 2. Has one\n\n- **Score: 4/10.**\n"
    with pytest.raises(ValueError):
        b.recommendations(md)


@pytest.mark.parametrize("score,expected_band,expected_verdict", [
    (10, "hi", "Adopt"), (7, "hi", "Adopt"), (6, "mid", "Adopt"), (5, "mid", "Adopt"),
    (4, "lo", "Leave alone"), (1, "lo", "Leave alone"),
])
def test_band_and_verdict_edges(score, expected_band, expected_verdict):
    assert b.band(score) == expected_band
    assert b.verdict(score) == expected_verdict


def test_with_badges_adds_badge_anchor_and_glance_table_before_first_recommendation():
    out = b.with_badges(TINY)
    assert '### <span class="score hi">9/10</span> 1. Mail engaged readers only {: #rec-1 }' in out
    assert '### <span class="score lo">3/10</span> 2. Buy a new domain {: #rec-2 }' in out
    assert '| <span class="score lo">3/10</span> | [2. Buy a new domain](#rec-2) | Leave alone |' in out
    assert out.index("| Score | Recommendation | Verdict |") < out.index("### <span")
    assert "### A theme heading without a number" in out            # untouched
    assert out.startswith("# Title\n\nIntro.")                      # nothing before the list is altered


def test_real_report_follows_the_ideas_format():
    """Igor's rule for recommendations: at least 5, numbered in order, presented from highest to lowest score."""
    md = b.SRC.read_text()
    recs = b.recommendations(md)
    assert len(recs) >= 5
    assert [n for n, _, _ in recs] == list(range(1, len(recs) + 1))
    scores = [s for _, _, s in recs]
    assert scores == sorted(scores, reverse=True)
    assert all(1 <= s <= 10 for s in scores)
    assert "—" not in md                                       # no em dashes anywhere
    assert md.splitlines()[0].startswith("# ")


def test_real_report_renders_every_anchor_the_glance_table_links_to():
    html = b.render_page(b.with_badges(b.SRC.read_text()), "T", b.EXTRA_CSS,
                         extensions=("tables", "sane_lists", "toc", "attr_list", "md_in_html"), subtitle="x")
    for n, _, _ in b.recommendations(b.SRC.read_text()):
        assert f'id="rec-{n}"' in html and f'href="#rec-{n}"' in html
    assert html.count("<table>") == 2                               # comparison table + glance table
