"""Unit tests for the pure rules in site_health_check.py (no network, no browser, no email)."""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import site_health_check as shc  # noqa: E402
from site_health_check import FAIL, PASS, UNKNOWN, Anchor, CheckResult, Fetched  # noqa: E402

V, A, S = shc.KEY_EVENTS
DAY = date(2026, 9, 30)


def series(day: date, baseline: dict, yesterday: dict) -> dict:
    """BASELINE_DAYS identical baseline days followed by `yesterday`."""
    out = {d: dict(baseline) for d in shc.baseline_days(day)}
    out[day.isoformat()] = dict(yesterday)
    return out


# ---- site-wide event volumes -------------------------------------------------------------------
def test_baseline_medians_by_hand():
    # Viewed over the 14 prior days: 10,20,...,140 -> median (70+80)/2 = 75. Accepted missing -> 0.
    assert shc.BASELINE_DAYS == 14
    daily = {(DAY - timedelta(days=i)).isoformat(): {V: 10 * i} for i in range(1, 15)}
    assert shc.baseline_medians(daily, DAY) == {V: 75, A: 0, S: 0}


def test_baseline_ignores_yesterday_and_older_days():
    daily = series(DAY, {V: 100, A: 100, S: 100}, {V: 9999, A: 9999, S: 9999})
    daily[(DAY - timedelta(days=shc.BASELINE_DAYS + 1)).isoformat()] = {V: 5000, A: 5000, S: 5000}
    assert shc.baseline_medians(daily, DAY) == {V: 100, A: 100, S: 100}


def test_a_missing_baseline_day_counts_as_zero():
    daily = series(DAY, {V: 100, A: 100, S: 100}, {V: 100, A: 100, S: 100})
    for d in shc.baseline_days(DAY)[:8]:   # 8 of 14 days absent -> median 0
        del daily[d]
    assert shc.baseline_medians(daily, DAY)[V] == 0


def test_an_event_that_never_fired_is_a_failure_even_with_no_history():
    assert len(shc.silent_event_problems({}, DAY)) == 3
    problems = shc.silent_event_problems(series(DAY, {V: 500, A: 400, S: 300}, {V: 500, A: 400}), DAY)
    assert problems == [f"{S}: 0 events on 2026-09-30 (trailing 14-day median 300)"]


def test_a_traffic_swing_is_not_a_failure():
    # Volume is not judged: campaigns ending took events to 6% of baseline in Feb 2026 with
    # nothing broken, and a volume rule raised 18 false alarms in the 12-month backtest.
    base = {V: 1000, A: 700, S: 400}
    assert shc.silent_event_problems(series(DAY, base, {V: 9000, A: 6000, S: 4000}), DAY) == []
    assert shc.silent_event_problems(series(DAY, base, {V: 60, A: 40, S: 1}), DAY) == []


# The site-wide counts GA4 actually reported for 2026-08-27..09-30, a window with a viral spike
# and its decay: the realistic "nothing is broken" data set.
REAL_SEP_2026 = """975 938 400|876 957 450|715 770 330|850 827 393|720 960 368|1432 1462 623|983 1003 543
905 955 460|696 626 322|631 615 339|1692 1197 653|2009 1462 945|2153 1371 844|2834 2097 1390
5041 3706 2548|5135 4038 2822|4155 3302 2301|3743 2887 1971|4507 3457 2367|3391 2327 1528
3121 2351 1555|2250 1633 1025|2279 1602 981|1962 1335 781|1689 1223 712|1684 1168 717|1721 1293 749
1526 990 569|1608 1140 674|1938 1347 802|1792 1234 778|1563 1099 640|1849 1248 741|1826 1208 721
1894 1271 728""".replace("\n", "|").split("|")


def real_daily() -> dict:
    start = date(2026, 8, 27)
    return {(start + timedelta(days=i)).isoformat(): dict(zip(shc.KEY_EVENTS, map(int, row.split())))
            for i, row in enumerate(REAL_SEP_2026)}


def test_realistic_healthy_month_raises_no_alert():
    daily = real_daily()
    for i in range(shc.BASELINE_DAYS, len(REAL_SEP_2026)):
        day = date(2026, 8, 27) + timedelta(days=i)
        assert shc.evaluate_ga4(daily, None, day).status == PASS, day


