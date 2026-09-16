"""Build the /all-articles and /all-tools link hubs that give Googlebot a crawlable path.

Why this exists: www.clearerthinking.org/blog exposes only 3 article links in its raw HTML and
/clearer-thinking-tools exposes zero tool links, because both galleries are drawn client-side.
Google therefore never follows a link to most posts and tools, which is the real cause of the
"Discovered - currently not indexed" and "URL is unknown to Google" buckets (see the
2026-09-16 sweep in reports/seo_indexing_impact_2026-09-16.html).

The output is plain HTML meant to be opened in a browser, selected, copied and pasted into a
NATIVE Wix text element. Do not paste it into a Wix HTML embed: those render in an iframe, so
the links would not count as links from the parent page and the whole exercise would be wasted.

Usage:
    python seo_hub_pages.py                 # regenerate both hubs into ~/Downloads
    python seo_hub_pages.py --out DIR       # write somewhere else
    python seo_hub_pages.py --no-cache      # ignore the title cache and refetch every page
"""
from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

BLOG_SITEMAP = "https://www.clearerthinking.org/blog-posts-sitemap.xml"
TOOLS_SITEMAP = (
    "https://www.clearerthinking.org/"
    "dynamic-tools_p_5c1ea742_9746_4bde_b765_d5e3f20bcaa5_0_5000-sitemap.xml"
)
UA = "Mozilla/5.0 (compatible; ClearerThinkingSEO/1.0; +https://www.clearerthinking.org/)"
HEAD_BYTES = 24_000  # title and datePublished both land in the first ~2KB
POLITE_DELAY = 0.8  # seconds between requests per worker; Wix returns 429 if pushed harder
CACHE = Path(__file__).parent / "reports" / "seo_hub_titles_cache.json"

# Wix appends this to most page titles; it is noise as anchor text.
TITLE_SUFFIXES = (" | Clearer Thinking", " - Clearer Thinking", " | ClearerThinking.org")


# --- pure helpers (unit-tested in tests/test_seo_hub_pages.py) -----------------------------
def clean_title(raw: str) -> str:
    """Unescape entities, drop the site-name suffix, collapse whitespace."""
    t = html.unescape(raw or "").strip()
    for suffix in TITLE_SUFFIXES:
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
            break
    return re.sub(r"\s+", " ", t)


def title_from_slug(url: str) -> str:
    """Fallback title when a page cannot be fetched: humanise the last URL segment."""
    slug = urllib.parse.unquote(url.rstrip("/").rsplit("/", 1)[-1])
    slug = re.sub(r"\.html?$", "", slug)
    slug = re.sub(r"-\d+$", "", slug)  # Wix duplicate suffix, e.g. "-1"
    words = re.split(r"[-_]+", slug)
    return " ".join(words).strip().capitalize() or url


def published_from_url(url: str) -> str | None:
    """Old-style CT post URLs carry the publish date: /post/2015/06/15/slug."""
    m = re.search(r"/post/(\d{4})/(\d{2})/(\d{2})/", url)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def year_of(item: dict) -> str:
    """Best available year for grouping, preferring the publish date over lastmod."""
    for key in ("published", "lastmod"):
        v = item.get(key)
        if v and re.match(r"^\d{4}", v):
            return v[:4]
    return "Undated"


