"""Unit tests for the pure helpers in seo_hub_pages.py (no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seo_hub_pages import (  # noqa: E402
    clean_title,
    group_by_year,
    head_complete,
    parse_sitemap,
    published_from_url,
    render_links,
    title_from_slug,
    year_of,
)


# --- clean_title --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Who Attracts You? | Clearer Thinking", "Who Attracts You?"),
        ("Unique Traits Test - Clearer Thinking", "Unique Traits Test"),
        ("Mind &amp; Body | ClearerThinking.org", "Mind & Body"),
        ("  Spaced   out   title  ", "Spaced out title"),
        ("No suffix here", "No suffix here"),
        # A title that merely contains the site name mid-string keeps it.
        ("Clearer Thinking turns 10", "Clearer Thinking turns 10"),
        ("", ""),
    ],
)
def test_clean_title(raw, expected):
    assert clean_title(raw) == expected


def test_clean_title_strips_only_one_suffix():
    assert clean_title("A | Clearer Thinking | Clearer Thinking") == "A | Clearer Thinking"


# --- title_from_slug ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.clearerthinking.org/post/why-don-t-chimps-run-the-world", "Why don t chimps run the world"),
        ("https://programs.clearerthinking.org/achieve_your_goals_signup.html", "Achieve your goals signup"),
        ("https://www.clearerthinking.org/post/declinism-definition-1", "Declinism definition"),
        ("https://www.clearerthinking.org/tools/who-attracts-you/", "Who attracts you"),
    ],
)
def test_title_from_slug(url, expected):
    assert title_from_slug(url) == expected


def test_title_from_slug_decodes_percent_encoding():
    url = "https://www.clearerthinking.org/tools/daily-ritual%3A-a-habit-creation-system"
    assert title_from_slug(url) == "Daily ritual: a habit creation system"


# --- published_from_url -------------------------------------------------------------------
def test_published_from_url_reads_old_style_dates():
    url = "https://www.clearerthinking.org/post/2015/06/15/biases-how-they-affect-your-career"
    assert published_from_url(url) == "2015-06-15"


def test_published_from_url_none_for_new_style():
    assert published_from_url("https://www.clearerthinking.org/post/what-stands-between-you") is None


# --- year_of and group_by_year ------------------------------------------------------------
def test_year_of_prefers_published_over_lastmod():
    assert year_of({"published": "2019-03-04", "lastmod": "2026-08-26"}) == "2019"


def test_year_of_falls_back_to_lastmod_then_undated():
    assert year_of({"published": None, "lastmod": "2026-08-26"}) == "2026"
    assert year_of({"published": None, "lastmod": None}) == "Undated"


def test_group_by_year_worked_by_hand():
    """Three posts across two years plus one undated. Newest year first, undated last,
    titles alphabetical (case-insensitive) within each year."""
    items = [
        {"url": "u1", "title": "Zebra", "published": "2024-01-02", "lastmod": None},
        {"url": "u2", "title": "apple", "published": "2024-11-30", "lastmod": None},
        {"url": "u3", "title": "Older one", "published": "2019-05-05", "lastmod": None},
        {"url": "u4", "title": "Mystery", "published": None, "lastmod": None},
    ]
    assert group_by_year(items) == [
        ("2024", [items[1], items[0]]),  # apple before Zebra
        ("2019", [items[2]]),
        ("Undated", [items[3]]),
    ]


def test_group_by_year_keeps_every_item():
    items = [{"url": f"u{i}", "title": f"t{i}", "published": f"20{10 + i % 5}-01-01", "lastmod": None}
             for i in range(37)]
    grouped = group_by_year(items)
    assert sum(len(v) for _, v in grouped) == 37


# --- render_links -------------------------------------------------------------------------
def test_render_links_one_paragraph_per_link():
    items = [
        {"url": "https://x.org/a", "title": "First"},
        {"url": "https://x.org/b", "title": "Second"},
    ]
    out = render_links(items)
    assert out == ('<p><a href="https://x.org/a">First</a></p>\n'
                   '<p><a href="https://x.org/b">Second</a></p>')


def test_render_links_escapes_titles_and_urls():
    items = [{"url": "https://x.org/a?b=1&c=2", "title": 'Tom & "Jerry" <script>'}]
    out = render_links(items)
    assert "&amp;c=2" in out
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


# --- parse_sitemap ------------------------------------------------------------------------
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://www.clearerthinking.org/post/one</loc><lastmod>2026-08-26</lastmod></url>
<url><loc>https://www.clearerthinking.org/post/two</loc></url>
<url><lastmod>2020-01-01</lastmod></url>
</urlset>"""


def test_parse_sitemap_worked_by_hand():
    assert parse_sitemap(SITEMAP) == [
        {"url": "https://www.clearerthinking.org/post/one", "lastmod": "2026-08-26"},
        {"url": "https://www.clearerthinking.org/post/two", "lastmod": None},
    ]


def test_parse_sitemap_empty_document():
    assert parse_sitemap("<urlset></urlset>") == []


# --- head_complete ------------------------------------------------------------------------
# Wix serves <title> ~130KB into the document for a non-Googlebot client, so the fetcher reads
# in chunks and stops on this predicate instead of a fixed byte offset.
def test_head_complete_needs_a_title():
    assert head_complete('<html><head><meta charset="utf-8">') is False
    assert head_complete('<title>Only a title</title>') is False


def test_head_complete_on_an_article():
    assert head_complete('<title>A post</title> ... "datePublished": "2025-12-02T21:44:04.155Z"') is True


def test_head_complete_on_a_page_without_a_publish_date():
    """Tool pages carry no datePublished; </head> means no more metadata is coming."""
    assert head_complete("<title>A tool</title><meta name=x></head><body>") is True


def test_parse_sitemap_unescapes_xml_entities():
    """The tools sitemap carries world&apos;s-biggest-problems-quiz; leaving it escaped 404s."""
    xml = ("<urlset><url><loc>https://www.clearerthinking.org/tools/world&apos;s-biggest-problems-quiz"
           "</loc></url><url><loc>https://x.org/a?b=1&amp;c=2</loc></url></urlset>")
    assert [r["url"] for r in parse_sitemap(xml)] == [
        "https://www.clearerthinking.org/tools/world's-biggest-problems-quiz",
        "https://x.org/a?b=1&c=2",
    ]
