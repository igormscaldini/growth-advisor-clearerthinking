"""Pure helpers for the blog discoverability follow-up (no network). Tested in tests/test_blog_discoverability.py."""
from __future__ import annotations

import html
import re
from collections import defaultdict
from urllib.parse import unquote, urlsplit

WWW = "www.clearerthinking.org"


def anchors(page: str) -> list[str]:
    """Every <a href> value in a raw HTML document, entity-decoded, in document order."""
    return [html.unescape(h) for h in re.findall(r'<a\b[^>]*?\bhref="([^"]*)"', page)]


def post_url(href: str) -> str | None:
    """Normalised https://www.clearerthinking.org/post/<slug> for a CT blog post link, else None.

    Drops the query, the fragment and a trailing slash, and percent-decodes the slug so that the sitemap
    form and the form used inside an article compare equal.
    """
    parts = urlsplit(href.strip())
    if parts.netloc.lower() not in (WWW, "clearerthinking.org"):
        return None
    path = unquote(parts.path).rstrip("/")
    if not path.startswith("/post/") or len(path) <= len("/post/"):
        return None
    return f"https://{WWW}{path}"


def post_links(page: str) -> list[str]:
    """Distinct CT post URLs linked from a page with a real <a href>, in first-seen order."""
    seen: dict[str, None] = {}
    for h in anchors(page):
        u = post_url(h)
        if u:
            seen.setdefault(u)
    return list(seen)


def canonical(page: str) -> str | None:
    m = re.search(r'<link[^>]+rel="canonical"[^>]*href="([^"]+)"', page) or \
        re.search(r'<link[^>]+href="([^"]+)"[^>]*rel="canonical"', page)
    return html.unescape(m.group(1)) if m else None


def robots_meta(page: str) -> str | None:
    m = re.search(r'<meta[^>]+name="robots"[^>]*content="([^"]+)"', page)
    return m.group(1) if m else None


def numbered_duplicates(urls: list[str]) -> list[tuple[str, str]]:
    """(base, copy) pairs where `copy` is `base` plus a -<n> suffix and both exist.

    Wix appends -1, -2 ... when a post is created with a slug that is already taken, so this is the
    candidate list for duplicate posts. A legitimate "part-2" style slug also matches, so callers must
    confirm each pair (same title or same body) before calling it a duplicate.
    """
    have = set(urls)
    out = []
    for u in sorted(have):
        m = re.fullmatch(r"(.+)-(\d+)", u)
        if m and m.group(1) in have:
            out.append((m.group(1), u))
    return out


def sitewide_links(pages: dict[str, list[str]], share: float = 0.5) -> set[str]:
    """Targets linked from more than `share` of the pages: menu, footer and "recent posts" chrome."""
    if not pages:
        return set()
    counts: dict[str, int] = defaultdict(int)
    for links in pages.values():
        for t in set(links):
            counts[t] += 1
    return {t for t, n in counts.items() if n / len(pages) > share}


def inbound(pages: dict[str, list[str]], ignore_sources: set[str] = frozenset(),
            ignore_targets: set[str] = frozenset()) -> dict[str, set[str]]:
    """target -> set of source pages linking to it. Self links never count."""
    out: dict[str, set[str]] = defaultdict(set)
    for src, links in pages.items():
        if src in ignore_sources:
            continue
        for t in links:
            if t != src and t not in ignore_targets:
                out[t].add(src)
    return out