def test_realistic_month_with_a_broken_event_raises_an_alert():
    # Submitted Email stops firing on Sep 20 (the email gate breaks); the other two carry on.
    daily = real_daily()
    for d in ("2026-09-20", "2026-09-21"):
        daily[d][S] = 0
    assert shc.evaluate_ga4(daily, None, date(2026, 9, 19)).status == PASS
    for day in (date(2026, 9, 20), date(2026, 9, 21)):
        result = shc.evaluate_ga4(daily, None, day)
        assert result.status == FAIL and len(result.problems) == 1 and result.problems[0].startswith(S)


# ---- realtime ------------------------------------------------------------------------------------
MEDIANS = {V: 1800, A: 1250, S: 730}   # 3780 a day -> 78.75 expected per 30 minutes


def test_realtime_all_zero_fails_only_when_traffic_is_high_enough():
    assert len(shc.realtime_problems({}, MEDIANS)) == 1
    # 1900 a day -> 39.6 expected per window: under the 40 threshold, so silence is not a failure.
    assert shc.realtime_problems({}, {V: 1000, A: 600, S: 300}) == []
    # 1920 a day -> exactly 40.
    assert len(shc.realtime_problems({}, {V: 1000, A: 620, S: 300})) == 1


def test_realtime_single_dead_event_needs_a_busy_peer():
    assert shc.realtime_problems({V: 40, A: 32, S: 24}, MEDIANS) == []
    problems = shc.realtime_problems({V: 40, A: 32}, MEDIANS)
    assert len(problems) == 1 and problems[0].startswith(S)
    # Quiet half hour: the busiest event is under 30, so a zero proves nothing.
    assert shc.realtime_problems({V: 29, A: 12}, MEDIANS) == []
    assert len(shc.realtime_problems({V: 30, A: 12}, MEDIANS)) == 1


def test_evaluate_ga4_combines_daily_and_realtime():
    daily = series(DAY, MEDIANS, MEDIANS)
    assert shc.evaluate_ga4(daily, {V: 40, A: 32, S: 24}, DAY).status == PASS
    assert shc.evaluate_ga4(daily, {V: 40, A: 32}, DAY).status == FAIL
    assert shc.evaluate_ga4(daily, None, DAY).status == PASS
    assert "Submitted 730" in shc.evaluate_ga4(daily, None, DAY).summary


# ---- per tool ------------------------------------------------------------------------------------
def healthy_tools() -> dict:
    """Shaped like the real property: the personality test never fires Viewed, the paid
    cognitive assessment never fires Submitted, and a tiny tool sits below every baseline."""
    return {
        "programs.clearerthinking.org/personality-test.html": series(DAY, {A: 160, S: 97}, {A: 150, S: 90}),
        "programs.clearerthinking.org/cognitive-test-intro.html": series(DAY, {V: 120, A: 26}, {V: 110, A: 20}),
        "programs.clearerthinking.org/philosophical_beliefs.html":
            series(DAY, {V: 147, A: 98, S: 41}, {V: 140, A: 90, S: 38}),
        "programs.clearerthinking.org/tiny.html": series(DAY, {V: 5, A: 3, S: 1}, {V: 4}),
    }


def test_site_totals_sums_tools_by_hand():
    totals = shc.site_totals(healthy_tools())[DAY.isoformat()]
    assert totals == {V: 110 + 140 + 4, A: 150 + 20 + 90, S: 90 + 38}


UPT = "programs.clearerthinking.org/personality-test.html"
BELIEFS = "programs.clearerthinking.org/philosophical_beliefs.html"


def tool_page(tool: str, status=200, body=None) -> Fetched:
    url = "https://" + tool
    if body is None:
        body = '<title>Tool</title><script src="/google_analytics_guidedtrack_trigger.js"></script>' + "x" * 600
    return Fetched(url, status, url, body)


def test_tools_healthy_property_passes_despite_events_that_never_fire():
    assert shc.silent_tools(healthy_tools(), DAY) == []
    assert shc.evaluate_tools(healthy_tools(), DAY, {}).status == PASS


def test_tool_losing_one_expected_event_while_busy_fails():
    tools = healthy_tools()
    tools[BELIEFS][DAY.isoformat()] = {V: 140, A: 90}
    result = shc.evaluate_tools(tools, DAY, {})
    assert result.status == FAIL and len(result.problems) == 1
    assert "philosophical_beliefs" in result.problems[0] and S in result.problems[0] and "140 times" in result.problems[0]


