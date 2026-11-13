"""The Flow tab's model: how GA4 sessions become the three columns of the diagram (first-touch source,
landing-page category, outcome). One source of truth for the page rules: the same expression tree is
compiled into GA4 dimension filters (so GA4 only ever returns light date x channel reports) and
evaluated in Python on (host, path) pairs, which is what tests/test_flow_model.py checks against.

Igor's choices (2026-11-13): the source is how we FIRST met the user (GA4 firstUserDefaultChannelGroup,
user-scoped acquisition); landing pages fall into Home, Articles, Tools and Other; outcomes are
"Email Submitted" (GA4 "Submitted Email", a tool finished) and "CT+ Sign Up" (GA4 plus_sign_up).
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

CHANNEL_KEY = "firstUserDefaultChannelGroup"
OUTCOME_EVENTS = {"Submitted Email": "Email Submitted", "plus_sign_up": "CT+ Sign Up"}

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

# Column 2, display order.
PAGE_ORDER = ["Home", "Articles", "Tools", "Other"]

# ---- page rules as an expression tree -------------------------------------------------------------
# Leaf: (field, op, value) with field in {"hostName", "landingPage"} and op in
# {"begins_with", "contains", "exact", "regexp"} (regexp = partial match, like GA4 PARTIAL_REGEXP).
# Nodes: ("and", [...]), ("or", [...]), ("not", expr). Matching is case-insensitive, as in GA4.
WEB = ("landingPage", "regexp", r"^/")  # a real page path; the email pixel and server events have none
HOME = ("and", [WEB, ("hostName", "begins_with", "www."), ("landingPage", "regexp", r"^/(home/?)?$")])
ARTICLES = ("and", [WEB, ("landingPage", "begins_with", "/post/")])
_NON_TOOL_PROGRAMS = ("landingPage", "regexp",
                      r"^/(coaching|mailing-list|dashboard|members-only|unanswered-questions|career-workshop|unsubscribe)")
TOOLS = ("and", [
    WEB, ("not", HOME), ("not", ARTICLES),
    ("or", [
        ("landingPage", "contains", "who_attracts_you"),
        ("landingPage", "begins_with", "/clearer-thinking-tools"),
        ("and", [("hostName", "begins_with", "programs."), ("not", _NON_TOOL_PROGRAMS)]),
    ]),
])
OTHER = ("and", [WEB, ("not", HOME), ("not", ARTICLES), ("not", TOOLS)])
PAGE_CATEGORIES: dict[str, Any] = {"Home": HOME, "Articles": ARTICLES, "Tools": TOOLS, "Other": OTHER}


def source_group(channel: str) -> str:
    return SOURCE_MAP.get(channel or "", "Other")


def _leaf_matches(leaf: tuple, host: str, path: str) -> bool:
    field, op, value = leaf
    subject = (host if field == "hostName" else path) or ""
    s, v = subject.lower(), value.lower()
    if op == "begins_with":
        return s.startswith(v)
    if op == "contains":
        return v in s
    if op == "exact":
        return s == v
    if op == "regexp":
        return re.search(value, subject, re.I) is not None
    raise ValueError(op)


def matches(expr: Any, host: str, path: str) -> bool:
    """Evaluate a rule tree on one (host, landing path) pair."""
    kind = expr[0]
    if kind == "and":
        return all(matches(e, host, path) for e in expr[1])
    if kind == "or":
        return any(matches(e, host, path) for e in expr[1])
    if kind == "not":
        return not matches(expr[1], host, path)
    return _leaf_matches(expr, host, path)


def page_category(host: str, path: str) -> str | None:
    """Home / Articles / Tools / Other, or None for a session with no landing page (not a web visit)."""
    for name, expr in PAGE_CATEGORIES.items():
        if matches(expr, host or "", path or ""):
            return name
    return None


def to_ga4_filter(expr: Any):
    """Compile a rule tree into a google.analytics.data_v1beta FilterExpression."""
    from google.analytics.data_v1beta.types import Filter, FilterExpression, FilterExpressionList

    kind = expr[0]
    if kind == "and":
        return FilterExpression(and_group=FilterExpressionList(expressions=[to_ga4_filter(e) for e in expr[1]]))
    if kind == "or":
        return FilterExpression(or_group=FilterExpressionList(expressions=[to_ga4_filter(e) for e in expr[1]]))
    if kind == "not":
        return FilterExpression(not_expression=to_ga4_filter(expr[1]))
    field, op, value = expr
    mt = {"begins_with": Filter.StringFilter.MatchType.BEGINS_WITH, "contains": Filter.StringFilter.MatchType.CONTAINS,
          "exact": Filter.StringFilter.MatchType.EXACT, "regexp": Filter.StringFilter.MatchType.PARTIAL_REGEXP}[op]
    return FilterExpression(filter=Filter(field_name=field, string_filter=Filter.StringFilter(match_type=mt, value=value)))


# ---- shaping GA4 rows into the snapshot ------------------------------------------------------------
def fold_sources(rows: list[dict], key: str = CHANNEL_KEY) -> dict[str, int]:
    """channel -> users rows summed into source groups (a user has one first-user channel, so exact)."""
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[source_group(r.get(key))] += int(r.get("totalUsers") or 0)
    return dict(out)


def flow_block(landing: dict[str, dict[str, int]], outcomes: dict[str, dict[str, dict[str, int]]]) -> dict:
    """One range's block: landing[page][source] = users, outcomes[page][outcome][source] = users."""
    return {
        "landing": [{"source": s, "page": p, "users": u}
                    for p in PAGE_ORDER for s, u in sorted(landing.get(p, {}).items(), key=lambda kv: -kv[1]) if u],
        "outcomes": [{"source": s, "page": p, "outcome": o, "users": u}
                     for p in PAGE_ORDER for o in OUTCOME_EVENTS.values()
                     for s, u in sorted(outcomes.get(p, {}).get(o, {}).items(), key=lambda kv: -kv[1]) if u],
    }
