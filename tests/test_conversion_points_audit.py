"""Tests for reports/conversion_points_audit_2026-11-06_src/analysis.py.

Three layers: hand-worked unit cases, tiny synthetic joins whose answer is known by construction,
and two realistic synthetic raw folders (same file structure as the real pull) run through the whole
builder: a NULL one (no promotion works, nobody buys) and a POSITIVE one (a known funnel).
"""
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reports" / "conversion_points_audit_2026-11-06_src"))
import analysis as A  # noqa: E402


# ------------------------------------------------------------------ hand-worked unit cases
def test_pct_and_wilson_by_hand():
    assert A.pct(1, 4) == 25.0
    assert A.pct(1, 0) is None
    assert A.wilson(0, 0) == (None, None)
    # Wilson 95% for 5/10 is 0.2366 to 0.7634 (textbook value)
    assert A.wilson(5, 10) == (23.66, 76.34)
    # for 0/10 the lower bound is 0 and the upper bound is z^2 / (n + z^2) = 3.8416 / 13.8416 = 27.75%
    assert A.wilson(0, 10) == (0.0, 27.75)
    assert A.rate(5, 10) == {"k": 5, "n": 10, "pct": 50.0, "lo": 23.66, "hi": 76.34}


def test_url_param_and_truncated_campaign():
    url = "https://www.clearerthinking.org/coaching?utm_source=tools&utm_medium=banner&utm_campaign=tools_floating_button"
    assert A.url_param(url, "utm_campaign") == "tools_floating_button"
    assert A.url_param(url, "missing") is None
    assert A.url_param(None, "x") is None
    # GA4 cuts linkUrl at 100 characters: the value arrives as a prefix
    assert A.campaign_is("tools_float", "tools_floating_button")
    assert A.campaign_is("tools_floating_button", "tools_floating_button")
    assert not A.campaign_is("tools", "tools_floating_button")          # too short to be trusted
    assert not A.campaign_is("coaching_floating_button", "tools_floating_button")
    assert not A.campaign_is(None, "tools_floating_button")
    assert A.campaign_is("ct_produ", "ct_product_grid_")                 # truncated grid link
    assert not A.campaign_is("ct_product_grid_plus", "ct_product_grid_")  # a full value must be compared in full


def test_week_of():
    assert A.week_of("2026-11-05") == "2026-11-02"   # a Thursday
    assert A.week_of("20261102") == "2026-11-02"     # the Monday itself
    assert A.week_of("2026-11-08") == "2026-11-02"   # Sunday belongs to the same week


def test_ga_clock_to_utc_across_the_dst_change():
    # 27 Oct 2026 is still daylight time in New York (UTC-4); DST ends on 1 Nov 2026 (UTC-5 after)
    assert A.ga_minute_to_utc("202610270930").strftime("%Y-%m-%d %H:%M") == "2026-10-27 13:30"
    assert A.ga_minute_to_utc("202611020930").strftime("%Y-%m-%d %H:%M") == "2026-11-02 14:30"


def test_source_group():
    g = A.source_group
    assert g("tools", "banner", "tools_floating_button") == "Floating buttons"
    assert g("programs", "banner", "ct_product_grid_plus") == "Product grid"
    assert g("clearerthinking.beehiiv.com", "newsletter", "x") == "Email"
    assert g("google", "cpc", "(referral)") == "Paid ads"
    assert g("google", "organic", "(organic)") == "Organic search"
    assert g("(direct)", "(none)", "(not set)") == "Direct"
    assert g("(not set)", "(not set)", "(not set)") == "Unattributed"
    assert g("t.co", "referral", "(referral)") == "Referral"
    assert g("unique_traits", "tool_report", "coaching_cta_unique_traits") == "Other on-site links"


def test_subscribe_run_drops_health_checks_and_team_tests():
    base = {"Time Started (UTC)": "2026-10-01 10:00:00", "p": "navigator", "email": "", "raw_email": "", "src": "",
            "wasRedirected": "0", "status": ""}
    assert A.subscribe_run({**base, "src": "healthcheck"}) is None
    assert A.subscribe_run({**base, "email": "igormscaldini+x@gmail.com"}) is None
    r = A.subscribe_run({**base, "email": "reader@example.com", "wasRedirected": "1", "status": "none"})
    assert r == {"time": "2026-10-01 10:00:00", "plan": "navigator", "gave_email": True, "reached_checkout": True, "already_member": False}
    assert A.subscribe_run({**base, "status": "active", "email": "m@example.com"})["already_member"] is True
    assert A.subscribe_run(base)["gave_email"] is False