def test_a_handful_of_events_is_too_little_traffic_to_judge():
    # 29 Viewed and no Accepted: suspicious, but under the 30-event bar. 30 Viewed is enough.
    tools = healthy_tools()
    tools[BELIEFS][DAY.isoformat()] = {V: 29}
    assert shc.silent_tools(tools, DAY) == [] and shc.evaluate_tools(tools, DAY, {}).status == PASS
    tools[BELIEFS][DAY.isoformat()] = {V: 30}
    result = shc.evaluate_tools(tools, DAY, {})
    assert result.status == FAIL and len(result.problems) == 2   # Accepted and Submitted


def test_silent_tool_with_a_healthy_page_just_had_no_visitors():
    # The real 2026-10-01 case: imposter_syndrome.html lost its traffic source, tracking intact.
    tools = healthy_tools()
    del tools[UPT][DAY.isoformat()]
    assert shc.silent_tools(tools, DAY) == [UPT]
    result = shc.evaluate_tools(tools, DAY, {UPT: tool_page(UPT)})
    assert result.status == PASS and "no visitors" in result.summary and "personality-test.html" in result.summary


def test_silent_tool_whose_page_lost_tracking_or_is_down_fails():
    tools = healthy_tools()
    del tools[UPT][DAY.isoformat()]
    untracked = shc.evaluate_tools(tools, DAY, {UPT: tool_page(UPT, body="<title>Tool</title>" + "x" * 600)})
    assert untracked.status == FAIL and len(untracked.problems) == 1
    assert "257 a day" in untracked.problems[0] and "tracking script" in untracked.problems[0]   # 160 + 97
    down = shc.evaluate_tools(tools, DAY, {UPT: tool_page(UPT, status=404)})
    assert down.status == FAIL and "HTTP 404" in down.problems[0]
    moved = Fetched("https://" + UPT, 200, "https://www.guidedtrack.com/programs/x/run", tool_page(UPT).body)
    assert "another site" in shc.evaluate_tools(tools, DAY, {UPT: moved}).problems[0]
    assert shc.evaluate_tools(tools, DAY, {UPT: tool_page(UPT, status=429)}).status == UNKNOWN


def test_tool_event_below_its_baseline_floor_is_ignored():
    # Baseline exactly 30 is expected; 29 is not.
    assert shc.TOOL_MIN_BASELINE == 30
    tools = {"t/a": series(DAY, {V: 100, A: 30, S: 29}, {V: 100})}
    result = shc.evaluate_tools(tools, DAY, {})
    assert result.status == FAIL and len(result.problems) == 1 and A in result.problems[0]


def test_partner_campaign_pages_are_not_checked_and_do_not_take_a_top_slot():
    assert shc.is_partner_page("programs.clearerthinking.org/p/hive/worlds-biggest-problems-quiz/")
    assert not shc.is_partner_page("programs.clearerthinking.org/personality-test.html")
    assert not shc.is_partner_page("programs.clearerthinking.org/tools/p/x.html")
    # Ten busy partner pages whose campaigns just ended, plus one CT tool that lost an event.
    tools = {f"programs.clearerthinking.org/p/partner{i}/quiz/": series(DAY, {V: 5000, A: 4000}, {})
             for i in range(shc.TOP_TOOLS)}
    assert shc.silent_tools(tools, DAY) == [] and shc.evaluate_tools(tools, DAY, {}).status == PASS
    tools["programs.clearerthinking.org/small.html"] = series(DAY, {V: 60, A: 40}, {V: 55})
    result = shc.evaluate_tools(tools, DAY, {})
    assert result.status == FAIL and len(result.problems) == 1 and "small.html" in result.problems[0]


def test_only_the_top_tools_are_checked():
    tools = {f"t/{i}": series(DAY, {V: 1000 - i}, {V: 1}) for i in range(shc.TOP_TOOLS)}
    tools["t/small"] = series(DAY, {V: 50}, {})   # 11th by volume and silent
    assert shc.silent_tools(tools, DAY) == [] and shc.evaluate_tools(tools, DAY, {}).status == PASS


# ---- pages ---------------------------------------------------------------------------------------
PAGE = "<html><head><title>Coaching | Clearer Thinking</title></head><body>" + "x" * 600 + "</body></html>"


def fetched(url="https://www.clearerthinking.org/coaching", status=200, final=None, body=PAGE, error=""):
    return Fetched(url, status, final or url, body, error)


