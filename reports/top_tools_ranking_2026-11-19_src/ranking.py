"""Pure rules for the top-tools ranking: which GA4 page paths count for which tool, and the ranking itself.

A tool = one card on https://www.clearerthinking.org/clearer-thinking-tools that lives on programs.clearerthinking.org.
Its pages = its own path in any spelling (trailing slash, .html, index.html, capitals), its sub-paths and its older
addresses (ALIASES). Report pages at another address (personality_report.html, /rationality-report/...) do not count:
the metric is "people who opened the tool". Partner-branded copies (/p/<partner>/<tool>/...) are told apart from the
tool's own pages so a ranking can leave them out or add them.
"""
from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm"))
from coaching_fab_tools_list import TOOLS_HOST, normalize_path  # noqa: E402  (the one normalizer of tool paths)

# Older address of a tool's page that still gets visits: normalized old path -> normalized current path.
ALIASES = {"/personality": "/personality-test"}
# Partner copies whose slug is not simply the tool's own path with hyphens: slug -> the tool's normalized path.
PARTNER_SLUGS = {"rationality-test": "/how_rational_are_you_really_take_the_test"}
PARTNER_RE = re.compile(r"^/p/[^/]+/([^/]+)(?:/.*)?$")
# Tools left out of the ranking at Igor's request (2026-11-19): normalized path -> name shown in the page's notes.
EXCLUDED = {"/who_attracts_you_study": "Who Attracts You?", "/cognitive-test-intro": "the Cognitive Assessment"}


def base_of(url_or_path: str) -> str:
    """The key of a tool: the normalized path of its page, old addresses mapped to the current one."""
    path = normalize_path(urllib.parse.unquote(urllib.parse.urlsplit(url_or_path).path))
    return ALIASES.get(path, path)


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def tools_from_cards(cards: list[tuple[str, str]], excluded=EXCLUDED) -> tuple[dict[str, dict], list[str]]:
    """({base: {"name", "url"}} for the cards on TOOLS_HOST minus `excluded`, [titles of the cards hosted elsewhere])."""
    tools, elsewhere = {}, []
    for title, link in cards:
        if urllib.parse.urlsplit(link).netloc.lower() != TOOLS_HOST:
            elsewhere.append(title)
            continue
        base = base_of(link)
        if base and base not in excluded:
            tools.setdefault(base, {"name": title, "url": link})
    return tools, elsewhere


def classify(path: str, bases) -> tuple[str, str] | None:
    """(tool base, "own" | "partner") for one GA4 pagePath, or None when the page belongs to no tool."""
    p = normalize_path(path)
    m = PARTNER_RE.match(p)
    if m:
        by_key = {_key(b): b for b in bases}
        base = PARTNER_SLUGS.get(m.group(1)) or by_key.get(_key(m.group(1)))
        return (base, "partner") if base in bases else None
    while p:
        base = ALIASES.get(p, p)
        if base in bases:
            return base, "own"
        p = p.rsplit("/", 1)[0]
    return None


def group_paths(rows: list[tuple[str, int]], bases) -> dict[str, dict[str, dict[str, int]]]:
    """{base: {"own": {path: users}, "partner": {path: users}}} from (pagePath, users) rows."""
    out = {b: {"own": {}, "partner": {}} for b in bases}
    for path, users in rows:
        hit = classify(path, bases)
        if hit:
            out[hit[0]][hit[1]][path] = users
    return out


def bounds(path_users: dict[str, int]) -> tuple[int, int]:
    """(lowest, highest) possible number of distinct users across pages whose separate user counts are known:
    everyone on the smaller pages also saw the biggest one, or nobody saw two of them."""
    values = list(path_users.values())
    return (max(values), sum(values)) if values else (0, 0)


def pick_candidates(upper: dict[str, int], n: int, extra: int = 10) -> list[str]:
    """The n + extra tools with the highest upper bound: the only ones that need an exact (deduplicated) count."""
    return sorted(upper, key=lambda b: (-upper[b], b))[:n + extra]


def rank(users: dict[str, int], n: int = 10) -> list[tuple[str, int]]:
    """Top n (base, users), most users first; ties in alphabetical order of the key."""
    return sorted(users.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def ranking_is_certain(exact: dict[str, int], upper_of_the_rest: dict[str, int], n: int = 10) -> bool:
    """True when no tool WITHOUT an exact count could belong in the top n: the n-th exact count beats (or equals)
    the highest upper bound among the rest."""
    top = rank(exact, n)
    if len(top) < n:
        return not upper_of_the_rest
    return top[-1][1] >= max(upper_of_the_rest.values(), default=0)
