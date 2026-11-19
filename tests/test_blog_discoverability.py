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


# --- analysis.py on tiny synthetic sites whose answers are worked out by hand -------------------------
import analysis  # noqa: E402
import cross_check  # noqa: E402

HUB = analysis.HUB


def _crawl(links: dict) -> dict:
    return {"pages": {u: {"status": 200, "post_links": v, "canonical": u} for u, v in links.items()},
            "sitemaps": {"posts": [{"url": u} for u in links if "/post/" in u]}}


def test_link_graph_buckets_on_a_five_page_site():
    a, b, c, d = (P + x for x in "abcd")
    # d is the "recent post" every page links to; the hub is in every page's menu and lists everything.
    crawl = _crawl({HUB: [a, b, c, d], a: [HUB, d], b: [HUB, d, a], c: [HUB, d], d: [HUB, d]})
    g = analysis.link_graph(crawl)
    assert set(g["chrome_targets"]) == {HUB, d}            # on 4/5 and 5/5 of the post pages
    assert g["buckets"] == {"sitewide": 1, "other_pages": 1, "hub_only": 2}   # d | a (from b) | b and c
    assert g["zero_inbound_including_hub"] == []
    assert g["linked_from_another_post"] == 1
    assert g["hub"] == {"links_in_raw_html": 4, "missing": [], "stale": []}
    assert g["hub_on_share_of_posts"] == 0.8


def test_link_graph_flags_an_article_the_hub_misses_and_a_stale_hub_link():
    a, b = P + "a", P + "b"
    crawl = _crawl({HUB: [a, P + "gone"], a: [HUB], b: [HUB]})
    g = analysis.link_graph(crawl)
    assert g["hub"]["missing"] == [b] and g["hub"]["stale"] == [P + "gone"]
    assert g["buckets"] == {"hub_only": 1, "none": 1}
    assert g["zero_inbound_including_hub"] == [b]


def test_links_on_unlinked_archive_pages_do_not_count_as_a_way_in():
    a = P + "a"
    crawl = _crawl({HUB: [a], a: [HUB]})
    crawl["pages"]["https://www.clearerthinking.org/blog/page/7"] = {"status": 200, "post_links": [a], "blog_page_links": []}
    assert analysis.link_graph(crawl)["buckets"] == {"hub_only": 1}


def test_baseline_timing_by_hand():
    a, b, c = P + "a", P + "b", P + "c"
    base = [{"url": a, "domain": "www", "reason": "x"}, {"url": b, "domain": "www", "reason": "x"},
            {"url": c, "domain": "www", "reason": "x"}, {"url": "https://programs.clearerthinking.org/t.html", "domain": "p", "reason": "x"}]
    gsc = {a: {"coverageState": "Submitted and indexed", "lastCrawlTime": "2026-10-05T00:00:00Z"},
           b: {"coverageState": "Submitted and indexed", "lastCrawlTime": "2026-08-01T00:00:00Z"},
           c: {"coverageState": "Discovered - currently not indexed"}}
    weekly = [{"week": "2026-10-05", "page": a, "clicks": 1, "impressions": 9},
              {"week": "2026-08-03", "page": b, "clicks": 0, "impressions": 2},
              {"week": "2026-10-12", "page": b, "clicks": 0, "impressions": 2}]
    got = analysis.baseline_timing(weekly, base, gsc)
    assert got["first_impressions"] == {"after the hub": 1, "before the hub": 1}     # c is not indexed: not counted
    assert got["last_crawl"] == {"last crawl after the hub": 1, "last crawl before the hub": 1}


def test_search_weekly_sums_and_baseline_subset():
    a, b = P + "a", P + "b"
    base = [{"url": a, "domain": "www", "reason": "x"}]
    weekly = [{"week": "2026-09-14", "page": a, "clicks": 1, "impressions": 10},
              {"week": "2026-09-14", "page": b + "#anchor", "clicks": 2, "impressions": 20},
              {"week": "2026-09-14", "page": b, "clicks": 3, "impressions": 30},
              {"week": "2026-10-05", "page": b, "clicks": 5, "impressions": 50}]
    s = analysis.search(weekly, base, {})
    w1, w2 = s["weekly"]
    assert (w1["pages_with_impressions"], w1["clicks"], w1["impressions"]) == (2, 6, 60)   # b and b#anchor are one page
    assert (w1["baseline_posts_with_impressions"], w1["baseline_clicks"], w1["baseline_impressions"]) == (1, 1, 10)
    assert (w2["pages_with_impressions"], w2["baseline_posts_with_impressions"]) == (1, 0)
    assert s["before_hub"]["n_weeks"] == 1 and s["before_hub"]["avg_clicks"] == 6.0


def test_categories_counts_posts_without_one():
    wix = {"categories": [{"id": "r", "label": "research"}, {"id": "b", "label": "blog"}],
           "posts": [{"url": P + "a", "categoryIds": ["r", "b"], "tagIds": []}, {"url": P + "b", "categoryIds": [], "tagIds": ["t"]},
                     {"url": P + "c", "categoryIds": [], "tagIds": []}, {"url": P + "d", "categoryIds": ["r"], "tagIds": []}]}
    got = analysis.categories(wix)
    assert (got["posts"], got["without_category"], got["pct_without"]) == (4, 2, 50.0)
    assert got["per_category"] == {"research": 2, "blog": 1} and got["with_tags"] == 1


def test_walk_links_finds_links_at_any_depth():
    doc = {"nodes": [{"nodes": [{"textData": {"decorations": [{"linkData": {"link": {"url": "u1"}}}]}}]},
                     {"buttonData": {"link": {"url": "u2"}}}, {"imageData": {"link": {"target": "BLANK"}}}]}
    assert cross_check.walk_links(doc) == ["u1", "u2"]
    assert cross_check.walk_links(None) == []


def test_by_month_fills_silent_months_with_zero():
    days = [{"keys": ["2025-11-30"], "impressions": 3, "clicks": 1}, {"keys": ["2026-02-01"], "impressions": 5, "clicks": 0},
            {"keys": ["2026-02-02"], "impressions": 2, "clicks": 1}]
    assert analysis.by_month(days) == [{"month": "2025-11", "impressions": 3, "clicks": 1}, {"month": "2025-12", "impressions": 0, "clicks": 0},
                                       {"month": "2026-01", "impressions": 0, "clicks": 0}, {"month": "2026-02", "impressions": 7, "clicks": 1}]
    assert analysis.by_month([]) == []


def test_not_indexed_group():
    assert analysis.not_indexed_group(P + "impact-bias-definition-examples-and-effects-1") == "bias glossary"
    assert analysis.not_indexed_group(P + "2017/03/14/want-to-change-your-habits") == "2015-2020 announcements"
    assert analysis.not_indexed_group(P + "why-don-t-chimps-run-the-world") == "other articles"


def test_chart_axis_ceiling_and_empty_segments():
    import charts
    assert charts._nice_max(51) == 60 and charts._nice_max(47) == 60 and charts._nice_max(20) == 20 and charts._nice_max(21) == 40
    bar = charts.segmented_bar([{"label": "A", "value": 9, "slot": 1}, {"label": "B", "value": 0, "slot": 2}, {"label": "C", "value": 1, "slot": 3}], 10)
    assert bar.count('class="seg"') == 2 and "B" not in bar          # a part at zero draws nothing, in the bar or the legend
    assert ">9<" in bar and "90.0%" in bar and "10.0%" in bar