def test_page_problem_cases():
    assert shc.page_problem(fetched()) is None
    assert "HTTP 404" in shc.page_problem(fetched(status=404))
    assert "did not load" in shc.page_problem(fetched(status=None, error="ConnectTimeout"))
    assert "another site" in shc.page_problem(fetched(final="https://parked.example.com/"))
    assert "nearly empty" in shc.page_problem(fetched(body="<title>x</title>"))
    assert "no page title" in shc.page_problem(fetched(body="<title> </title>" + "x" * 600))


def test_same_host_redirect_is_fine():
    assert shc.page_problem(fetched(final="https://www.clearerthinking.org/coaching-2")) is None


MENU_HTML = """
<a href="https://www.clearerthinking.org/outside">Outside the menu</a>
<nav aria-label="Site"><ul>
  <li><a href="https://www.clearerthinking.org/clearer-thinking-tools"><span>All Tools</span></a></li>
  <li><a href="https://www.clearerthinking.org">Resources</a></li>
  <li><a href="https://www.clearerthinking.org/">About</a></li>
  <li><a href="./#comp-1">anchor</a></li>
  <li><a href="https://podcast.clearerthinking.org/">Podcast</a></li>
</ul></nav>
<nav aria-label="slides"><a href="https://www.clearerthinking.org/slide">slide</a></nav>
"""


def test_menu_links_are_unique_absolute_and_only_from_the_site_nav():
    assert shc.menu_links(shc.parse_anchors(MENU_HTML)) == [
        "https://www.clearerthinking.org/clearer-thinking-tools",
        "https://www.clearerthinking.org",
        "https://podcast.clearerthinking.org",
    ]


def test_parse_anchors_reads_nested_text_and_unescapes_hrefs():
    anchors = shc.parse_anchors('<a href="https://x.org/run?p=a&amp;src=b"><span><b>Sign</b> Up</span></a>')
    assert anchors == [Anchor("https://x.org/run?p=a&src=b", "Sign Up", False)]


def test_evaluate_pages():
    ok = [fetched(), fetched(url="https://www.clearerthinking.org/plus")]
    assert shc.evaluate_pages(ok, 21).status == PASS
    assert shc.evaluate_pages(ok, shc.MIN_MENU_LINKS).status == PASS
    shrunk = shc.evaluate_pages(ok, shc.MIN_MENU_LINKS - 1)
    assert shrunk.status == FAIL and "menu" in shrunk.problems[0]
    broken = shc.evaluate_pages(ok + [fetched(status=500)], 21)
    assert broken.status == FAIL and len(broken.problems) == 1
    # Rate limiting is our problem, not the site's; but a real failure outranks it.
    assert shc.evaluate_pages(ok + [fetched(status=429)], 21).status == UNKNOWN
    assert shc.evaluate_pages([fetched(status=429), fetched(status=500)], 21).status == FAIL


# ---- sign-up links -------------------------------------------------------------------------------
def button(tier, extra="", text="Sign Up"):
    return Anchor(f"{shc.SUBSCRIBE_RUN}?p={tier}{extra}", text, False)


ALL = frozenset(shc.TIERS)
NAV = frozenset({"navigator"})


def test_clean_signup_links_pass():
    assert shc.signup_link_problems([button(t) for t in shc.TIERS], ALL) == []
    assert shc.signup_link_problems([button("navigator"), button("navigator")], NAV) == []
    # A src tag is allowed, and unrelated anchors are ignored.
    anchors = [button("navigator", "&src=coaching"), Anchor("https://www.clearerthinking.org/blog", "Blog", True)]
    assert shc.signup_link_problems(anchors, NAV) == []


def test_pasted_browser_url_is_flagged():
    # The real /coaching link on 2026-10-01.
    pasted = button("navigator", "&ga_client_id=629654890.1762726747&ga_session_id=1790187394&_gl=1*ujo3q4")
    problems = shc.signup_link_problems([pasted, pasted], NAV)
    assert len(problems) == 1 and "_gl, ga_client_id, ga_session_id" in problems[0]


