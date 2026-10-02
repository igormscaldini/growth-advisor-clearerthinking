"""Daily health check of the Clearer Thinking site. Emails Igor only when something is wrong.

Six checks, each ending PASS, FAIL or UNKNOWN (reported as "COULD NOT CHECK"):

  ga4       each of the three key events fired yesterday site-wide, and is firing right now
  tools     each of CT's top tools still fires every event its own history says it should, and a
            tool that went completely silent still has a working page with the tracking script
  pages     the homepage and every page linked in the site menu load
  links     the Sign Up buttons on /plus and /coaching point at the CT+ subscribe program
  checkout  that program really ends on a Stripe checkout page, for each tier
  beehiiv   the API is still creating subscribers

    python site_health_check.py                 # run everything, email if anything is not PASS
    python site_health_check.py --dry-run       # print the result, send nothing
    python site_health_check.py --only links,checkout
    python site_health_check.py --heartbeat     # also send the weekly summary (automatic on Mondays)

A check that does not pass is run a second time before it counts: Wix rate limiting and slow
GuidedTrack responses both produce convincing false negatives on a single attempt.

The process exits non-zero whenever a check did not pass or the email could not be sent. That is
deliberate: the run's conclusion is the only record the weekly summary reads, and GitHub's own
"workflow failed" notification is the backstop when Gmail itself is what broke (the same Google
token powers both the GA4 check and the sending).

The checkout check creates REAL runs of GuidedTrack program 34235 and real (unpaid, self-expiring)
Stripe Checkout Sessions, three a day. They are tagged src=healthcheck and use HEALTHCHECK_EMAIL:
exclude both whenever that program's runs are counted as sign-up clicks.

Every rule lives in a pure function (evaluate_* / *_problem*), tested in
tests/test_site_health_check.py; the thresholds are the constants below.
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
STATUS_LABEL = {PASS: "OK", FAIL: "FAILED", UNKNOWN: "COULD NOT CHECK"}

# ---- GA4 -------------------------------------------------------------------------------------
KEY_EVENTS = ("Viewed Privacy Policy", "Accepted Privacy Policy", "Submitted Email")
GA4_TZ = "America/New_York"   # the property's clock; "yesterday" is a US Eastern day
BASELINE_DAYS = 14
IGNORED_HOSTS = frozenset({"localhost"})
# Every GA4 rule asks "did an event that should fire, fire at all?", never "is volume down?".
# Backtest on Oct 2025 - Sep 2026: a "below 30% of the trailing median" rule raised 18 false
# alarms, every one an ad or partner campaign ending, and no real break. GA4 alone cannot tell a
# tool that lost its visitors from one whose tracking died (both read as zero), so a tool that goes
# completely silent is judged by fetching its page: see evaluate_tools.
# Realtime (last 30 minutes) only speaks when traffic is high enough for a zero to mean something.
REALTIME_WINDOWS_PER_DAY = 48
REALTIME_MIN_EXPECTED = 40    # key events expected per window before "all zero" is a failure
REALTIME_MIN_PEER = 30        # one event at 0 fails only if another reached this in the window
TOP_TOOLS = 10
# A tool's event is "expected" once its trailing median reaches this. Events a tool never fires
# (the Ultimate Personality Test has had no Viewed Privacy Policy since Sep 2025, intentionally;
# the paid Cognitive Assessment has no Submitted Email) have a baseline of 0 and are never flagged.
TOOL_MIN_BASELINE = 30
# Partner campaign pages (/p/<partner>/...) go silent whenever the partner's campaign ends, which
# GA4 cannot tell apart from broken tracking, so the per-tool check covers CT's own tools only.
PARTNER_PATH = "/p/"
# The GuidedTrack-to-GA4 bridge script. Every tool page loads it (all 25 busiest did on 2026-10-02),
# and it is what loads GTM, so a page without it records nothing at all.
TRACKING_SCRIPT = "google_analytics_guidedtrack_trigger"

# ---- Pages -----------------------------------------------------------------------------------
HOME = "https://www.clearerthinking.org"
PLUS = HOME + "/plus"
COACHING = HOME + "/coaching"
REQUIRED_PAGES = (HOME, PLUS, COACHING)   # checked even if they drop out of the menu
MENU_NAV_LABEL = "Site"                   # aria-label of the Wix menu <nav>
MIN_MENU_LINKS = 15                       # 21 on 2026-10-01; fewer means the menu shrank or moved
MIN_PAGE_BYTES = 500                      # the smallest healthy menu page is about 1 KB
PAGE_PAUSE_SECONDS = 0.6                  # Wix 429s on bursts and the penalty outlives them
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# ---- Sign-up links and checkout --------------------------------------------------------------
SUBSCRIBE_RUN = "https://www.guidedtrack.com/programs/1pvomgo/run"   # GT program 34235
TIERS = ("supporter", "explorer", "navigator")
SIGNUP_PAGES = {PLUS: frozenset(TIERS), COACHING: frozenset({"navigator"})}   # tiers each must offer
ALLOWED_LINK_PARAMS = frozenset({"p", "src"})
HEALTHCHECK_EMAIL = "igormscaldini+healthcheck@gmail.com"
HEALTHCHECK_SRC = "healthcheck"
STRIPE_CHECKOUT = "https://checkout.stripe.com/"
PRICE_RE = re.compile(r"\d+[.,]\d{2}")

# ---- beehiiv ---------------------------------------------------------------------------------
API_CHANNEL = "api"
MAX_API_SUB_AGE_HOURS = 3
# API subscribers per GA4 Submitted Email. Since the tools began writing to beehiiv (2026-03-09)
# the daily ratio's low was 0.25, on one GA4 spike day (2026-03-19); otherwise 0.46 and up. A broken
# pipe gives a ratio near 0. (Backtested on the committed new-subscriber cache: all non-import
# channels by UTC day, of which API subscribers are about 98%.)
MIN_SHARE_OF_SUBMITTED = 0.20
MIN_SUBMITTED_FOR_RATIO = 50    # below this the ratio is too noisy to judge
BEEHIIV_MAX_PAGES = 150         # 15k subscribers; a walk that long means paging is broken

RETRY_WAIT_SECONDS = 90
NAMES = {
    "ga4": "GA4 key events (site-wide)",
    "tools": "GA4 key events (per tool)",
    "pages": "Site and menu pages",
    "links": "Sign-up links on /plus and /coaching",
    "checkout": "Stripe checkout",
    "beehiiv": "beehiiv API subscribers",
}
EMAIL_TAG = "[CT site check]"
WORKFLOW_FILE = "site-health-check.yml"


@dataclass
class CheckResult:
    name: str
    status: str
    summary: str
    problems: list = field(default_factory=list)


def _n(x: float) -> str:
    return f"{x:,.0f}"


# =============================================================================
# GA4
# =============================================================================
def ga4_yesterday(now: Optional[datetime] = None) -> date:
    from zoneinfo import ZoneInfo

    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(GA4_TZ)).date() - timedelta(days=1)


def baseline_days(day: date) -> list:
    return [(day - timedelta(days=i)).isoformat() for i in range(1, BASELINE_DAYS + 1)]


def baseline_medians(daily: dict, day: date) -> dict:
    """Median of each key event over the BASELINE_DAYS before `day`. A missing day counts as 0:
    GA4 returns no row at all for an event that did not fire."""
    return {ev: statistics.median(daily.get(d, {}).get(ev, 0) for d in baseline_days(day))
            for ev in KEY_EVENTS}


def site_totals(by_tool: dict) -> dict:
    """{tool: {date: {event: n}}} -> {date: {event: n}} summed over every tool."""
    out: dict = {}
    for days in by_tool.values():
        for d, events in days.items():
            bucket = out.setdefault(d, {})
            for ev, n in events.items():
                bucket[ev] = bucket.get(ev, 0) + n
    return out


def silent_event_problems(daily: dict, day: date) -> list:
    """Site-wide rule: a key event that did not fire once all day is broken."""
    medians = baseline_medians(daily, day)
    counts = daily.get(day.isoformat(), {})
    return [f"{ev}: 0 events on {day} (trailing {BASELINE_DAYS}-day median {_n(medians[ev])})"
            for ev in KEY_EVENTS if counts.get(ev, 0) == 0]


def realtime_problems(realtime: dict, medians: dict) -> list:
    """Last-30-minutes rule. Silent when traffic is too low for a zero to be meaningful."""
    counts = {ev: realtime.get(ev, 0) for ev in KEY_EVENTS}
    expected = sum(medians.values()) / REALTIME_WINDOWS_PER_DAY
    if sum(counts.values()) == 0:
        if expected >= REALTIME_MIN_EXPECTED:
            return [f"no key event at all in the last 30 minutes (about {_n(expected)} expected)"]
        return []
    peer = max(counts, key=counts.get)
    if counts[peer] < REALTIME_MIN_PEER:
        return []
    return [f"{ev}: 0 in the last 30 minutes while {peer} fired {_n(counts[peer])} times"
            for ev in KEY_EVENTS if counts[ev] == 0]


def evaluate_ga4(daily: dict, realtime: Optional[dict], day: date) -> CheckResult:
    problems = silent_event_problems(daily, day)
    if realtime is not None:
        problems += realtime_problems(realtime, baseline_medians(daily, day))
    counts = daily.get(day.isoformat(), {})
    summary = ", ".join(f"{ev.split()[0]} {_n(counts.get(ev, 0))}" for ev in KEY_EVENTS) + f" on {day}"
    return CheckResult(NAMES["ga4"], FAIL if problems else PASS, summary, problems)


def is_partner_page(tool: str) -> bool:
    """`tool` is host + path, e.g. programs.clearerthinking.org/p/hive/quiz/."""
    return tool[tool.find("/"):].startswith(PARTNER_PATH)


def top_tool_medians(by_tool: dict, day: date) -> dict:
    """{tool: baseline medians} for CT's TOP_TOOLS by trailing volume, partner pages excluded."""
    medians = {tool: baseline_medians(days, day) for tool, days in by_tool.items()
               if not is_partner_page(tool)}
    return {t: medians[t] for t in sorted(medians, key=lambda t: -sum(medians[t].values()))[:TOP_TOOLS]}