def test_classify_session():
    typ = "https://www.clearerthinking.org/typ-ct-ambassador"
    c = A.classify_session
    assert c({"mode": "subscription", "amount_total": 9900, "success_url": typ, "email": "a@example.com", "metadata": {}}) == ("navigator", True)
    assert c({"mode": "subscription", "amount_total": 2900, "success_url": typ, "metadata": {"product_key": "explorer", "user_email": "a@example.com"}}) == ("explorer", True)
    assert c({"mode": "subscription", "amount_total": 900, "success_url": "https://programs.clearerthinking.org/members-only-content-x/", "metadata": {}}) == ("supporter_article", True)
    assert c({"mode": "subscription", "amount_total": 9900, "success_url": typ, "metadata": {"user_email": "igormscaldini+healthcheck@gmail.com"}}) == ("navigator", False)
    assert c({"mode": "payment", "amount_total": 3500, "success_url": "https://www.guidedtrack.com/programs/to8e8we/users/sign_up", "metadata": {}}) == ("cognitive", True)
    assert c({"mode": "payment", "amount_total": 900, "success_url": "https://craftmypdf-gen.s3.amazonaws.com/abc.pdf", "metadata": {}}) == ("pdf", True)
    assert c({"mode": "payment", "amount_total": 9991, "success_url": typ, "metadata": {}}) == ("other", True)
    assert c({"mode": "subscription", "amount_total": 1990, "success_url": typ, "metadata": {}}) == ("other", True)


def test_sub_tier():
    ok = {"product_name": "Clearer Thinking Plus - Navigator (4 Monthly Coaching Sessions)", "status": "active", "email": "a@example.com"}
    assert A.sub_tier(ok) == "navigator"
    assert A.sub_tier({**ok, "product_name": "Clearer Thinking Plus - Supporter"}) == "supporter"
    assert A.sub_tier({**ok, "status": "incomplete_expired"}) is None
    assert A.sub_tier({**ok, "email": "joshrcastle+ga4tests@gmail.com"}) is None
    assert A.sub_tier({**ok, "product_name": "Clearer Thinking Supporter"}) is None     # the legacy, pre-CT+ product
    # team tests are cancelled the same day; a real customer who leaves after five days still counts
    assert A.sub_tier({**ok, "status": "canceled", "created": "2026-10-15 13:50:28", "ended": "2026-10-15 14:02:00"}) is None
    assert A.sub_tier({**ok, "status": "canceled", "created": "2026-10-28 10:00:00", "ended": "2026-11-02 08:00:00"}) == "navigator"


def test_article_paywall_checkouts_before_the_first_send_are_tests(tmp_path):
    _write_raw(tmp_path, positive=True)
    st = json.loads((tmp_path / "stripe.json").read_text())
    art = "https://programs.clearerthinking.org/members-only-content-supplement-paradox/"
    mk = lambda sid, created, status, sub: {"id": sid, "created": created, "mode": "subscription", "status": status, "amount_total": 900,  # noqa: E731
                                            "email": f"{sid}@example.com", "success_url": art, "metadata": {}, "pi": None, "subscription": sub}
    sub = lambda sid, created, ended, status: {"id": sid, "created": created, "ended": ended, "status": status, "email": f"{sid}@example.com",  # noqa: E731
                                               "amount": 900, "product": "p", "product_name": "Clearer Thinking Plus - Supporter", "cancel_reason": None}
    st["sessions"] += [mk("cs_pre", "2026-10-15 13:50:00", "complete", "sub_pre"),      # before the send: a rehearsal
                       mk("cs_ok", "2026-10-17 02:25:00", "complete", "sub_ok"),        # a real reader
                       mk("cs_left", "2026-10-23 13:42:00", "expired", None)]           # a real reader who did not pay
    st["subs"] += [sub("sub_pre", "2026-10-15 13:50:30", "2026-10-15 13:58:00", "canceled"), sub("sub_ok", "2026-10-17 02:25:30", None, "active")]
    (tmp_path / "stripe.json").write_text(json.dumps(st))
    dp = A.build_datapoints(tmp_path)
    assert dp["ctplus_funnel"]["article_paywall"] == {"stripe_checkouts": 2, "stripe_completed": 1, "paid_subs": 1}
    assert dp["ctplus_funnel"]["by_tier"]["supporter"]["paid_subs"] == 0          # the paywall sale is not double counted in the sign-up flow


