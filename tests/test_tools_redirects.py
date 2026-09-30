"""Unit tests for the pure helpers in tools_redirects.py (no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools_redirects import ALREADY_DONE, EXCLUDE, build_redirects, is_special, slug_of  # noqa: E402


@pytest.mark.parametrize("slug,expected", [
    ("who-attracts-you", False),
    ("the_intrinsic_values_test", False),
    ("40-winks%3A-better-sleep-made-easy", True),       # encoded colon
    ("what-causes-match-your-values%3F", True),          # encoded question mark
    ("world's-biggest-problems-quiz", True),             # literal apostrophe
    ("how-rational-are-you%2C-really%3F", True),         # encoded comma + question mark
])
def test_is_special(slug, expected):
    assert is_special(slug) is expected


def test_slug_of_keeps_the_encoded_form():
    """The live URL uses the percent-encoded path; the decoded form 404s."""
    u = "https://www.clearerthinking.org/tools/what-causes-match-your-values%3F"
    assert slug_of(u) == "what-causes-match-your-values%3F"


def test_build_redirects_worked_by_hand():
    rows = [
        {"wix_url": "https://www.clearerthinking.org/tools/alpha",
         "target": "https://programs.clearerthinking.org/alpha.html"},
        {"wix_url": "https://www.clearerthinking.org/tools/beta%3F",
         "target": "https://programs.clearerthinking.org/beta.html"},
    ]
    simple, special = build_redirects(rows)
    assert simple == [{"from": "/tools/alpha", "to": "https://programs.clearerthinking.org/alpha.html"}]
    assert special == [{"from": "/tools/beta%3F", "to": "https://programs.clearerthinking.org/beta.html"}]


def test_build_redirects_skips_the_excluded_third_party_tool():
    """Igor chose to leave this one alone rather than 301 a CT URL off-domain."""
    slug = next(iter(EXCLUDE))
    rows = [{"wix_url": f"https://www.clearerthinking.org/tools/{slug}", "target": "https://example.org/x"}]
    assert build_redirects(rows) == ([], [])


def test_build_redirects_skips_the_already_redirected():
    slug = next(iter(ALREADY_DONE))
    rows = [{"wix_url": f"https://www.clearerthinking.org/tools/{slug}", "target": "https://x.org/a"}]
    assert build_redirects(rows) == ([], [])


def test_build_redirects_fills_a_manual_target_when_the_scrape_found_none():
    rows = [{"wix_url": "https://www.clearerthinking.org/tools/society-explained", "target": None}]
    simple, special = build_redirects(rows)
    assert simple == [{"from": "/tools/society-explained", "to": "https://society.clearerthinking.org/"}]


def test_build_redirects_drops_rows_with_no_target_at_all():
    rows = [{"wix_url": "https://www.clearerthinking.org/tools/mystery-tool", "target": None}]
    assert build_redirects(rows) == ([], [])


def test_from_paths_are_site_relative_and_unique():
    rows = [{"wix_url": f"https://www.clearerthinking.org/tools/t{i}",
             "target": f"https://programs.clearerthinking.org/t{i}.html"} for i in range(20)]
    simple, _ = build_redirects(rows)
    froms = [e["from"] for e in simple]
    assert all(f.startswith("/tools/") for f in froms)
    assert len(froms) == len(set(froms)) == 20