def _tool_state(by_tool: dict, day: date, tool: str, medians: dict) -> tuple:
    """(dead events, busiest event count, usual daily total, silent) for one tool on `day`. An
    event is dead when the tool usually fires it (median >= TOOL_MIN_BASELINE) and it did not fire
    once; the tool is silent when every event it usually fires is dead."""
    counts = by_tool[tool].get(day.isoformat(), {})
    expected = [ev for ev in KEY_EVENTS if medians[ev] >= TOOL_MIN_BASELINE]
    dead = [ev for ev in expected if counts.get(ev, 0) == 0]
    silent = bool(dead) and len(dead) == len(expected)
    return dead, max(counts.values(), default=0), sum(medians[ev] for ev in expected), silent


def silent_tools(by_tool: dict, day: date) -> list:
    """Top tools that fired none of the events they usually fire, on a day too quiet to judge
    from the counts alone. Their pages have to be fetched to tell lost traffic from lost tracking."""
    out = []
    for tool, medians in top_tool_medians(by_tool, day).items():
        _dead, busiest, _usual, silent = _tool_state(by_tool, day, tool, medians)
        if silent and busiest < TOOL_MIN_BASELINE:
            out.append(tool)
    return out


def tracking_page_problem(f: "Fetched") -> Optional[str]:
    why = page_problem(f)
    if why:
        return f"its page {why}"
    if TRACKING_SCRIPT not in f.body:
        return "its page loads but no longer includes the tracking script"
    return None