def group_by_year(items: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group newest year first; 'Undated' always sorts last. Titles sorted within a year."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        buckets[year_of(it)].append(it)
    years = sorted((y for y in buckets if y != "Undated"), reverse=True)
    if "Undated" in buckets:
        years.append("Undated")
    return [(y, sorted(buckets[y], key=lambda i: i["title"].lower())) for y in years]


def render_links(items: list[dict]) -> str:
    """One <p> per link. Wix keeps paragraph-level links intact on paste."""
    return "\n".join(
        f'<p><a href="{html.escape(i["url"])}">{html.escape(i["title"])}</a></p>'
        for i in items
    )


def render_hub(heading: str, intro: str, sections: list[tuple[str, list[dict]]]) -> str:
    """The full paste-me document. Content only: no instructions, no chrome."""
    body = [f"<h1>{html.escape(heading)}</h1>", f"<p>{html.escape(intro)}</p>"]
    for name, items in sections:
        if name:
            body.append(f"<h2>{html.escape(name)}</h2>")
        body.append(render_links(items))
    return (
        "<!doctype html>\n<html lang=en>\n<head><meta charset=utf-8>\n"
        f"<title>{html.escape(heading)}</title>\n"
        "<style>body{max-width:820px;margin:40px auto;padding:0 20px;"
        "font:16px/1.7 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#16181d}"
        "h1{font-size:28px;margin:0 0 8px}h2{font-size:18px;margin:34px 0 10px;color:#6b7280}"
        "p{margin:0 0 7px}a{color:#1d63d1;text-decoration:none}a:hover{text-decoration:underline}"
        "</style>\n</head>\n<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )


# --- fetching -----------------------------------------------------------------------------
def parse_sitemap(xml: str) -> list[dict]:
    """Return [{url, lastmod}] for every <url> entry in a sitemap document."""
    out = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        if not loc:
            continue
        lastmod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        out.append({"url": loc.group(1).strip(), "lastmod": lastmod.group(1).strip() if lastmod else None})
    return out


def _fetch(url: str, limit: int | None = None, attempts: int = 6) -> str:
    """GET a URL, reading at most `limit` bytes, backing off on Wix's 429 rate limiting.

    Wix throttles aggressively once a burst has been seen, and the penalty outlives the burst,
    so the backoff has to be generous rather than clever.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read(limit) if limit else r.read()
            return raw.decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
            wait = float(e.headers.get("Retry-After") or 0) or 5 * (2 ** attempt)
            time.sleep(min(wait, 120))
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last = e
            time.sleep(POLITE_DELAY * (2 ** attempt))
    raise last  # type: ignore[misc]


def fetch_sitemap(url: str) -> list[dict]:
    return parse_sitemap(_fetch(url))


def page_meta(url: str) -> dict:
    """Read only the head of the page: enough for <title> and datePublished."""
    try:
        head = _fetch(url, limit=HEAD_BYTES)
    except Exception as e:  # noqa: BLE001 - one bad page must not sink the run
        return {"title": None, "published": None, "error": f"{type(e).__name__}: {e}"}
    time.sleep(POLITE_DELAY)
    t = re.search(r"<title[^>]*>(.*?)</title>", head, re.S)
    d = re.search(r'"datePublished"\s*:\s*"([^"]+)"', head)
    return {
        "title": clean_title(t.group(1)) if t else None,
        "published": d.group(1)[:10] if d else None,
        "error": None,
    }


def enrich(entries: list[dict], use_cache: bool = True, workers: int = 2) -> list[dict]:
    """Attach a title and publish date to each sitemap entry, caching across runs."""
    cache = {}
    if use_cache and CACHE.exists():
        # Only successful lookups are worth keeping; a cached failure would be permanent.
        cache = {k: v for k, v in json.loads(CACHE.read_text()).items() if v.get("title")}
    todo = [e["url"] for e in entries if e["url"] not in cache]
    print(f"  {len(entries)} URLs, {len(todo)} to fetch, {len(entries) - len(todo)} cached", flush=True)

    if todo:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            for i, (u, meta) in enumerate(zip(todo, ex.map(page_meta, todo)), 1):
                if meta.get("title"):
                    cache[u] = meta
                if i % 100 == 0:
                    print(f"    fetched {i}/{len(todo)}", flush=True)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True))

    failed = 0
    out = []
    for e in entries:
        meta = cache.get(e["url"], {})
        if not meta.get("title"):
            failed += 1
        out.append({
            "url": e["url"],
            "title": meta.get("title") or title_from_slug(e["url"]),
            "published": meta.get("published") or published_from_url(e["url"]),
            "lastmod": e.get("lastmod"),
        })
    if failed:
        print(f"  [warn] {failed} pages had no usable <title>; fell back to the URL slug", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path.home() / "Downloads"))
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()

    print("Blog posts:")
    posts = enrich(fetch_sitemap(BLOG_SITEMAP), use_cache=not args.no_cache)
    blog_html = render_hub(
        "All Clearer Thinking articles",
        f"Every article we have published, {len(posts)} in total, newest year first.",
        group_by_year(posts),
    )
    blog_file = out_dir / f"all-articles_PASTE-INTO-WIX_{stamp}.html"
    blog_file.write_text(blog_html)
    print(f"  -> {blog_file}  ({len(posts)} links)")

    print("Tools:")
    tools = enrich(fetch_sitemap(TOOLS_SITEMAP), use_cache=not args.no_cache)
    tools_sorted = sorted(tools, key=lambda i: i["title"].lower())
    tools_html = render_hub(
        "All Clearer Thinking tools",
        f"Every free tool and mini-course we have built, {len(tools)} in total, listed A to Z.",
        [("", tools_sorted)],
    )
    tools_file = out_dir / f"all-tools_PASTE-INTO-WIX_{stamp}.html"
    tools_file.write_text(tools_html)
    print(f"  -> {tools_file}  ({len(tools)} links)")


if __name__ == "__main__":
    main()