def test_missing_and_wrong_signup_links():
    assert shc.signup_link_problems([], NAV) == ["no Sign Up button found"]
    missing = shc.signup_link_problems([button("supporter"), button("navigator")], ALL)
    assert missing == ["no Sign Up button for the explorer tier"]
    elsewhere = shc.signup_link_problems([Anchor("https://buy.stripe.com/abc", "Sign Up", False)], NAV)
    assert len(elsewhere) == 2 and "points to https://buy.stripe.com/abc" in elsewhere[0]
    bad_tier = shc.signup_link_problems([button("platinum"), button("")], NAV)
    assert "p=platinum" in bad_tier[0] and "p=(missing)" in bad_tier[1] and "navigator tier" in bad_tier[2]
    other_program = Anchor("https://www.guidedtrack.com/programs/zzzzzzz/run?p=navigator", "Sign Up", False)
    assert len(shc.signup_link_problems([other_program], NAV)) == 2


def test_subscribe_link_with_other_button_text_is_still_checked():
    assert shc.signup_link_problems([button("navigator", "&_gl=1", text="Join now")], NAV) != []


def signup_page(*anchors):
    links = "".join(f'<a href="{a.href.replace("&", "&amp;")}">{a.text}</a>' for a in anchors)
    return "<title>CT</title>" + links + "x" * 600


def test_evaluate_links():
    good = {shc.PLUS: fetched(shc.PLUS, body=signup_page(*[button(t) for t in shc.TIERS])),
            shc.COACHING: fetched(shc.COACHING, body=signup_page(button("navigator")))}
    assert shc.evaluate_links(good).status == PASS
    bad = dict(good)
    bad[shc.COACHING] = fetched(shc.COACHING, body=signup_page(button("navigator", "&_gl=1")))
    result = shc.evaluate_links(bad)
    assert result.status == FAIL and result.problems[0].startswith("/coaching:")
    down = dict(good)
    down[shc.PLUS] = fetched(shc.PLUS, status=503)
    assert shc.evaluate_links(down).status == FAIL
    limited = dict(good)
    limited[shc.PLUS] = fetched(shc.PLUS, status=429)
    assert shc.evaluate_links(limited).status == UNKNOWN


# ---- checkout ------------------------------------------------------------------------------------
STRIPE_URL = "https://checkout.stripe.com/c/pay/cs_live_abc"
STRIPE_TEXT = "Back\nSubscribe to Clearer Thinking Plus - Supporter\n$9.00\nper\nmonth\nEmail"


def test_checkout_problem_cases():
    assert shc.checkout_problem("supporter", STRIPE_URL, STRIPE_TEXT) is None
    # Brazilian formatting of the same page.
    assert shc.checkout_problem("supporter", STRIPE_URL, STRIPE_TEXT.replace("$9.00", "R$48,92")) is None
    stuck = shc.checkout_problem("supporter", "https://www.guidedtrack.com/programs/1pvomgo/run?p=supporter",
                                 "Something went wrong")
    assert "never reached Stripe" in stuck and "Something went wrong" in stuck
    assert "does not show" in shc.checkout_problem("navigator", STRIPE_URL, STRIPE_TEXT)
    assert "no price" in shc.checkout_problem("supporter", STRIPE_URL, STRIPE_TEXT.replace("$9.00", ""))


def test_evaluate_checkout_reports_each_broken_tier():
    def page_for(tier):
        return STRIPE_URL, STRIPE_TEXT.replace("Supporter", tier.title())

    outcomes = {t: page_for(t) for t in shc.TIERS}
    assert shc.evaluate_checkout(outcomes).status == PASS
    outcomes["explorer"] = ("https://www.guidedtrack.com/programs/1pvomgo/run", "")
    result = shc.evaluate_checkout(outcomes)
    assert result.status == FAIL and len(result.problems) == 1 and result.problems[0].startswith("explorer")


# ---- beehiiv -------------------------------------------------------------------------------------
START, END = 1_000_000.0, 1_086_400.0
NOW = END + 12 * 3600


def test_beehiiv_healthy_by_hand():
    # 3 subscribers yesterday, 1 today (30 minutes ago), 1 before yesterday (ignored by the count).
    created = [NOW - 1800, END - 10, START + 5, START, START - 1]
    result = shc.evaluate_beehiiv(created, START, END, NOW, ga4_submitted=None)
    assert result.status == PASS and result.summary.startswith("3 API subscribers yesterday, newest 30 minutes")


