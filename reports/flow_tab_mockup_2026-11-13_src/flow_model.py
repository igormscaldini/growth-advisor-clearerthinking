"""Pure grouping for the Flow tab: GA4 rows (first-user channel, host, landing page, users) into the
three columns of the diagram. No I/O. fetch_data.py applies it; build.py renders the result.

Igor's choices (2026-11-13): the source is how we FIRST met the user (GA4 firstUserDefaultChannelGroup,
user-scoped acquisition), and landing pages fall into four categories: Home, Articles, Tools, Other.
"""
from __future__ import annotations

from collections import defaultdict

CHANNEL_KEY = "firstUserDefaultChannelGroup"

# Column 1: GA4 channel groups folded into the sources Igor reads, in a FIXED order (the categorical
# palette follows this order; a filter never repaints a survivor).
SOURCE_ORDER = ["Organic Search", "Direct", "Paid Media", "Email", "Social", "Referral", "AI Assistant", "Other"]
SOURCE_MAP = {
    "Organic Search": "Organic Search",
    "Direct": "Direct",
    "Paid Search": "Paid Media", "Paid Social": "Paid Media", "Paid Other": "Paid Media", "Paid Video": "Paid Media",
    "Paid Shopping": "Paid Media", "Display": "Paid Media", "Cross-network": "Paid Media",
    "Email": "Email",
    "Organic Social": "Social", "Organic Video": "Social",
    "Referral": "Referral",
    "AI Assistant": "AI Assistant",
}

# Column 2: landing pages in four categories, display order.
PAGE_ORDER = ["Home", "Articles", "Tools", "Other"]

# programs.* paths that are not tools (coaching page, list management, member dashboard, prize form).
NON_TOOL_PROGRAMS_PREFIXES = ("/coaching", "/mailing-list", "/dashboard", "/members-only", "/unanswered-questions",
                              "/career-workshop", "/unsubscribe")


def source_group(channel: str) -> str:
    return SOURCE_MAP.get(channel or "", "Other")


def page_family(host: str, path: str) -> str | None:
    """Home (the www homepage), Articles (every /post/), Tools (programs.* tool pages, the tools gallery and
    the www copy of a tool), Other (coaching, CT+, podcast, list pages, sessions with no landing page
    recorded). None = not a web session at all (the email-open pixel and server-side purchase events)."""
    host = (host or "").strip()
    path = (path or "").strip()
    if not host or host == "(not set)":
        return None
    if not path or path == "(not set)":
        return "Other"  # a real web session (host known) whose first hit was not a page view
    p = path.lower()
    if host.startswith("www.") and p in ("/", "/home"):
        return "Home"
    if p.startswith("/post/"):
        return "Articles"
    if "who_attracts_you" in p or p.startswith("/clearer-thinking-tools"):
        return "Tools"
    if host.startswith("programs.") and not p.startswith(NON_TOOL_PROGRAMS_PREFIXES):
        return "Tools"  # includes the programs root, which redirects to the tools gallery
    return "Other"


def group_landing(rows: list[dict], channel_key: str = CHANNEL_KEY) -> tuple[dict[tuple[str, str], int], int]:
    """(source, page category) -> users, plus the users dropped for not being web sessions."""
    out: dict[tuple[str, str], int] = defaultdict(int)
    dropped = 0
    for r in rows:
        fam = page_family(r.get("hostName"), r.get("landingPage"))
        users = int(r.get("totalUsers") or 0)
        if fam is None:
            dropped += users
            continue
        out[(source_group(r.get(channel_key)), fam)] += users
    return dict(out), dropped


def group_outcomes(rows: list[dict], events: dict[str, str], channel_key: str = CHANNEL_KEY) -> dict[tuple[str, str, str], int]:
    """(source, page category, outcome label) -> users who fired the event in such a session."""
    out: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        label = events.get(r.get("eventName") or "")
        fam = page_family(r.get("hostName"), r.get("landingPage"))
        if label is None or fam is None:
            continue
        out[(source_group(r.get(channel_key)), fam, label)] += int(r.get("totalUsers") or 0)
    return dict(out)
