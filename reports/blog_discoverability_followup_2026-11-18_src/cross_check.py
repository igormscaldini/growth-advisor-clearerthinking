"""Independent recount of the report's headline numbers, by the simplest different route for each.

1. Internal links: read every article BODY through the Wix Blog API (rich content), not the rendered
   page, and count which articles are linked from another article's body. Compare with the crawl.
2. Indexing: an article with a search impression in the last four complete weeks must be indexed, so
   count those from Search Analytics and compare with the URL Inspection verdicts.
3. Categories: the Wix category objects carry their own postCount.
4. Hub: link count from the Wix API copy of the post against the rendered page.

Writes cross_check.json. Run after crawl_site.py, fetch_gsc.py and analysis.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

import lib  # noqa: E402
import wix_publish_hub as wix  # noqa: E402
from analysis import HUB, INDEXED, load, norm  # noqa: E402


def walk_links(node) -> list[str]:
    """Every link URL anywhere in a Ricos document (text decorations, buttons, images, embeds)."""
    out = []
    if isinstance(node, dict):
        url = node.get("link", {}).get("url") if isinstance(node.get("link"), dict) else None
        if url:
            out.append(url)
        for v in node.values():
            out += walk_links(v)
    elif isinstance(node, list):
        for v in node:
            out += walk_links(v)
    return out


def body_links() -> dict[str, list[str]]:
    cache = HERE / "data" / "wix_body_links.json"
    if cache.exists():
        return json.loads(cache.read_text())
    out, offset = {}, 0
    while True:
        res = wix._call("GET", f"/posts?paging.limit=50&paging.offset={offset}&fieldsets=URL&fieldsets=RICH_CONTENT")
        batch = res.get("posts", [])
        for p in batch:
            u = norm((p.get("url") or {}).get("base", "") + (p.get("url") or {}).get("path", ""))
            out[u] = sorted({t for t in map(lib.post_url, walk_links(p.get("richContent"))) if t})
        offset += len(batch)
        print(f"  bodies {offset}", flush=True)
        if not batch or offset >= res.get("metaData", {}).get("total", 0):
            break
    cache.write_text(json.dumps(out))
    return out


def main() -> None:
    d = json.loads((HERE / "datapoints.json").read_text())
    crawl, wixp, gsc, weekly = load("crawl.json"), load("wix_posts.json"), load("gsc_inspection.json"), load("gsc_weekly_pages.json")
    articles = [u for u in (norm(e["url"]) for e in crawl["sitemaps"]["posts"]) if u != HUB]

    bodies = body_links()
    inbound = lib.inbound({u: v for u, v in bodies.items() if u != HUB})
    api_linked = {a for a in articles if inbound.get(a)}
    chrome = set(d["links"]["chrome_targets"])
    crawl_pages = {norm(u): [norm(t) for t in p.get("post_links", [])] for u, p in crawl["pages"].items()
                   if p.get("status") == 200 and p.get("group") == "post"}
    crawl_inbound = lib.inbound(crawl_pages, ignore_sources={HUB}, ignore_targets=chrome)
    crawl_linked = {a for a in articles if crawl_inbound.get(a)}

    state = {norm(u): v for u, v in gsc.items()}
    weeks = sorted({r["week"] for r in weekly})[-4:]
    seen = {norm(r["page"].split("#")[0]) for r in weekly if r["week"] in weeks}
    indexed = {a for a in articles if state.get(a, {}).get("coverageState") in INDEXED}
    contradiction = sorted(a for a in articles if a in seen and a not in indexed)

    # Markus's July counts, rebuilt from today's data with the hub taken out: the 300 newest posts were
    # reachable by scrolling /blog, and his "zero inbound links" are the older posts no article links to.
    july = sorted((p for p in wixp["posts"] if (p["firstPublishedDate"] or "")[:10] <= "2026-07-30" and norm(p["url"]) in set(articles)),
                  key=lambda p: p["firstPublishedDate"], reverse=True)
    july_urls = {norm(p["url"]) for p in july}
    july_inbound = lib.inbound({u: v for u, v in bodies.items() if u in july_urls})
    beyond_scroll = july_urls - {norm(p["url"]) for p in july[:300]}

    out = {
        "markus_reconstruction": {
            "posts_live_on_2026_07_30": len(july_urls),
            "beyond_the_300_post_scroll": len(beyond_scroll),
            "beyond_scroll_and_not_linked_from_any_article": sum(1 for u in beyond_scroll if not july_inbound.get(u)),
            "not_linked_from_any_article_in_july": sum(1 for u in july_urls if not july_inbound.get(u)),
            "not_linked_from_any_article_today": sum(1 for a in articles if not inbound.get(a)),
        },
        "links": {
            "linked_from_another_article_body_wix_api": len(api_linked),
            "linked_from_another_article_crawl": len(crawl_linked),
            "in_api_not_crawl": sorted(api_linked - crawl_linked)[:15], "n_in_api_not_crawl": len(api_linked - crawl_linked),
            "in_crawl_not_api": sorted(crawl_linked - api_linked)[:15], "n_in_crawl_not_api": len(crawl_linked - api_linked),
            "chrome_targets_excluded_from_crawl_count": sorted(chrome),
        },
        "index": {
            "weeks": weeks, "articles_with_impressions": len(seen & set(articles)),
            "indexed_by_inspection": len(indexed),
            "indexed_with_no_impressions": len(indexed - seen),
            "not_indexed_but_with_impressions": [{"url": a, "coverage": state.get(a, {}).get("coverageState"),
                                                  "last_crawl": (state.get(a, {}).get("lastCrawlTime") or "")[:10]} for a in contradiction],
        },
        "categories": {"sum_of_category_post_counts": sum(c.get("postCount", 0) for c in wixp["categories"]),
                       "posts_with_a_category": d["categories"]["posts"] - d["categories"]["without_category"]},
        "hub": {"links_wix_api": len(wix.linked_urls(wix.find_hub_post().get("richContent"))),
                "links_raw_html": d["links"]["hub"]["links_in_raw_html"]},
    }
    (HERE / "cross_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