def evaluate_tools(by_tool: dict, day: date, pages: dict) -> CheckResult:
    """Per-tool rules, for each of CT's top tools:

    - It had real traffic (some key event fired TOOL_MIN_BASELINE+ times) but an event it usually
      fires did not fire once: that event is broken on that tool.
    - It fired nothing it usually fires: `pages[tool]` (its fetched page) decides. A page that is
      down, redirects elsewhere or lost the tracking script is a failure; a healthy page means the
      tool simply had no visitors, which is not this monitor's business.
    - Anything in between (a handful of events) is too little traffic to judge.
    """
    top = top_tool_medians(by_tool, day)
    problems, limited, quiet = [], [], []
    for tool, medians in top.items():
        dead, busiest, usual, silent = _tool_state(by_tool, day, tool, medians)
        if busiest >= TOOL_MIN_BASELINE:
            problems += [f"{tool}: {ev} was 0 on {day} (trailing median {_n(medians[ev])} a day) "
                         f"while another key event fired {_n(busiest)} times" for ev in dead]
        elif silent and pages[tool].status == 429:
            limited.append(f"rate limited (HTTP 429) on https://{tool}")
        elif silent:
            why = tracking_page_problem(pages[tool])
            if why:
                problems.append(f"{tool}: no key event on {day} (usually about {_n(usual)} a day) and {why}")
            else:
                quiet.append(tool.split("/", 1)[1])
    summary = f"top {len(top)} tools fire every event they usually do"
    if quiet:
        summary += f" (no visitors on {day}, page and tracking script intact: {', '.join(quiet)})"
    if problems:
        return CheckResult(NAMES["tools"], FAIL, "", problems)
    if limited:
        return CheckResult(NAMES["tools"], UNKNOWN, "", limited)
    return CheckResult(NAMES["tools"], PASS, summary)


