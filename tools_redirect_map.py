"""Map each auto-generated Wix /tools/<slug> page to the official programs.* tool page.

Wix creates a dynamic CMS item page for every tool, which duplicates the real tool hosted on
programs.clearerthinking.org. Each wrapper's body links to its own program, so the mapping can be
read off the pages themselves rather than guessed from slugs.

Nav links (the same programs.* URLs on every page) are excluded by frequency, not by hardcoding.

Usage: python tools_redirect_map.py [--out PATH]
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import re
import urllib.parse
from pathlib import Path

import seo_hub_pages as hub

TOOLS_SITEMAP = hub.TOOLS_SITEMAP
# A programs.* URL appearing on this share of pages is site furniture, not the page's tool.
NAV_SHARE = 0.5


def programs_links(html: str) -> list[str]:
    """Absolute programs.* URLs in the page, query strings and fragments stripped."""
    found = re.findall(r'href="(https://programs\.clearerthinking\.org/[^"]+)"', html)
    return [urllib.parse.unquote(u).split("?")[0].split("#")[0].rstrip("/") for u in found]


def pick_target(candidates: list[str], nav: set[str]) -> tuple[str | None, list[str]]:
    """The page's own tool is the non-nav programs link. Returns (target, other_candidates)."""
    real = [u for u in dict.fromkeys(candidates) if u not in nav]
    if not real:
        return None, []
    return real[0], real[1:]


def fetch(url: str) -> tuple[str, str | None, str | None]:
    """Returns (url, html, error)."""
    try:
        return url, hub._fetch(url), None
    except Exception as e:  # noqa: BLE001
        return url, None, f"{type(e).__name__}: {e}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home() / "Downloads" / "wix_tools_redirect_map.json"))
    args = ap.parse_args()

    urls = [e["url"] for e in hub.parse_sitemap(hub._fetch(TOOLS_SITEMAP))]
    print(f"{len(urls)} /tools/ pages in the dynamic-tools sitemap", flush=True)

    pages: dict[str, str] = {}
    errors: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for i, (u, html, err) in enumerate(ex.map(fetch, urls), 1):
            if err:
                errors[u] = err
            else:
                pages[u] = html
            if i % 25 == 0:
                print(f"  fetched {i}/{len(urls)}", flush=True)

    # Identify site furniture by how often a programs.* URL shows up across all pages.
    freq: collections.Counter = collections.Counter()
    for html in pages.values():
        freq.update(set(programs_links(html)))
    nav = {u for u, n in freq.items() if n >= max(2, int(len(pages) * NAV_SHARE))}
    print(f"\ntreating {len(nav)} programs.* URLs as nav furniture: {sorted(nav)}")

    rows = []
    for u in urls:
        html = pages.get(u)
        if html is None:
            rows.append({"wix_url": u, "target": None, "note": f"fetch failed: {errors[u]}", "others": []})
            continue
        target, others = pick_target(programs_links(html), nav)
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        rows.append({
            "wix_url": u,
            "title": hub.clean_title(title.group(1)) if title else None,
            "target": target,
            "others": others,
            "note": "" if target else "NO programs.* link found on the page",
        })

    Path(args.out).write_text(json.dumps({"rows": rows, "nav": sorted(nav)}, indent=1))
    ok = sum(1 for r in rows if r["target"])
    amb = sum(1 for r in rows if r["others"])
    print(f"\nmapped {ok}/{len(rows)}; {amb} have more than one candidate; "
          f"{len(rows) - ok} need a manual decision")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