@pytest.mark.parametrize("amount,refunded,desc,status", [
    (900, 0, None, "succeeded"), (900, 0, "Subscription creation", "succeeded"), (3500, 0, "", "succeeded"),
    (1750, 0, None, "succeeded"), (3500, 3500, None, "succeeded"), (9900, 0, "Subscription update", "succeeded"),
    (500, 0, None, "succeeded"), (900, 0, None, "failed"),
])
def test_charge_kind_agrees_with_the_dashboard_rule(amount, refunded, desc, status):
    """One source of truth: the audit must bucket a charge exactly like data_layer._charge_bucket."""
    import data_layer

    ours = A.charge_kind({"amount": amount, "refunded": refunded, "desc": desc, "status": status})
    theirs = data_layer._charge_bucket(SimpleNamespace(id="ch_x", status=status, amount=amount, amount_refunded=refunded,
                                                       description=desc, invoice=None))
    expected = None if theirs is None else {"subscriptions": "subscription"}.get(theirs[0], theirs[0])
    assert ours == expected


# ------------------------------------------------------------------ joins with a known answer
FP_A = {"city": "Austin", "deviceCategory": "mobile", "browser": "Safari", "operatingSystem": "iOS", "screenResolution": "390x844"}
FP_B = {"city": "Leeds", "deviceCategory": "desktop", "browser": "Chrome", "operatingSystem": "Windows", "screenResolution": "1920x1080"}


def test_collapse_purchase_events_keeps_the_first_reload():
    rows = [{**FP_A, "dateHourMinute": "202610271005"}, {**FP_A, "dateHourMinute": "202610271001"},
            {**FP_B, "dateHourMinute": "202610271001"}, {**FP_A, "dateHourMinute": "202610280900"}]
    out = A.collapse_purchase_events(rows)
    assert [(r["city"], r["dateHourMinute"]) for r in out] == [("Austin", "202610271001"), ("Leeds", "202610271001"), ("Austin", "202610280900")]


def test_match_purchases_by_hand():
    # GA4 clock 10:01 on 27 Oct = 14:01 UTC. Sub 0 was created at 13:59 UTC (2 min before the page view): match.
    # Sub 1 was created a day earlier: no match. Sub 2 was created at 14:20 UTC, 19 min AFTER the event: no match.
    events = [{"dateHourMinute": "202610271001"}]
    subs = [{"created": "2026-10-27 13:59:10"}, {"created": "2026-10-26 13:59:10"}, {"created": "2026-10-27 14:20:00"}]
    assert A.match_purchases(events, subs) == [(0, 0)]


def test_match_purchases_is_one_to_one_and_picks_the_closest():
    events = [{"dateHourMinute": "202610271001"}, {"dateHourMinute": "202610271004"}]
    subs = [{"created": "2026-10-27 14:03:30"}, {"created": "2026-10-27 14:00:30"}]
    # event 0 (14:01) is 0.5 min after sub 1; event 1 (14:04) is 0.5 min after sub 0
    assert A.match_purchases(events, subs) == [(0, 1), (1, 0)]


def test_match_purchases_null_case_shifted_times_match_nothing():
    events = [{"dateHourMinute": f"202610{d:02d}1001"} for d in range(10, 20)]
    subs = [{"created": f"2026-10-{d:02d} 02:00:00"} for d in range(10, 20)]      # 12 hours away from every event
    assert A.match_purchases(events, subs) == []


def test_touches_before_respects_fingerprint_and_lookback():
    ev = {**FP_A, "dateHourMinute": "202610271001"}
    fab = "https://www.clearerthinking.org/coaching?utm_source=tools&utm_medium=banner&utm_campaign=tools_floating_button"
    views = [
        {**FP_A, "dateHourMinute": "202610270955", "pagePath": "/coaching", "pageLocation": fab},                                     # counts
        {**FP_A, "dateHourMinute": "202610261200", "pagePath": "/plus", "pageLocation": "https://www.clearerthinking.org/plus"},      # counts
        {**FP_A, "dateHourMinute": "202610201200", "pagePath": "/coaching", "pageLocation": fab},                                     # 7 days back: too old
        {**FP_A, "dateHourMinute": "202610271100", "pagePath": "/coaching", "pageLocation": fab},                                     # after the purchase
        {**FP_B, "dateHourMinute": "202610270955", "pagePath": "/coaching", "pageLocation": fab},                                     # another browser
    ]
    assert A.touches_before(ev, views, lookback_days=3) == [{"page": "/coaching", "label": "tools floating button"},
                                                            {"page": "/plus", "label": "other / untagged"}]