def fetch_ga4_by_tool(day: date) -> dict:
    """{host+path: {iso date: {event: count}}} for `day` and its baseline days."""
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest,
    )
    from ga4_client import get_client, property_path

    resp = get_client().run_report(RunReportRequest(
        property=property_path(),
        date_ranges=[DateRange(start_date=str(day - timedelta(days=BASELINE_DAYS)), end_date=str(day))],
        dimensions=[Dimension(name=d) for d in ("date", "hostName", "pagePath", "eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=_key_event_filter(Filter, FilterExpression),
        limit=250000,
    ))
    out: dict = {}
    for r in resp.rows:
        d, host, path, ev = (v.value for v in r.dimension_values)
        if host in IGNORED_HOSTS:
            continue
        bucket = out.setdefault(host + path, {}).setdefault(f"{d[:4]}-{d[4:6]}-{d[6:8]}", {})
        bucket[ev] = bucket.get(ev, 0) + int(r.metric_values[0].value)
    return out


def fetch_ga4_realtime() -> dict:
    from google.analytics.data_v1beta.types import (
        Dimension, Filter, FilterExpression, Metric, RunRealtimeReportRequest,
    )
    from ga4_client import get_client, property_path

    resp = get_client().run_realtime_report(RunRealtimeReportRequest(
        property=property_path(),
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=_key_event_filter(Filter, FilterExpression),
    ))
    return {r.dimension_values[0].value: int(r.metric_values[0].value) for r in resp.rows}


def _key_event_filter(Filter, FilterExpression):
    return FilterExpression(filter=Filter(
        field_name="eventName", in_list_filter=Filter.InListFilter(values=list(KEY_EVENTS))))


# =============================================================================
# Pages and sign-up links
# =============================================================================
@dataclass
class Fetched:
    url: str
    status: Optional[int] = None
    final_url: str = ""
    body: str = ""
    error: str = ""


@dataclass
class Anchor:
    href: str
    text: str
    in_menu: bool


class _AnchorParser(HTMLParser):
    """Collects every <a href> with its visible text, noting which sit inside the site menu."""

    def __init__(self) -> None:
        super().__init__()
        self.anchors: list = []
        self._in_menu = False
        self._open: Optional[Anchor] = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav" and a.get("aria-label") == MENU_NAV_LABEL:
            self._in_menu = True
        elif tag == "a" and a.get("href"):
            self._open = Anchor(a["href"], "", self._in_menu)

    def handle_endtag(self, tag):
        if tag == "nav":
            self._in_menu = False
        elif tag == "a" and self._open:
            self._open.text = " ".join(self._open.text.split())
            self.anchors.append(self._open)
            self._open = None

    def handle_data(self, data):
        if self._open:
            self._open.text += data


def parse_anchors(html: str) -> list:
    parser = _AnchorParser()
    parser.feed(html)
    return parser.anchors


def menu_links(anchors: list) -> list:
    """Unique absolute URLs in the site menu, in menu order."""
    seen: dict = {}
    for a in anchors:
        if a.in_menu and a.href.startswith("http"):
            seen.setdefault(a.href.rstrip("/"), None)
    return list(seen)


_TITLE_RE = re.compile(r"<title[^>]*>\s*[^<\s]", re.I)


def page_problem(f: Fetched) -> Optional[str]:
    """Why a fetched page does not count as loaded, or None. HTTP 429 is handled by the caller:
    it says we were rate limited, not that the page is down."""
    if f.error:
        return f"did not load ({f.error})"
    if f.status != 200:
        return f"returned HTTP {f.status}"
    if urlparse(f.final_url).hostname != urlparse(f.url).hostname:
        return f"redirects to another site ({f.final_url})"
    if len(f.body) < MIN_PAGE_BYTES:
        return f"came back nearly empty ({len(f.body)} bytes)"
    if not _TITLE_RE.search(f.body):
        return "has no page title"
    return None


def evaluate_pages(fetches: list, menu_count: int) -> CheckResult:
    name = NAMES["pages"]
    problems, limited = [], []
    if menu_count < MIN_MENU_LINKS:
        problems.append(f"the site menu has {menu_count} links, expected at least {MIN_MENU_LINKS}: "
                        "it shrank or its markup changed")
    for f in fetches:
        if f.status == 429:
            limited.append(f.url)
            continue
        why = page_problem(f)
        if why:
            problems.append(f"{f.url} {why}")
    if problems:
        return CheckResult(name, FAIL, "", problems)
    if limited:
        return CheckResult(name, UNKNOWN, "", [f"rate limited (HTTP 429) on {u}" for u in limited])
    return CheckResult(name, PASS, f"{len(fetches)} pages load ({menu_count} menu links)")


def signup_link_problems(anchors: list, required: frozenset) -> list:
    """Rules for one page's Sign Up buttons: each must be the bare subscribe-program link for a
    valid tier, and every required tier must have one."""
    buttons = [a for a in anchors
               if a.text.lower() == "sign up" or a.href.startswith(SUBSCRIBE_RUN.rsplit("/", 1)[0])]
    if not buttons:
        return ["no Sign Up button found"]
    problems, found = [], set()
    for href in dict.fromkeys(a.href for a in buttons):
        url = urlparse(href)
        if f"{url.scheme}://{url.netloc}{url.path}" != SUBSCRIBE_RUN:
            problems.append(f"a Sign Up button points to {href[:120]} instead of the subscribe program")
            continue
        params = parse_qs(url.query)
        tier = (params.get("p") or [""])[0]
        if tier not in TIERS:
            problems.append(f"a Sign Up button has tier p={tier or '(missing)'}, not one of {', '.join(TIERS)}")
            continue
        found.add(tier)
        extra = sorted(set(params) - ALLOWED_LINK_PARAMS)
        if extra:
            problems.append(f"the {tier} Sign Up link carries extra parameters ({', '.join(extra)}): "
                            "a pasted browser URL, so every visitor is sent with those same values")
    problems += [f"no Sign Up button for the {t} tier" for t in sorted(required - found)]
    return problems


def evaluate_links(pages: dict) -> CheckResult:
    """`pages` maps each SIGNUP_PAGES url to its Fetched."""
    name = NAMES["links"]
    problems, unknown = [], []
    for url, required in SIGNUP_PAGES.items():
        f = pages[url]
        path = urlparse(url).path
        if f.status == 429:
            unknown.append(f"rate limited (HTTP 429) on {url}")
        elif page_problem(f):
            problems.append(f"{path}: page {page_problem(f)}")
        else:
            problems += [f"{path}: {p}" for p in signup_link_problems(parse_anchors(f.body), required)]
    if problems:
        return CheckResult(name, FAIL, "", problems)
    if unknown:
        return CheckResult(name, UNKNOWN, "", unknown)
    return CheckResult(name, PASS, "every Sign Up button is the bare subscribe-program link")


def fetch_page(url: str) -> Fetched:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as e:
        return Fetched(url, error=f"{type(e).__name__}: {str(e)[:150]}")
    return Fetched(url, r.status_code, r.url, r.text)


# =============================================================================
# Stripe checkout
# =============================================================================
def product_name(tier: str) -> str:
    return f"Clearer Thinking Plus - {tier.title()}"


def checkout_problem(tier: str, final_url: str, text: str) -> Optional[str]:
    """Judge where the browser ended up after submitting the email in the subscribe program."""
    shown = " ".join(text.split())[:200]
    if not final_url.startswith(STRIPE_CHECKOUT):
        return (f"{tier}: never reached Stripe checkout (ended on {final_url.split('?')[0][:80]}; "
                f"page said: {shown!r})")
    if product_name(tier).lower() not in text.lower():
        return f"{tier}: Stripe checkout does not show \"{product_name(tier)}\" (page said: {shown!r})"
    if not PRICE_RE.search(text):
        return f"{tier}: Stripe checkout shows no price"
    return None


def evaluate_checkout(outcomes: dict) -> CheckResult:
    """`outcomes` maps tier -> (final_url, page_text)."""
    problems = [p for p in (checkout_problem(t, *outcomes[t]) for t in TIERS) if p]
    return CheckResult(NAMES["checkout"], FAIL if problems else PASS,
                       f"all {len(TIERS)} tiers reach a Stripe checkout with the right product", problems)


def drive_checkout() -> dict:
    """Run the subscribe program once per tier in headless Chrome. Creates real, tagged runs."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    outcomes = {}
    with sync_playwright() as p:
        # channel="chrome": plain headless Chromium renders GuidedTrack pages blank.
        browser = p.chromium.launch(channel="chrome", headless=True)
        for tier in TIERS:
            context = browser.new_context(viewport={"width": 1100, "height": 1000})
            page = context.new_page()
            try:
                page.goto(f"{SUBSCRIBE_RUN}?p={tier}&src={HEALTHCHECK_SRC}", timeout=45000)
                page.fill("input[type=text]", HEALTHCHECK_EMAIL, timeout=30000)
                page.get_by_role("button", name="Submit").first.click()
                page.wait_for_url(STRIPE_CHECKOUT + "**", timeout=45000)
                page.get_by_text(product_name(tier)).first.wait_for(timeout=30000)
            except PlaywrightTimeout:
                pass  # judged by checkout_problem from wherever the browser stopped
            outcomes[tier] = (page.url, page.inner_text("body"))
            context.close()
        browser.close()
    return outcomes


# =============================================================================
# beehiiv
# =============================================================================
def evaluate_beehiiv(api_created: list, day_start: float, day_end: float, now: float,
                     ga4_submitted: Optional[int]) -> CheckResult:
    """`api_created`: creation timestamps of every API-channel subscriber since `day_start`."""
    name = NAMES["beehiiv"]
    if not api_created:
        return CheckResult(name, FAIL, "", ["no subscriber has been created through the API since "
                                           "the start of yesterday (US Eastern)"])
    problems = []
    age_hours = (now - max(api_created)) / 3600
    if age_hours > MAX_API_SUB_AGE_HOURS:
        problems.append(f"the newest API-created subscriber is {age_hours:.1f} hours old "
                        f"(limit {MAX_API_SUB_AGE_HOURS})")
    count = sum(day_start <= ts < day_end for ts in api_created)
    summary = f"{_n(count)} API subscribers yesterday, newest {age_hours * 60:.0f} minutes ago"
    if count == 0:
        problems.append("no subscriber was created through the API yesterday")
    elif ga4_submitted is not None and ga4_submitted >= MIN_SUBMITTED_FOR_RATIO:
        ratio = count / ga4_submitted
        summary += f" ({ratio:.2f} per GA4 Submitted Email)"
        if ratio < MIN_SHARE_OF_SUBMITTED:
            problems.append(f"only {_n(count)} API subscribers yesterday against {_n(ga4_submitted)} "
                            f"GA4 Submitted Email events ({ratio:.0%}): sign-ups are not reaching beehiiv")
    return CheckResult(name, FAIL if problems else PASS, summary, problems)


def fetch_api_subscriber_times(since: float) -> list:
    """Creation timestamps of API-channel subscribers created at or after `since`, newest first."""
    from data_layer import BEEHIIV_BASE, _beehiiv_get

    key = os.getenv("BEEHIIV_API_KEY", "").strip()
    pub = os.getenv("BEEHIIV_PUB_CLEARER_THINKING", "").strip()
    if not key or not pub:
        raise RuntimeError("BEEHIIV_API_KEY / BEEHIIV_PUB_CLEARER_THINKING not set")
    params = {"limit": 100, "order_by": "created", "direction": "desc"}
    out = []
    for _ in range(BEEHIIV_MAX_PAGES):
        resp = _beehiiv_get(f"{BEEHIIV_BASE}/publications/{pub}/subscriptions",
                            headers={"Authorization": f"Bearer {key}"}, params=params)
        resp.raise_for_status()
        page = resp.json()
        subs = page.get("data", [])
        out += [s["created"] for s in subs
                if s["created"] >= since and (s.get("utm_channel") or "").lower() == API_CHANNEL]
        if not subs or subs[-1]["created"] < since or not page.get("has_more"):
            return out
        params["cursor"] = page["next_cursor"]
    raise RuntimeError(f"beehiiv walk did not reach yesterday within {BEEHIIV_MAX_PAGES} pages")


# =============================================================================
# Running the checks
# =============================================================================
class Context:
    """Fetches shared between checks within one attempt; reset() before a retry."""

    def __init__(self) -> None:
        self.day = ga4_yesterday()
        self.submitted_yesterday: Optional[int] = None   # kept across retries, for the beehiiv ratio
        self.reset()

    def reset(self) -> None:
        self._pages: dict = {}
        self._ga4: Optional[dict] = None

    def page(self, url: str) -> Fetched:
        if url not in self._pages:
            if self._pages:
                time.sleep(PAGE_PAUSE_SECONDS)
            self._pages[url] = fetch_page(url)
        return self._pages[url]

    def ga4_by_tool(self) -> dict:
        if self._ga4 is None:
            self._ga4 = fetch_ga4_by_tool(self.day)
        return self._ga4


def run_ga4(ctx: Context) -> CheckResult:
    daily = site_totals(ctx.ga4_by_tool())
    ctx.submitted_yesterday = daily.get(ctx.day.isoformat(), {}).get("Submitted Email", 0)
    return evaluate_ga4(daily, fetch_ga4_realtime(), ctx.day)


def run_tools(ctx: Context) -> CheckResult:
    by_tool = ctx.ga4_by_tool()
    pages = {tool: ctx.page("https://" + tool) for tool in silent_tools(by_tool, ctx.day)}
    return evaluate_tools(by_tool, ctx.day, pages)


def run_pages(ctx: Context) -> CheckResult:
    menu = menu_links(parse_anchors(ctx.page(HOME).body))
    urls = list(dict.fromkeys(list(REQUIRED_PAGES) + menu))
    return evaluate_pages([ctx.page(u) for u in urls], len(menu))


def run_links(ctx: Context) -> CheckResult:
    return evaluate_links({url: ctx.page(url) for url in SIGNUP_PAGES})


def run_checkout(ctx: Context) -> CheckResult:
    return evaluate_checkout(drive_checkout())


def run_beehiiv(ctx: Context) -> CheckResult:
    from zoneinfo import ZoneInfo

    start = datetime.combine(ctx.day, datetime.min.time(), ZoneInfo(GA4_TZ))
    return evaluate_beehiiv(fetch_api_subscriber_times(start.timestamp()), start.timestamp(),
                            (start + timedelta(days=1)).timestamp(), time.time(), ctx.submitted_yesterday)


# Order matters: ga4 records the Submitted Email count that beehiiv compares against.
CHECKS: dict = {"ga4": run_ga4, "tools": run_tools, "pages": run_pages, "links": run_links,
                "checkout": run_checkout, "beehiiv": run_beehiiv}


def run_check(key: str, ctx: Context, retry: bool, sleep: Callable = time.sleep) -> CheckResult:
    """Run one check; anything it raises means the check itself could not be performed."""
    def attempt() -> CheckResult:
        try:
            return CHECKS[key](ctx)
        except (Exception, SystemExit) as e:  # noqa: BLE001 - ga4_client exits on a missing token
            return CheckResult(NAMES[key], UNKNOWN, "", [f"{type(e).__name__}: {str(e)[:300]}"])

    result = attempt()
    if result.status != PASS and retry:
        print(f"  {key}: {STATUS_LABEL[result.status]}, retrying in {RETRY_WAIT_SECONDS}s", flush=True)
        sleep(RETRY_WAIT_SECONDS)
        ctx.reset()
        result = attempt()
    return result


# =============================================================================
# Emails
# =============================================================================
def compose_alert(results: list, when: datetime, retried: bool, run_url: str = "") -> Optional[tuple]:
    """(subject, body) for the alert email, or None when every check passed."""
    failed = [r for r in results if r.status == FAIL]
    unknown = [r for r in results if r.status == UNKNOWN]
    if not failed and not unknown:
        return None
    parts = []
    if failed:
        parts.append("FAILED: " + ", ".join(r.name for r in failed))
    if unknown:
        parts.append(("COULD NOT CHECK: " if not failed else "could not check: ")
                     + ", ".join(r.name for r in unknown))
    lines = [f"CT site check, {when:%a %Y-%m-%d %H:%M} UTC", ""]
    for r in failed + unknown:
        lines.append(f"{STATUS_LABEL[r.status]}: {r.name}")
        lines += [f"  - {p}" for p in r.problems]
        lines.append("")
    if unknown:
        lines += ["COULD NOT CHECK means the check itself did not run, not that the site is broken.", ""]
    lines += [f"OK: {r.name}: {r.summary}" for r in results if r.status == PASS]
    if retried:
        lines += ["", f"Every check listed as {STATUS_LABEL[FAIL]} or {STATUS_LABEL[UNKNOWN]} was run twice, "
                      f"{RETRY_WAIT_SECONDS} seconds apart, before this email was sent."]
    if run_url:
        lines += ["", f"Run log: {run_url}"]
    return f"{EMAIL_TAG} {' | '.join(parts)}", "\n".join(lines)


def week_outcomes(runs: list, today: date, today_ok: bool) -> list:
    """[(day, True passed / False problems / None did not run)] for the 7 days ending today.

    `runs` are GitHub workflow runs (created_at, status, conclusion). A day takes the conclusion
    of its last completed run; today comes from this process, whose own run is still in progress.
    """
    last: dict = {}
    for run in sorted(runs, key=lambda r: r["created_at"]):
        if run.get("status") == "completed":
            last[run["created_at"][:10]] = run.get("conclusion") == "success"
    days = [today - timedelta(days=i) for i in range(6, 0, -1)]
    return [(d, last.get(d.isoformat())) for d in days] + [(today, today_ok)]


def compose_heartbeat(outcomes: list) -> tuple:
    ran = [d for d, ok in outcomes if ok is not None]
    bad = [d for d, ok in outcomes if ok is False]
    headline = f"{len(ran)} of {len(outcomes)} daily checks ran, "
    headline += "all passed" if not bad else f"{len(bad)} found problems"
    word = {True: "passed", False: "problems found (see that day's alert email)", None: "DID NOT RUN"}
    lines = [headline + ".", ""] + [f"{d:%a %Y-%m-%d}: {word[ok]}" for d, ok in outcomes]
    if len(ran) < len(outcomes):
        lines += ["", "A day with no run means the monitor itself was down that day, so nothing "
                      "was checked. A scheduled run that slipped past midnight UTC also shows up this way."]
    return f"{EMAIL_TAG} Weekly: {headline}", "\n".join(lines)


def fetch_workflow_runs(since: date) -> list:
    repo, token = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        raise RuntimeError("GITHUB_REPOSITORY / GITHUB_TOKEN not set (run history is only available in CI)")
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs",
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                     params={"created": f">={since.isoformat()}", "per_page": 100}, timeout=30)
    r.raise_for_status()
    return r.json()["workflow_runs"]


def send(subject: str, body: str) -> bool:
    """Email Igor from his own address. Returns False if it could not be delivered by email."""
    import email_transport

    try:
        email_transport.send_email(subject, body, email_transport.EMAIL_FROM, from_label="CT Site Check",
                                   header_tag="site-health", to_inbox=True)
        print(f"emailed: {subject}")
        return True
    except Exception as e:  # noqa: BLE001 - report the delivery failure, do not crash on it
        print(f"[error] could not email: {e}", file=sys.stderr)
        email_transport.slack_fallback(str(e), "CT site check", email_transport.TRANSPORT_FIX)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the result, send no email")
    ap.add_argument("--only", help="comma-separated subset of: " + ", ".join(CHECKS))
    ap.add_argument("--no-retry", action="store_true", help="do not re-run a check that did not pass")
    ap.add_argument("--heartbeat", action="store_true", help="send the weekly summary (automatic on Mondays)")
    args = ap.parse_args()

    import secrets_loader

    secrets_loader.materialize_ci_secrets()
    keys = [k.strip() for k in args.only.split(",")] if args.only else list(CHECKS)
    unknown_keys = [k for k in keys if k not in CHECKS]
    if unknown_keys:
        ap.error(f"unknown check(s): {', '.join(unknown_keys)}")

    ctx = Context()
    results = []
    for key in keys:
        result = run_check(key, ctx, retry=not args.no_retry)
        results.append(result)
        print(f"{STATUS_LABEL[result.status]:16} {result.name}: {result.summary}", flush=True)
        for p in result.problems:
            print(f"    - {p}")

    now = datetime.now(timezone.utc)
    all_ok = all(r.status == PASS for r in results)
    delivered = True
    run_url = ""
    if os.getenv("GITHUB_RUN_ID"):
        run_url = (f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}")

    emails = []
    alert = compose_alert(results, now, retried=not args.no_retry, run_url=run_url)
    if alert:
        emails.append(alert)
    if args.heartbeat or now.weekday() == 0:
        try:
            runs = fetch_workflow_runs(now.date() - timedelta(days=7))
            emails.append(compose_heartbeat(week_outcomes(runs, now.date(), all_ok)))
        except Exception as e:  # noqa: BLE001 - the summary must not hide today's result
            emails.append((f"{EMAIL_TAG} Weekly: summary unavailable",
                           f"Today's check {'passed' if all_ok else 'found problems'}, but the week's "
                           f"run history could not be read: {type(e).__name__}: {e}"))
    for subject, body in emails:
        if args.dry_run:
            print(f"\n--- would email ---\nSubject: {subject}\n\n{body}")
        else:
            delivered = send(subject, body) and delivered
    return 0 if all_ok and delivered else 1


if __name__ == "__main__":
    sys.exit(main())
