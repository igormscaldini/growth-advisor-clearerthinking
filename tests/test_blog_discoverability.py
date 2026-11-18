"""Pure-function tests for reports/blog_discoverability_followup_2026-11-18_src/lib.py (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reports" / "blog_discoverability_followup_2026-11-18_src"))

import lib  # noqa: E402

P = "https://www.clearerthinking.org/post/"


def test_anchors_reads_href_and_decodes_entities():
    page = '<a class="x" href="https://a.org/?a=1&amp;b=2">A</a><link href="/style.css"><a href="/b">B</a>'
    assert lib.anchors(page) == ["https://a.org/?a=1&b=2", "/b"]


def test_post_url_normalises_query_fragment_slash_and_encoding():
    want = P + "what's-new"
    assert lib.post_url(P + "what%27s-new/?utm_source=x#top") == want
    assert lib.post_url("https://clearerthinking.org/post/what's-new") == want


def test_post_url_rejects_other_hosts_and_non_posts():
    assert lib.post_url("https://blakemasters.tumblr.com/post/245/notes") is None
    assert lib.post_url("https://www.clearerthinking.org/blog") is None
    assert lib.post_url("https://www.clearerthinking.org/post/") is None
    assert lib.post_url("/post/relative") is None


def test_post_links_dedupes_and_keeps_first_seen_order():
    page = (f'<a href="{P}b">1</a><a href="{P}a?x=1">2</a><a href="{P}b/">3</a>'
            '<a href="https://example.org/post/c">4</a>')
    assert lib.post_links(page) == [P + "b", P + "a"]


def test_canonical_and_robots_meta():
    page = '<link rel="canonical" href="https://x.org/a?b=1&amp;c=2"/><meta name="robots" content="noindex"/>'
    assert lib.canonical(page) == "https://x.org/a?b=1&c=2"
    assert lib.robots_meta(page) == "noindex"
    assert lib.canonical("<html></html>") is None
    assert lib.robots_meta("<html></html>") is None


def test_numbered_duplicates_needs_both_slugs():
    urls = [P + "anchoring", P + "anchoring-1", P + "top-10", P + "habits-2", P + "x", P + "x-1", P + "x-2"]
    # top-10 has no "top" base and habits-2 has no "habits" base, so neither is a candidate.
    assert lib.numbered_duplicates(urls) == [(P + "anchoring", P + "anchoring-1"), (P + "x", P + "x-1"), (P + "x", P + "x-2")]
    assert lib.numbered_duplicates([]) == []


def test_sitewide_links_are_those_on_more_than_half_the_pages():
    pages = {"p1": ["menu", "a"], "p2": ["menu", "b"], "p3": ["menu"], "p4": ["a", "menu"]}
    assert lib.sitewide_links(pages) == {"menu"}          # "a" is on exactly half: not over the bar
    assert lib.sitewide_links(pages, share=0.4) == {"menu", "a"}
    assert lib.sitewide_links({}) == set()


def test_inbound_by_hand():
    # a -> b, c ; b -> a, b (self) ; hub -> a, b, c
    pages = {"a": ["b", "c"], "b": ["a", "b"], "hub": ["a", "b", "c"]}
    got = lib.inbound(pages)
    assert got["a"] == {"b", "hub"}
    assert got["b"] == {"a", "hub"}      # the self link is not counted
    assert got["c"] == {"a", "hub"}
    no_hub = lib.inbound(pages, ignore_sources={"hub"})
    assert no_hub["a"] == {"b"} and no_hub["b"] == {"a"} and no_hub["c"] == {"a"}
    assert "c" not in lib.inbound(pages, ignore_targets={"c"})