def test_touch_label():
    base = "https://www.clearerthinking.org/coaching"
    assert A.touch_label(base + "?utm_campaign=coaching_floating_button") == "www floating button"
    assert A.touch_label(base + "?src=tools_fab") == "tools floating button"
    assert A.touch_label(base + "?utm_source=programs&utm_medium=banner&utm_campaign=ct_product_grid_coaching") == "product grid"
    assert A.touch_label(base + "?utm_campaign=coaching_cta_unique_traits") == "in-tool coaching CTA"
    assert A.touch_label(base + "?_bhlid=abc") == "email"
    assert A.touch_label(base) == "other / untagged"


def test_label_base_rates_null_and_positive():
    fab = "https://www.clearerthinking.org/coaching?utm_campaign=tools_floating_button"
    e1, e2 = {**FP_A, "dateHourMinute": "202610271001"}, {**FP_B, "dateHourMinute": "202610281001"}
    # NULL: each buyer only has views before their OWN purchase, far from the other's -> swapping fingerprints finds nothing
    views = [{**FP_A, "dateHourMinute": "202610270955", "pagePath": "/coaching", "pageLocation": fab}]
    rates, n = A.label_base_rates([e1, e2], views, lookback_days=0.01)
    assert n == 2 and rates == {}
    # POSITIVE by construction: browser B viewed the tagged page just before A's purchase time, so the swap (A's time, B's
    # fingerprint) carries the label in 1 of the 2 pseudo pairs = 50%
    views.append({**FP_B, "dateHourMinute": "202610271000", "pagePath": "/coaching", "pageLocation": fab})
    rates, n = A.label_base_rates([e1, e2], views, lookback_days=0.01)
    assert rates == {"tools floating button": 50.0}


# ------------------------------------------------------------------ whole builder on realistic synthetic raw folders
SUB_COLS = ["Time Started (UTC)", "p", "selectedPlan", "selected_plan", "email", "raw_email", "src", "wasRedirected", "was_redirected", "status"]
COG_COLS = ["Time Started (UTC)", "email", "TEST_MODE", "utm_campaign", "utm_medium", "gclid", "gbraid", "wbraid", "cameFromEndCard",
            "referringProgram", "wasRedirectedToPayment", "gad_campaignid"]
TYP = "https://www.clearerthinking.org/typ-ct-ambassador"


