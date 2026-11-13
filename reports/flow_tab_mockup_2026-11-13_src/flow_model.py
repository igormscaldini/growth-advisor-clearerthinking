"""Pure grouping for the Flow tab: GA4 rows (session channel, host, landing page, users) into the
three columns of the diagram. No I/O. fetch_data.py applies it; build.py renders the result."""
from __future__ import annotations

from collections import defaultdict

# Column 1: GA4 default channel groups folded into the sources Igor reads, in a FIXED order (the
# categorical palette follows this order; a filter never repaints a survivor).
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

# Column 2: landing pages folded into families, in display order.
PAGE_ORDER = ["Who Attracts You study", "Homepage", "Personality Test", "Rationality Test", "Other tools",
              "Tools gallery", "Articles", "Coaching page", "CT+ page", "Cognitive Assessment page", "Podcast", "Other pages"]


def source_group(channel: str) -> str:
    return SOURCE_MAP.get(channel or "", "Other")


def page_family(host: str, path: str) -> str | None:
    """None = not a web landing (the email-open pixel and server-side purchase events have no page)."""
    host = (host or "").strip()
    path = (path or "").strip()
    if not host or host == "(not set)" or not path or path == "(not set)":
        return None
    p = path.lower()
    if "who_attracts_you" in p:
        return "Who Attracts You study"
    if host.startswith("podcast."):
        return "Podcast"
    if p == "/" and host.startswith("www."):
        return "Homepage"
    if p.startswith("/personality") or p.startswith("/personality_report"):
        return "Personality Test"
    if "how_rational_are_you" in p:
        return "Rationality Test"
    if p.startswith("/cognitive-test") or p.startswith("/cognitive_test"):
        return "Cognitive Assessment page"
    if p.startswith("/coaching"):
        return "Coaching page"
    if p.startswith("/plus"):
        return "CT+ page"
    if p.startswith("/clearer-thinking-tools"):
        return "Tools gallery"
    if p.startswith("/post/"):
        return "Articles"
    if host.startswith("programs.") and (p.endswith(".html") or p.count("/") == 1) and p not in ("/",):
        return "Other tools"
    return "Other pages"


def group_landing(rows: list[dict]) -> tuple[dict[tuple[str, str], int], int]:
    """(source, page family) -> users, plus the users dropped for having no landing page."""
    out: dict[tuple[str, str], int] = defaultdict(int)
    dropped = 0
    for r in rows:
        fam = page_family(r.get("hostName"), r.get("landingPage"))
        users = int(r.get("totalUsers") or 0)
        if fam is None:
            dropped += users
            continue
        out[(source_group(r.get("sessionDefaultChannelGroup")), fam)] += users
    return dict(out), dropped


def group_outcomes(rows: list[dict], events: dict[str, str]) -> dict[tuple[str, str, str], int]:
    """(source, page family, outcome label) -> users who fired the event in such a session."""
    out: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        label = events.get(r.get("eventName") or "")
        fam = page_family(r.get("hostName"), r.get("landingPage"))
        if label is None or fam is None:
            continue
        out[(source_group(r.get("sessionDefaultChannelGroup")), fam, label)] += int(r.get("totalUsers") or 0)
    return dict(out)
