"""Fetch www.clearerthinking.org the way Googlebot does and record what each page links to.

Writes data/crawl.json: one record per page with its status, canonical, robots meta, title and the CT
blog posts it links to through a real <a href> in the RAW HTML (nothing is rendered, so client-side
galleries count for nothing, exactly as for a crawler that does not scroll).

Resumable: pages already in data/crawl.json with a 200 are skipped. Wix answers bursts with 429s whose
penalty outlives the burst, so this stays at 4 workers with a pause each.

    python crawl_site.py            # everything
    python crawl_site.py --tools    # only the /tools/ redirect check (slow, one at a time)
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

import lib  # noqa: E402
import seo_hub_pages as hub  # noqa: E402

OUT = HERE / "data" / "crawl.json"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
SITE = "https://www.clearerthinking.org"
STUDIES_SITEMAP = f"{SITE}/dynamic-studies_p_3b681dc2_1f98_463d_b4eb_990cf680404a_0_5000-sitemap.xml"
EXTRA = [f"{SITE}/", f"{SITE}/blog", f"{SITE}/clearer-thinking-tools"] + \
        [f"{SITE}/blog/page/{n}" for n in (2, 3, 4, 5, 50, 100, 101)]


def get(url: str, follow: bool = True, attempts: int = 6) -> requests.Response:
    for attempt in range(attempts):
        try:
            r = requests.get(url, headers={"User-Agent": GOOGLEBOT}, timeout=90, allow_redirects=follow)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(float(r.headers.get("Retry-After") or 0) or 5 * 2 ** attempt, 120))
            continue
        return r
    raise RuntimeError(f"gave up on {url}")


def record(url: str, group: str) -> dict:
    try:
        r = get(url)
    except Exception as e:  # noqa: BLE001 - one bad page must not sink the crawl
        return {"url": url, "group": group, "status": None, "error": str(e)}
    time.sleep(hub.POLITE_DELAY)
    page = r.text if r.status_code == 200 else ""
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S)
    published = re.search(r'"datePublished"\s*:\s*"([^"]+)"', page)
    hrefs = lib.anchors(page)
    return {
        "url": url, "group": group, "status": r.status_code, "final_url": r.url,
        "canonical": lib.canonical(page), "robots": lib.robots_meta(page),
        "title": hub.clean_title(title.group(1)) if title else None,
        "published": published.group(1)[:10] if published else None,
        "post_links": lib.post_links(page),
        "category_links": sorted({h.split("?")[0] for h in hrefs if "/blog/categories/" in h}),
        "blog_page_links": sorted({h.split("?")[0] for h in hrefs if "/blog/page/" in h}),
        "n_anchors": len(hrefs), "bytes": len(r.content),
    }


def load() -> dict:
    return json.loads(OUT.read_text()) if OUT.exists() else {"pages": {}, "tools": {}, "sitemaps": {}}


def crawl_pages(state: dict) -> None:
    posts = hub.fetch_sitemap(hub.BLOG_SITEMAP)
    cats = hub.fetch_sitemap(f"{SITE}/blog-categories-sitemap.xml")
    pages = hub.fetch_sitemap(f"{SITE}/pages-sitemap.xml")
    studies = hub.fetch_sitemap(STUDIES_SITEMAP)
    state["sitemaps"] = {"posts": posts, "categories": cats, "pages": pages, "studies": studies}
    todo = [(e["url"], "post") for e in posts] + [(e["url"], "category") for e in cats] + \
           [(e["url"], "page") for e in pages] + [(e["url"], "study") for e in studies] + \
           [(u, "extra") for u in EXTRA]
    todo = [(u, g) for u, g in dict(todo).items() if state["pages"].get(u, {}).get("status") != 200]
    print(f"{len(posts)} posts, {len(cats)} categories, {len(pages)} pages, {len(studies)} studies; "
          f"{len(todo)} to fetch", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for n, rec in enumerate(ex.map(lambda t: record(*t), todo), 1):
            state["pages"][rec["url"]] = rec
            if n % 50 == 0 or n == len(todo):
                OUT.write_text(json.dumps(state))
                print(f"  {n}/{len(todo)}", flush=True)
    OUT.write_text(json.dumps(state))


def crawl_tools(state: dict) -> None:
    """Where does each sitemap-listed /tools/<slug> go? No redirect following, one request at a time."""
    tools = hub.fetch_sitemap(hub.TOOLS_SITEMAP)
    state["sitemaps"]["tools"] = tools
    for n, e in enumerate(tools, 1):
        u = e["url"]
        if u in state["tools"]:
            continue
        try:
            r = get(u, follow=False)
            state["tools"][u] = {"status": r.status_code, "location": r.headers.get("Location")}
        except Exception as ex:  # noqa: BLE001
            state["tools"][u] = {"status": None, "error": str(ex)}
        time.sleep(1.5)
        if n % 20 == 0:
            OUT.write_text(json.dumps(state))
            print(f"  tools {n}/{len(tools)}", flush=True)
    OUT.write_text(json.dumps(state))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", action="store_true")
    args = ap.parse_args()
    OUT.parent.mkdir(exist_ok=True)
    st = load()
    if args.tools:
        crawl_tools(st)
    else:
        crawl_pages(st)
    print("done", flush=True)