def test_beehiiv_stale_or_empty_fails():
    assert shc.evaluate_beehiiv([], START, END, NOW, None).status == FAIL
    fresh_enough = [NOW - 3 * 3600, START]
    assert shc.evaluate_beehiiv(fresh_enough, START, END, NOW, None).status == PASS
    stale = shc.evaluate_beehiiv([NOW - 3 * 3600 - 60, START], START, END, NOW, None)
    assert stale.status == FAIL and "hours old" in stale.problems[0]
    none_yesterday = shc.evaluate_beehiiv([NOW - 60], START, END, NOW, None)
    assert none_yesterday.status == FAIL and "yesterday" in none_yesterday.problems[0]


def test_beehiiv_ratio_against_ga4_submitted_email():
    created = [NOW - 60] + [START + i for i in range(20)]    # 20 yesterday
    assert shc.MIN_SHARE_OF_SUBMITTED == 0.20
    assert shc.evaluate_beehiiv(created, START, END, NOW, ga4_submitted=100).status == PASS   # exactly 20%
    low = shc.evaluate_beehiiv(created, START, END, NOW, ga4_submitted=101)
    assert low.status == FAIL and "not reaching beehiiv" in low.problems[0]
    # Too few GA4 events to judge the ratio, or GA4 unavailable: freshness alone decides.
    few = [NOW - 60, START]
    assert shc.evaluate_beehiiv(few, START, END, NOW, ga4_submitted=shc.MIN_SUBMITTED_FOR_RATIO - 1).status == PASS
    assert shc.evaluate_beehiiv(few, START, END, NOW, ga4_submitted=shc.MIN_SUBMITTED_FOR_RATIO).status == FAIL
    assert shc.evaluate_beehiiv(few, START, END, NOW, ga4_submitted=None).status == PASS


def test_beehiiv_realistic_healthy_and_broken_days():
    # Healthy: ~780 sign-ups spread over yesterday and still arriving (the real 2026-09-30 shape).
    healthy = [NOW - 120] + [START + i * 110 for i in range(780)]
    assert shc.evaluate_beehiiv(healthy, START, END, NOW, ga4_submitted=728).status == PASS
    # Broken: the GuidedTrack -> beehiiv call started failing at 02:00, 5% through the day's sign-ups.
    broken = [START + i * 110 for i in range(39)]
    result = shc.evaluate_beehiiv(broken, START, END, NOW, ga4_submitted=728)
    assert result.status == FAIL and len(result.problems) == 2


# ---- retry and the Context -----------------------------------------------------------------------
def test_run_check_retries_once_and_keeps_the_second_result(monkeypatch):
    calls, sleeps = [], []
    outcomes = iter([CheckResult("x", FAIL, ""), CheckResult("x", PASS, "fine")])
    monkeypatch.setitem(shc.CHECKS, "pages", lambda ctx: calls.append(1) or next(outcomes))
    ctx = shc.Context()
    result = shc.run_check("pages", ctx, retry=True, sleep=sleeps.append)
    assert result.status == PASS and len(calls) == 2 and sleeps == [shc.RETRY_WAIT_SECONDS]


def test_run_check_does_not_retry_a_pass_or_when_disabled(monkeypatch):
    calls = []
    monkeypatch.setitem(shc.CHECKS, "pages", lambda ctx: calls.append(1) or CheckResult("x", FAIL, ""))
    assert shc.run_check("pages", shc.Context(), retry=False).status == FAIL and len(calls) == 1
    monkeypatch.setitem(shc.CHECKS, "pages", lambda ctx: calls.append(1) or CheckResult("x", PASS, ""))
    assert shc.run_check("pages", shc.Context(), retry=True, sleep=None).status == PASS and len(calls) == 2


def test_a_crashing_check_is_reported_as_could_not_check(monkeypatch):
    def boom(ctx):
        raise SystemExit("Missing secrets/ga4-token.json")

    monkeypatch.setitem(shc.CHECKS, "ga4", boom)
    result = shc.run_check("ga4", shc.Context(), retry=False)
    assert result.status == UNKNOWN and result.name == shc.NAMES["ga4"]
    assert "ga4-token.json" in result.problems[0]


def test_ga4_yesterday_uses_the_us_eastern_day():
    # 03:00 UTC on Oct 1 is still Sep 30 in New York, so "yesterday" is Sep 29.
    assert shc.ga4_yesterday(datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)) == date(2026, 9, 29)
    assert shc.ga4_yesterday(datetime(2026, 10, 1, 5, 0, tzinfo=timezone.utc)) == date(2026, 9, 30)


def test_every_check_has_a_name():
    assert set(shc.NAMES) == set(shc.CHECKS)