def _write_raw(folder, positive):
    """A raw folder shaped like fetch_data.py's output. NULL: traffic but no clicks and no sales.
    POSITIVE: 1,000 exposed www users of whom 20 clicked the button; 4 Navigator clicks -> 2 checkouts -> 1 paid,
    whose thank-you event follows a tools-button visit; 3 PDF sales from 300 finishers; 2 cognitive sales, 1 from the grid."""
    k = 1 if positive else 0
    fab_url = "https://www.clearerthinking.org/coaching?utm_source=tools&utm_medium=banner&utm_campaign=tools_floating_button"
    lp = lambda path, users: {"pagePath": path, "totalUsers": users, "sessions": users, "engagedSessions": users // 2,  # noqa: E731
                              "screenPageViews": users, "userEngagementDuration": users * 10.0}
    src = lambda path, s, m, c, n: {"pagePath": path, "sessionSource": s, "sessionMedium": m, "sessionManualCampaignName": c,  # noqa: E731
                                    "totalUsers": n, "sessions": n, "engagedSessions": n // 2, "screenPageViews": n, "userEngagementDuration": n * 10.0}
    ga = {
        "lp_totals": [lp("/coaching", 200), lp("/plus", 50), lp("/cognitive-test-intro.html", 100), lp("/getmyreport.html", 10),
                      lp("/personality-test-pdf-generator/", 30)],
        "lp_daily": [{"date": "20261027", **lp("/coaching", 200)}, {"date": "20261027", **lp("/plus", 50)}],
        "lp_sources": [src("/coaching", "google", "organic", "(organic)", 100), src("/coaching", "tools", "banner", "tools_floating_button", 40 * k),
                       src("/coaching", "website", "banner", "coaching_floating_button", 20 * k), src("/plus", "(direct)", "(none)", "(not set)", 50)],
        "utm_landings": [{"date": "20261027", "pagePath": "/coaching", "pageLocation": fab_url, "sessionSource": "tools", "screenPageViews": 40 * k},
                         {"date": "20261027", "pagePath": "/coaching", "pageLocation": fab_url, "sessionSource": "(not set)", "screenPageViews": 500}],
        "campaign_landings": [{"key": key, "period": "window", "users": 0, "views": 0, "sessions": 0, "bot_views": 0} for key, _, _ in A.CAMPAIGN_LANDINGS]
        + [{"key": "tools_fab", "period": p, "users": 30 * k, "views": 40 * k, "sessions": 30 * k, "bot_views": 0} for p in A.FAB_PERIODS],
        "fab_tools_clicks": {p: {"eventCount": 50 * k, "totalUsers": 45 * k} for p in A.FAB_PERIODS},
        "www_users_ex_coaching": [{"totalUsers": 1000}],
        "clicks_to_www": [{"date": "20261027", "pagePath": "/who_attracts_you_study.html", "linkUrl": fab_url[:100], "eventCount": 50 * k, "totalUsers": 45 * k},
                          {"date": "20261027", "pagePath": "/unique-traits-test/", "linkUrl": "https://www.clearerthinking.org/coaching", "eventCount": 5 * k, "totalUsers": 5 * k},
                          {"date": "20261027", "pagePath": "/personality-test.html", "eventCount": 7 * k, "totalUsers": 7 * k,
                           "linkUrl": "https://www.clearerthinking.org/plus?utm_source=programs&utm_medium=banner&utm_campaign=ct_product_g"}],
        "tool_events": [{"pagePath": "/personality-test.html", "eventName": "Submitted Email", "eventCount": 300, "totalUsers": 300},
                        {"pagePath": "/personality-test.html", "eventName": "Accepted Privacy Policy", "eventCount": 600, "totalUsers": 600},
                        {"pagePath": "/how_rational_are_you_really_take_the_test.html", "eventName": "Submitted Email", "eventCount": 100, "totalUsers": 100},
                        {"pagePath": "/unique-traits-test/", "eventName": "Finished Exercise", "eventCount": 250, "totalUsers": 250}],
        "tool_events_monthly": [{"yearMonth": "202610", "pagePath": "/personality-test.html", "eventName": "Submitted Email", "eventCount": 300, "totalUsers": 300}],
        "pdf_page_referrers": [{"pagePath": "/personality-test-pdf-generator/", "pageReferrer": "https://programs.clearerthinking.org/personality-test.html",
                                "screenPageViews": 30, "totalUsers": 30}],
        "purchase_events": [{**FP_A, "dateHourMinute": "202610271001", "sessionSourceMedium": "(direct) / (none)", "sessionManualCampaignName": "(not set)",
                             "eventCount": 2}] * k,
        "lp_views_fp": [{**FP_A, "dateHourMinute": "202610270950", "pagePath": "/coaching", "pageLocation": fab_url, "screenPageViews": 1}] * k,
    }
    for p in A.FAB_PERIODS:
        ga[f"programs_users_{p}"] = [{"totalUsers": 900}]
        ga[f"programs_pages_{p}"] = [{"pagePath": "/who_attracts_you_study.html", "totalUsers": 500}]
    for row in ga["campaign_landings"]:
        if row["key"] == "www_fab":
            row.update(users=20 * k, views=25 * k, sessions=20 * k, bot_views=7)
        if row["key"] == "grid_cognitive":
            row.update(users=10 * k, views=12 * k)
    (folder / "ga4.json").write_text(json.dumps(ga))

    sess = lambda sid, mode, amt, status, url, email, sub=None: {  # noqa: E731
        "id": sid, "created": "2026-10-27 13:58:00", "mode": mode, "status": status, "amount_total": amt, "email": email,
        "success_url": url, "metadata": {}, "pi": None, "subscription": sub}
    stripe = {"subs": [], "charges": [], "sessions": [
        sess("cs_hc", "subscription", 9900, "expired", TYP, "igormscaldini+healthcheck@gmail.com")]}     # must never count
    if positive:
        stripe["subs"] = [{"id": "sub_1", "created": "2026-10-27 13:59:30", "ended": None, "status": "active", "email": "buyer@example.com",
                           "amount": 9900, "product": "prod_n", "product_name": "Clearer Thinking Plus - Navigator", "cancel_reason": None}]
        stripe["sessions"] += [sess("cs_1", "subscription", 9900, "complete", TYP, "buyer@example.com", "sub_1"),
                               sess("cs_2", "subscription", 9900, "expired", TYP, "walker@example.com"),
                               sess("cs_p1a", "payment", 900, "complete", "https://craftmypdf-gen.s3.amazonaws.com/a.pdf", "p1@example.com"),
                               sess("cs_p1b", "payment", 900, "expired", "https://craftmypdf-gen.s3.amazonaws.com/a.pdf", "p1@example.com"),
                               sess("cs_p2", "payment", 900, "expired", "https://craftmypdf-gen.s3.amazonaws.com/b.pdf", None),
                               sess("cs_c1", "payment", 3500, "complete", "https://www.guidedtrack.com/programs/to8e8we/users/sign_up", "grid@example.com"),
                               sess("cs_c2", "payment", 3500, "complete", "https://www.guidedtrack.com/programs/to8e8we/users/sign_up", "direct@example.com")]
        ch = lambda cid, amt, email, desc=None: {"id": cid, "created": "2026-10-27 14:00:00", "amount": amt, "refunded": 0,  # noqa: E731
                                                 "status": "succeeded", "desc": desc, "pi": None, "email": email}
        stripe["charges"] = [ch("ch_p1", 900, "p1@example.com"), ch("ch_p2", 900, "p2@example.com"), ch("ch_p3", 900, "p3@example.com"),
                             ch("ch_c1", 3500, "grid@example.com"), ch("ch_c2", 3500, "direct@example.com"),
                             ch("ch_s1", 9900, "buyer@example.com", "Subscription creation")]
    (folder / "stripe.json").write_text(json.dumps(stripe))

    run = lambda **kw: {**dict.fromkeys(SUB_COLS, ""), "Time Started (UTC)": "2026-10-27 13:50:00", **kw}  # noqa: E731
    sub_runs = [run(p="navigator", src="healthcheck", email="igormscaldini+healthcheck@gmail.com")]
    if positive:
        sub_runs += [run(p="navigator", email="buyer@example.com", wasRedirected="1", status="none"),
                     run(p="navigator", email="walker@example.com", wasRedirected="1", status="none"),
                     run(p="navigator"), run(p="navigator"), run(p="explorer"),
                     run(**{"Time Started (UTC)": "2026-06-01 10:00:00"}, p="navigator")]                 # before the window
    cog = lambda **kw: {**dict.fromkeys(COG_COLS, ""), "Time Started (UTC)": "2026-10-27 13:00:00", "wasRedirectedToPayment": "0", **kw}  # noqa: E731
    cog_runs = [cog() for _ in range(20)] + [cog(gclid=f"g{i}", gad_campaignid=A.UNLINKED_ADS_CAMPAIGN) for i in range(10)]
    if positive:
        cog_runs += [cog(utm_campaign="ct_product_grid_cognitive", utm_medium="banner", email="grid@example.com", wasRedirectedToPayment="1"),
                     cog(utm_campaign="ct_product_grid_cognitive", utm_medium="banner"),
                     cog(email="direct@example.com", wasRedirectedToPayment="1"),
                     cog(gclid="gx", gad_campaignid=A.UNLINKED_ADS_CAMPAIGN, email="adclick@example.com", wasRedirectedToPayment="1")]
    for name, cols, rows in (("gt_subscribe.csv", SUB_COLS, sub_runs), ("gt_cognitive_intro.csv", COG_COLS, cog_runs)):
        with open(folder / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


def test_builder_null_dataset(tmp_path):
    _write_raw(tmp_path, positive=False)
    dp = A.build_datapoints(tmp_path)
    assert dp["fab_www"]["ctr"] == {"k": 0, "n": 1000, "pct": 0.0, "lo": 0.0, "hi": 0.38}
    assert dp["fab_tools"]["periods"]["fab_all"]["clicks"] == 0
    assert all(v == {"signup_clicks": 0, "already_member": 0, "gave_email": 0, "reached_checkout": 0, "stripe_checkouts": 0,
                     "stripe_completed": 0, "paid_subs": 0, "cancelled_within_14d": 0, "still_active": 0, "first_month_revenue": 0.0}
               for v in dp["ctplus_funnel"]["by_tier"].values())
    assert dp["ctplus_funnel"]["test_sessions_excluded"] == 1
    assert dp["purchases"]["matched"] == 0 and dp["purchases"]["by_touch"] == {}
    assert dp["cognitive"]["paid_charges"] == 0 and dp["cognitive"]["runs"] == 30
    assert dp["cognitive"]["unlinked_ads_campaign"]["runs"] == 10 and dp["cognitive"]["unlinked_ads_campaign"]["paid"] == 0
    assert dp["pdf"]["paid_charges"] == 0 and dp["pdf"]["per_finisher"]["pct"] == 0.0
    assert dp["tool_ctas"]["unique_traits"]["clicks"] == 0
    # the 500 scanner hits (session source "(not set)") must not show up as button landings
    assert sum(w["tools_fab_landings"] for w in dp["weekly"]) == 0


def test_builder_positive_dataset(tmp_path):
    _write_raw(tmp_path, positive=True)
    dp = A.build_datapoints(tmp_path)
    # www button: 20 of 1,000 exposed users = 2.0%
    assert dp["fab_www"]["ctr"]["pct"] == 2.0 and dp["fab_www"]["bot_views_excluded"] == 7
    # tools button: 45 clicking users of 900 = 5.0%; 50 clicks from a page with 500 users = 10 per 100
    p = dp["fab_tools"]["periods"]["fab_all"]
    assert p["ctr"]["pct"] == 5.0 and p["by_page"] == [{"page": "/who_attracts_you_study.html", "clicks": 50, "page_users": 500, "clicks_per_100_users": 10.0}]
    # Navigator: 4 clicks in the window (health check and the June run dropped), 2 reached checkout, 2 Stripe checkouts, 1 paid
    nav = dp["ctplus_funnel"]["by_tier"]["navigator"]
    assert (nav["signup_clicks"], nav["gave_email"], nav["reached_checkout"], nav["stripe_checkouts"], nav["stripe_completed"], nav["paid_subs"]) == (4, 2, 2, 2, 1, 1)
    assert nav["first_month_revenue"] == 99.0 and dp["ctplus_funnel"]["by_tier"]["explorer"]["signup_clicks"] == 1
    # the one purchase is matched and carries the tools-button touch on /coaching
    assert dp["purchases"]["matched"] == 1 and dp["purchases"]["by_touch"] == {"tools floating button": 1} and dp["purchases"]["by_page"] == {"/coaching": 1}
    # cognitive: 34 runs, 3 sent to payment, 2 paid; the grid brought 2 runs and 1 sale; the ad campaign 11 runs, 1 checkout, 0 sales
    c = dp["cognitive"]
    assert (c["runs"], c["to_payment"], c["paid_charges"], c["revenue"], c["stripe_checkouts"], c["stripe_completed"]) == (34, 3, 2, 70.0, 2, 2)
    assert dp["grid"]["cognitive_from_grid"] == {"group": "Product grid", "runs": 2, "to_payment": 1, "paid": 1}
    assert c["unlinked_ads_campaign"] == {"id": A.UNLINKED_ADS_CAMPAIGN, "first": "2026-10-27", "last": "2026-10-27", "runs": 11, "to_payment": 1, "paid": 0}
    # PDF: 3 sales from 300 finishers = 1.0%; 2 distinct PDFs had a checkout (a.pdf twice, b.pdf once), 1 completed
    assert dp["pdf"]["paid_charges"] == 3 and dp["pdf"]["revenue"] == 27.0 and dp["pdf"]["per_finisher"]["pct"] == 1.0
    assert (dp["pdf"]["pdfs_generated_with_checkout"], dp["pdf"]["checkouts_completed"]) == (2, 1)
    # grid: the truncated plus-card link is recognised; 10 cognitive-card users over 400 finishers = 2.5 per 100
    assert dp["grid"]["www_card_clicks_by_tool"] == [{"page": "/personality-test.html", "plus": 7}]
    assert dp["grid"]["cards"]["cognitive"]["per_100_finishers"] == 2.5
    # Unique Traits CTA: 5 clicks over 250 finishers = 2.0% (the floating-button clicks from other pages are not counted)
    assert dp["tool_ctas"]["unique_traits"]["clicks"] == 5 and dp["tool_ctas"]["unique_traits"]["ctr"]["pct"] == 2.0
    assert dp["cross_checks"]["ctplus_completed_checkouts_vs_paid_subs"] == [1, 1]
