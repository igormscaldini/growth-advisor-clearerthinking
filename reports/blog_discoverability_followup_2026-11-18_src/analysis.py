"""Turn the crawl, the Wix post list and the Search Console pulls into datapoints.json.

Every number in the report comes from here. Markus's July figures are quoted from his email
(2026-07-30) and are not recomputed: they are the "before" column.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import lib  # noqa: E402

DATA = HERE / "data"
HUB = "https://www.clearerthinking.org/post/all-clearer-thinking-articles"
MARKUS = "https://www.clearerthinking.org/post/what-20-000-people-taught-us-about-entrepreneurship-and-startups"
HUB_LIVE = "2026-09-30"          # hub published and added to the site menu (a Wednesday)
HUB_WEEK = "2026-09-28"          # the Monday of that week: weekly figures count it as "after"
EMAIL = "2026-07-30"             # Markus's email
INDEXED = ("Submitted and indexed", "Indexed, not submitted in sitemap")
MARKUS_CLAIMS = {"posts": 611, "no_category": 585, "zero_inbound": 272, "unreachable_from_blog": 316,
                 "tools_pages": 96, "tools_unlinked": 96, "duplicate_pairs": 10, "blog_feed_links": 3}


def norm(u: str) -> str:
    return lib.post_url(u) or u.rstrip("/")


def load(name: str):
    return json.loads((DATA / name).read_text())


def link_graph(crawl: dict) -> dict:
    """Who links to each article in raw HTML, split into menu/widget chrome, the hub and real links."""
    pages = {norm(u): [norm(t) for t in p.get("post_links", [])]
             for u, p in crawl["pages"].items() if p.get("status") == 200}
    sitemap_posts = [norm(e["url"]) for e in crawl["sitemaps"]["posts"]]
    articles = [u for u in sitemap_posts if u != HUB]
    post_pages = {u: pages[u] for u in sitemap_posts if u in pages}
    chrome = lib.sitewide_links(post_pages)                      # linked from more than half of all posts
    # /blog/page/N are not linked from anywhere, so a link that only exists there is not a path in.
    orphan_sources = {u for u in pages if "/blog/page/" in u}
    everything = lib.inbound(pages, ignore_sources=orphan_sources)
    editorial = lib.inbound(pages, ignore_sources=orphan_sources | {HUB}, ignore_targets=chrome)

    hub_links = set(pages.get(HUB, []))
    buckets = Counter()
    only_hub = []
    for a in articles:
        if a in chrome:
            buckets["sitewide"] += 1
        elif editorial.get(a):
            buckets["other_pages"] += 1
        elif a in hub_links:
            buckets["hub_only"] += 1
            only_hub.append(a)
        else:
            buckets["none"] += 1
    n_edit = sorted(len(editorial.get(a, ())) for a in articles if a not in chrome)
    from_posts = lib.inbound(post_pages, ignore_sources={HUB}, ignore_targets=chrome)
    return {
        "pages_crawled": len(pages), "post_pages_crawled": len(post_pages), "articles": len(articles),
        "chrome_targets": sorted(chrome),
        "hub_on_share_of_posts": round(sum(HUB in v for v in post_pages.values()) / len(post_pages), 4),
        "buckets": dict(buckets), "hub_only_examples": only_hub[:8],
        "zero_inbound_including_hub": [a for a in articles if not everything.get(a)],
        "median_other_links": n_edit[len(n_edit) // 2] if n_edit else 0,
        "linked_from_another_post": sum(1 for a in articles if from_posts.get(a)),
        "markus_article_sources": sorted(editorial.get(MARKUS, ())),
        "hub": {
            "links_in_raw_html": len(hub_links - {HUB}),
            "missing": sorted(set(articles) - hub_links),
            "stale": sorted(hub_links - set(sitemap_posts)),
        },
        "blog_feed": {
            u.rsplit("clearerthinking.org", 1)[1] or "/": {
                "status": p.get("status"),
                "post_links_excl_chrome": len([t for t in map(norm, p.get("post_links", [])) if t != HUB]),
                "pagination_links": [x for x in p.get("blog_page_links", []) if x.rstrip("/") != u.rstrip("/")],
            } for u, p in crawl["pages"].items() if u.rstrip("/").endswith(".org/blog") or "/blog/page/" in u},
        "category_pages": {u.rsplit("/", 1)[1]: len([t for t in map(norm, p.get("post_links", [])) if t not in chrome and t != HUB])
                           for u, p in crawl["pages"].items() if "/blog/categories/" in u},
        "canonical_mismatch": sorted(u for u in sitemap_posts if u in pages and norm(crawl_canon(crawl, u) or "") != u),
        "noindex": sorted(u for u, p in crawl["pages"].items() if "noindex" in (p.get("robots") or "")),
        "not_200": {u: p.get("status") for u, p in crawl["pages"].items() if p.get("status") != 200 and "/page/101" not in u},
    }


def crawl_canon(crawl: dict, normed: str) -> str | None:
    for u, p in crawl["pages"].items():
        if norm(u) == normed:
            return p.get("canonical")
    return None


def categories(wix: dict) -> dict:
    names = {c["id"]: c["label"] for c in wix["categories"]}
    posts = wix["posts"]
    per = Counter(names.get(i, i) for p in posts for i in p["categoryIds"])
    none = sum(1 for p in posts if not p["categoryIds"])
    return {"posts": len(posts), "without_category": none, "pct_without": round(100 * none / len(posts), 1),
            "per_category": {c["label"]: per.get(c["label"], 0) for c in wix["categories"]},
            "with_tags": sum(1 for p in posts if p["tagIds"]),
            "markus_article_categories": [names.get(i, i) for p in posts if norm(p["url"]) == MARKUS for i in p["categoryIds"]]}


def duplicates(crawl: dict, wix: dict, gsc: dict) -> dict:
    title = {norm(p["url"]): p["title"] for p in wix["posts"]}
    published = {norm(p["url"]): (p["firstPublishedDate"] or "")[:10] for p in wix["posts"]}
    urls = sorted(set(title) | {norm(e["url"]) for e in crawl["sitemaps"]["posts"]})
    state = {norm(u): v for u, v in gsc.items()}

    def side(u):
        s = state.get(u, {})
        return {"url": u, "title": title.get(u), "published": published.get(u),
                "canonical_is_self": norm(crawl_canon(crawl, u) or "") == u,
                "coverage": s.get("coverageState"), "google_canonical": s.get("googleCanonical")}

    pairs = [{"base": side(b), "copy": side(c), "same_title": (title.get(b) or "").strip().lower() == (title.get(c) or "").strip().lower()}
             for b, c in lib.numbered_duplicates(urls)]
    by_title = defaultdict(list)
    for u, t in title.items():
        by_title[re.sub(r"\W+", " ", t or "").strip().lower()].append(u)
    same_title = {t: sorted(us) for t, us in by_title.items() if len(us) > 1}
    return {"numbered_pairs": pairs, "same_title_groups": same_title}


def tools(crawl: dict) -> dict:
    t = crawl.get("tools", {})
    by = Counter(str(v.get("status")) for v in t.values())
    dest = Counter(re.sub(r"^https?://([^/]+).*", r"\1", v.get("location") or "") for v in t.values() if v.get("status") in (301, 302, 308))
    tools_page = next((p for u, p in crawl["pages"].items() if u.endswith("/clearer-thinking-tools")), {})
    return {"in_sitemap": len(t), "by_status": dict(by), "redirect_hosts": dict(dest),
            "still_200": sorted(u for u, v in t.items() if v.get("status") == 200),
            "tools_page_anchors": tools_page.get("n_anchors")}


def not_indexed_group(url: str) -> str:
    """Three kinds of article Google is skipping; the split decides what is worth fixing."""
    if "definition-examples-and-effects" in url:
        return "bias glossary"
    if re.search(r"/post/20\d\d/\d\d/\d\d/", url):
        return "2015-2020 announcements"
    return "other articles"


def index_status(crawl: dict, wix: dict, gsc: dict, base: list[dict]) -> dict:
    state = {norm(u): v for u, v in gsc.items()}
    sitemap_posts = [norm(e["url"]) for e in crawl["sitemaps"]["posts"]]
    articles = [u for u in sitemap_posts if u != HUB]
    cov = Counter(state.get(u, {}).get("coverageState", "not inspected") for u in articles)
    indexed = [u for u in articles if state.get(u, {}).get("coverageState") in INDEXED]

    def crawled(u):
        return (state.get(u, {}).get("lastCrawlTime") or "")[:10]

    via_hub = [u for u in articles if HUB in [norm(r) for r in state.get(u, {}).get("referringUrls", [])]]
    not_indexed = sorted(({"url": u, "coverage": state.get(u, {}).get("coverageState"), "last_crawl": crawled(u) or None}
                          for u in articles if u not in indexed), key=lambda r: (r["coverage"] or "", r["url"]))

    base_posts = [b for b in base if "/post/" in b["url"]]
    trans = Counter()
    for b in base_posts:
        now = state.get(norm(b["url"]), {}).get("coverageState", "not inspected")
        trans[(b["reason"], "Indexed" if now in INDEXED else now)] += 1
    base_now_indexed = sum(n for (r, now), n in trans.items() if now == "Indexed")
    by_domain = defaultdict(Counter)
    for b in base:
        kind = "blog posts" if "/post/" in b["url"] else "/tools/ pages" if "clearerthinking.org/tools/" in b["url"] else b["domain"]
        now = state.get(norm(b["url"]), {}).get("coverageState", "not inspected")
        by_domain[kind]["Indexed" if now in INDEXED else now] += 1
    wix_only = sorted(set(norm(p["url"]) for p in wix["posts"]) - set(sitemap_posts))
    return {
        "articles": len(articles), "coverage": dict(cov), "indexed": len(indexed),
        "pct_indexed": round(100 * len(indexed) / len(articles), 1),
        "crawled_since_hub": sum(1 for u in articles if crawled(u) >= HUB_LIVE),
        "never_crawled": sum(1 for u in articles if not crawled(u)),
        "hub_is_referring_url": len(via_hub),
        "hub_referrer_and_indexed": sum(1 for u in via_hub if u in indexed),
        "hub_status": {k: state.get(HUB, {}).get(k) for k in ("coverageState", "lastCrawlTime", "googleCanonical")},
        "not_indexed": not_indexed,
        "bias_series_not_indexed": sum(1 for r in not_indexed if "definition-examples-and-effects" in r["url"]),
        "not_indexed_groups": dict(Counter(not_indexed_group(r["url"]) for r in not_indexed)),
        "soft_404": [r["url"] for r in not_indexed if r["coverage"] == "Soft 404"],
        "crawled_declined_recently": [r for r in not_indexed if r["coverage"] == "Crawled - currently not indexed" and (r["last_crawl"] or "") >= HUB_LIVE],
        "baseline": {"rows": len(base), "posts": len(base_posts), "posts_now_indexed": base_now_indexed,
                     "posts_crawled_since_hub": sum(1 for b in base_posts if crawled(norm(b["url"])) >= HUB_LIVE),
                     "posts_never_crawled": sum(1 for b in base_posts if not crawled(norm(b["url"]))),
                     "transitions": [{"then": r, "now": now, "n": n} for (r, now), n in sorted(trans.items(), key=lambda kv: -kv[1])],
                     "by_group": {k: dict(v) for k, v in by_domain.items()}},
        "wix_posts_missing_from_sitemap": [{"url": u, "coverage": state.get(u, {}).get("coverageState")} for u in wix_only],
        "errors": sum(1 for v in gsc.values() if "error" in v),
    }


def search(weekly: list[dict], base: list[dict], idx: dict) -> dict:
    base_posts = {norm(b["url"]) for b in base if "/post/" in b["url"]}
    weeks = defaultdict(lambda: {"pages": set(), "clicks": 0, "impressions": 0, "base_pages": set(), "base_clicks": 0, "base_impressions": 0})
    for r in weekly:
        u = norm(r["page"].split("#")[0])
        w = weeks[r["week"]]
        w["pages"].add(u); w["clicks"] += r["clicks"]; w["impressions"] += r["impressions"]
        if u in base_posts:
            w["base_pages"].add(u); w["base_clicks"] += r["clicks"]; w["base_impressions"] += r["impressions"]
    series = [{"week": wk, "pages_with_impressions": len(w["pages"]), "clicks": w["clicks"], "impressions": w["impressions"],
               "baseline_posts_with_impressions": len(w["base_pages"]), "baseline_clicks": w["base_clicks"],
               "baseline_impressions": w["base_impressions"]} for wk, w in sorted(weeks.items())]

    def window(rows):
        n = len(rows) or 1
        return {"weeks": [rows[0]["week"], rows[-1]["week"]] if rows else [], "n_weeks": len(rows),
                "avg_pages_with_impressions": round(sum(r["pages_with_impressions"] for r in rows) / n, 1),
                "avg_clicks": round(sum(r["clicks"] for r in rows) / n, 1),
                "avg_impressions": round(sum(r["impressions"] for r in rows) / n),
                "avg_baseline_posts_with_impressions": round(sum(r["baseline_posts_with_impressions"] for r in rows) / n, 1),
                "avg_baseline_clicks": round(sum(r["baseline_clicks"] for r in rows) / n, 1),
                "avg_baseline_impressions": round(sum(r["baseline_impressions"] for r in rows) / n)}

    before = [r for r in series if r["week"] < HUB_WEEK][-6:]
    after = series[-6:]
    return {"weekly": series, "before_hub": window(before), "latest": window(after)}


def baseline_timing(weekly: list[dict], base: list[dict], gsc: dict) -> dict:
    """For the posts Google was NOT indexing in August: when did the now-indexed ones start to appear?

    A page cannot earn an impression unless it is indexed, so the first week with impressions is the
    latest date it can have been indexed. Weeks start on Monday; the hub went live on Wed 2026-09-30,
    so the week of 09-28 is counted as "after".
    """
    state = {norm(u): v for u, v in gsc.items()}
    first: dict[str, str] = {}
    for r in sorted(weekly, key=lambda r: r["week"]):
        first.setdefault(norm(r["page"].split("#")[0]), r["week"])
    when, crawl = Counter(), Counter()
    for b in base:
        u = norm(b["url"])
        if "/post/" not in u:
            continue
        s = state.get(u, {})
        if s.get("coverageState") not in INDEXED:
            continue
        f = first.get(u)
        when["never seen in search" if not f else "before the hub" if f < HUB_WEEK else "after the hub"] += 1
        c = (s.get("lastCrawlTime") or "")[:10]
        crawl["last crawl after the hub" if c >= HUB_LIVE else "last crawl before the hub" if c else "no crawl date"] += 1
    return {"first_impressions": dict(when), "last_crawl": dict(crawl)}


def by_month(days: list[dict]) -> list[dict]:
    """Daily Search Analytics rows -> one row per calendar month, months with no row filled with zero."""
    tot = defaultdict(lambda: [0, 0])
    for r in days:
        tot[r["keys"][0][:7]][0] += r["impressions"]
        tot[r["keys"][0][:7]][1] += r["clicks"]
    if not tot:
        return []
    out, (y, mth) = [], map(int, min(tot).split("-"))
    while f"{y}-{mth:02d}" <= max(tot):
        k = f"{y}-{mth:02d}"
        out.append({"month": k, "impressions": tot[k][0] if k in tot else 0, "clicks": tot[k][1] if k in tot else 0})
        y, mth = (y + 1, 1) if mth == 12 else (y, mth + 1)
    return out


def markus_article(gsc: dict, m: dict, graph: dict) -> dict:
    s = {norm(u): v for u, v in gsc.items()}.get(MARKUS, {})
    days = sorted(m["by_week"], key=lambda r: r["keys"][0])

    def tot(rows):
        return {"clicks": sum(r["clicks"] for r in rows), "impressions": sum(r["impressions"] for r in rows)}

    y26 = [r for r in days if r["keys"][0] >= "2026-01-01"]
    return {
        "coverage": s.get("coverageState"), "last_crawl": s.get("lastCrawlTime"),
        "referring_urls": s.get("referringUrls", []),
        "first_day_with_impressions": days[0]["keys"][0] if days else None,
        "before_email_2026": tot([r for r in y26 if r["keys"][0] < EMAIL]),
        "since_email": tot([r for r in days if r["keys"][0] >= EMAIL]),
        "last_28_days": tot(days and [r for r in days if r["keys"][0] >= (date.fromisoformat(days[-1]["keys"][0]) - timedelta(days=27)).isoformat()]),
        "last_day_in_data": days[-1]["keys"][0] if days else None,
        "since_september": tot([r for r in days if r["keys"][0] >= "2026-09-01"]),
        "by_month": by_month(days),
        "queries_since_email": [{"query": r["keys"][0], "clicks": r["clicks"], "impressions": r["impressions"], "position": round(r["position"], 1)}
                                for r in sorted(m["queries_since_email"], key=lambda r: -r["impressions"])[:8]],
        "other_pages_linking_to_it": graph["markus_article_sources"],
    }


def main() -> None:
    crawl, wix, gsc = load("crawl.json"), load("wix_posts.json"), load("gsc_inspection.json")
    base, weekly, m = load("baseline_sheet.json"), load("gsc_weekly_pages.json"), load("gsc_markus.json")
    graph = link_graph(crawl)
    idx = index_status(crawl, wix, gsc, base)
    out = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "markus_claims": MARKUS_CLAIMS, "hub_live": HUB_LIVE, "email_date": EMAIL,
        "links": graph, "categories": categories(wix), "duplicates": duplicates(crawl, wix, gsc),
        "tools": tools(crawl), "index": idx, "search": search(weekly, base, idx),
        "baseline_timing": baseline_timing(weekly, base, gsc),
        "markus_article": markus_article(gsc, m, graph),
    }
    (HERE / "datapoints.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("search",)}, indent=1)[:200])
    print("wrote datapoints.json")


if __name__ == "__main__":
    main()