# ---- the daily email --------------------------------------------------------------------------------
def test_email_when_everything_passes():
    results = [CheckResult("GA4 key events (site-wide)", PASS, "Viewed 1,735 on 2026-10-01"),
               CheckResult("Stripe checkout", PASS, "all 3 tiers reach a Stripe checkout")]
    subject, body = shc.compose_email(results, date(2026, 10, 2))
    assert subject == "Website Checks - 2026-10-02: all passed"
    assert body == "All 2 checks passed.\n\nGA4 key events (site-wide): OK\nStripe checkout: OK"


def test_email_lists_every_check_in_run_order_with_reasons_under_the_ones_that_did_not_pass():
    results = [CheckResult("Pages", PASS, "21 pages load"),
               CheckResult("Checkout", FAIL, "", ["navigator: never reached Stripe", "explorer: no price"]),
               CheckResult("beehiiv", UNKNOWN, "", ["HTTPError: 401"]),
               CheckResult("Links", PASS, "fine")]
    subject, body = shc.compose_email(results, date(2026, 10, 2))
    assert subject == "Website Checks - 2026-10-02: 1 failed, 1 could not check"
    assert body == ("2 of 4 checks did not pass.\n\n"
                    "Pages: OK\n"
                    "Checkout: FAILED\n    navigator: never reached Stripe\n    explorer: no price\n"
                    "beehiiv: COULD NOT CHECK\n    HTTPError: 401\n"
                    "Links: OK")
    assert "\u2014" not in subject + body   # Igor's rule: no em dashes


def test_outcome_counts_each_kind_of_bad_result():
    ok, bad, unk = (CheckResult("x", status, "") for status in (PASS, FAIL, UNKNOWN))
    assert shc.outcome([ok, ok]) == "all passed"
    assert shc.outcome([ok, bad]) == "1 failed"
    assert shc.outcome([bad, ok, bad]) == "2 failed"
    assert shc.outcome([unk, ok]) == "1 could not check"
    assert shc.outcome([unk, bad, unk]) == "1 failed, 2 could not check"


def test_report_date_is_igors_local_date():
    # 01:30 UTC on Oct 3 is still Oct 2 in Sao Paulo (UTC-3).
    assert shc.report_date(datetime(2026, 10, 3, 1, 30, tzinfo=timezone.utc)) == date(2026, 10, 2)
    assert shc.report_date(datetime(2026, 10, 3, 3, 0, tzinfo=timezone.utc)) == date(2026, 10, 3)


def run_main(monkeypatch, argv, results, delivered=True):
    """Run main() with the checks and the transport faked; returns (exit code, emails sent)."""
    sent = []
    for key, result in zip(shc.CHECKS, results):
        monkeypatch.setitem(shc.CHECKS, key, lambda ctx, r=result: r)
    monkeypatch.setattr(shc, "send", lambda subject, body: sent.append((subject, body)) or delivered)
    monkeypatch.setattr(sys, "argv", ["site_health_check.py", "--no-retry"] + argv)
    return shc.main(), sent


def test_main_sends_exactly_one_email_and_exits_zero_even_when_a_check_fails(monkeypatch):
    results = [CheckResult(shc.NAMES[k], PASS, "") for k in shc.CHECKS]
    code, sent = run_main(monkeypatch, [], results)
    assert code == 0 and len(sent) == 1 and sent[0][1].startswith("All 6 checks passed.")
    results[3] = CheckResult(shc.NAMES["links"], FAIL, "", ["/coaching: bad link"])
    code, sent = run_main(monkeypatch, [], results)
    assert code == 0 and len(sent) == 1
    assert "1 of 6 checks did not pass." in sent[0][1] and "FAILED\n    /coaching: bad link" in sent[0][1]


def test_main_exits_non_zero_only_when_the_email_cannot_be_sent(monkeypatch):
    results = [CheckResult(shc.NAMES[k], PASS, "") for k in shc.CHECKS]
    code, sent = run_main(monkeypatch, [], results, delivered=False)
    assert code == 1 and len(sent) == 1


def test_dry_run_sends_nothing(monkeypatch, capsys):
    results = [CheckResult(shc.NAMES[k], PASS, "") for k in shc.CHECKS]
    code, sent = run_main(monkeypatch, ["--dry-run"], results)
    assert code == 0 and sent == [] and "Subject: Website Checks - " in capsys.readouterr().out
