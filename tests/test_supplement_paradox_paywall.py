"""Tests for reports/supplement_paradox_paywall_results_2026-11-06_src/analysis.py.

Three layers, as the project's data-science rules ask:
  1. tiny synthetic inputs whose answer is worked out by hand in the comments;
  2. realistic synthetic "worlds" with the same shape as the real pulls, one built to be a null
     result (nobody pays, the edition behaves like its baseline) and one built to be positive
     (planted payers, tripled unsubscribes), pushed through the real build_datapoints();
  3. the independent recount lives in cross_check.py beside the analysis (it needs the real data).
"""
import importlib.util
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "reports" / "supplement_paradox_paywall_results_2026-11-06_src" / "analysis.py"
spec = importlib.util.spec_from_file_location("sp_paywall_analysis", SRC)
az = importlib.util.module_from_spec(spec)
spec.loader.exec_module(az)

UTC = timezone.utc
SEND = datetime(2026, 10, 16, 12, 57, tzinfo=UTC)


def h(n: int) -> str:
    """A fake 32-char email hash."""
    return f"{n:032x}"


# ---------------------------------------------------------------------------------------------
# 1. hand-worked cases
# ---------------------------------------------------------------------------------------------

def test_wilson_matches_hand_calculation():
    # k=5, n=10, z=1.96: centre = (0.5 + 3.8416/20) / (1 + 0.38416) = 0.5
    # half = 1.96 * sqrt(0.25/10 + 3.8416/400) / 1.38416 = 1.96 * 0.186021 / 1.38416 = 0.26341
    lo, hi = az.wilson(5, 10)
    assert lo == pytest.approx(0.23659, abs=1e-4) and hi == pytest.approx(0.76341, abs=1e-4)
    assert az.wilson(0, 10)[0] == 0.0 and az.wilson(10, 10)[1] == 1.0
    assert az.wilson(0, 0) == (0.0, 0.0)


def test_binom_tail_by_hand():
    assert az.binom_tail(2, 2, 0.5) == pytest.approx(0.25)     # both of two coin flips
    assert az.binom_tail(1, 2, 0.5) == pytest.approx(0.75)     # at least one of two
    assert az.binom_tail(0, 7, 0.3) == pytest.approx(1.0)      # at least zero is certain
    assert az.binom_tail(3, 3, 0.1) == pytest.approx(0.001)


def test_rate_ratio_equal_windows_by_hand():
    # 1 event in each of two 7-day windows: 1 per week both, ratio 1.
    # Given 2 events, each falls in the test window with p = 0.5; P(at least 1 of 2) = 0.75.
    r = az.rate_ratio_test(1, 7, 1, 7)
    assert r["per_week_test"] == pytest.approx(1.0) and r["per_week_base"] == pytest.approx(1.0)
    assert r["ratio"] == pytest.approx(1.0) and r["p_one_sided"] == pytest.approx(0.75)


def test_rate_ratio_unequal_windows_by_hand():
    # 2 events in 10 days vs 0 in 30 days: share = 10/40 = 0.25; P(both of 2 in test) = 0.0625.
    r = az.rate_ratio_test(2, 10, 0, 30)
    assert r["per_week_test"] == pytest.approx(1.4) and r["ratio"] is None
    assert r["p_one_sided"] == pytest.approx(0.0625)


def test_compare_to_baseline_by_hand():
    base = [1.0, 2.0, 3.0]                       # mean 2, sample sd 1
    above = az.compare_to_baseline(5.0, base)    # z = 3, beyond the max
    assert above["mean"] == pytest.approx(2.0) and above["sd"] == pytest.approx(1.0)
    assert above["z"] == pytest.approx(3.0) and above["verdict"] == "above"
    assert az.compare_to_baseline(2.5, base)["verdict"] == "within"
    assert az.compare_to_baseline(3.5, base)["verdict"] == "within"   # beyond the max but only 1.5 sd
    assert az.compare_to_baseline(-1.0, base)["verdict"] == "below"   # z = -3


def run(t, hash_="", src="supplement-paradox", member="0.0", typed=""):
    return {"t": t, "src": src, "h": hash_, "isMember": member, "emailMember": typed}


def test_classify_runs_small_case_by_hand():
    runs = [
        run(SEND - timedelta(hours=1), h(1)),                                  # before the send: dropped
        run(SEND + timedelta(minutes=5), h(9)),                                # team hash: dropped
        run(SEND + timedelta(minutes=10), h(2)),                               # reader A
        run(SEND + timedelta(minutes=11), h(2)),                               # reader A reloads: same visitor
        run(SEND + timedelta(minutes=20), h(3), member="1.0"),                 # member let in by hash
        run(SEND + timedelta(minutes=30), h(4), typed="0.0"),                  # typed an email, not a member
        run(SEND + timedelta(minutes=40), "", src="supplement-paradox-web"),   # web visitor
        run(SEND + timedelta(minutes=50), "", src="supplement-paradox-web", typed="1.0"),  # web member, typed
    ]
    f = az.classify_runs(runs, SEND, team_hashes={h(9)})
    assert f["pre_send_runs"] == 1 and f["team_runs"] == 1
    e, w = f["email"], f["web"]
    assert e["runs"] == 4 and e["visitors"] == 3                 # hashes 2, 3, 4
    assert e["members_by_hash"] == 1 and e["non_member_visitors"] == 2
    assert e["typed_non_member"] == 1 and e["typed_member"] == 0
    assert w["runs"] == 2 and w["typed_member"] == 1 and w["non_member_visitors"] == 1
    assert e["typed_member_hashes"] == set()


def test_classify_runs_remembers_who_typed_their_way_in():
    runs = [run(SEND + timedelta(minutes=1), h(2), typed="1.0"), run(SEND + timedelta(minutes=2), h(3), typed="0.0")]
    e = az.classify_runs(runs, SEND, set())["email"]
    assert e["typed_member_hashes"] == {h(2)} and e["typed_member"] == 1 and e["typed_non_member"] == 1


def test_classify_runs_empty_and_all_pre_send():
    assert az.classify_runs([], SEND, set())["email"]["visitors"] == 0
    f = az.classify_runs([run(SEND - timedelta(days=1), h(1)), run(SEND - timedelta(days=2))], SEND, set())
    assert f["pre_send_runs"] == 2 and f["email"]["runs"] == 0 and f["web"]["runs"] == 0


def session(t, status="complete", email_md5=None, sub=None):
    return {"created": t, "status": status, "email_md5": email_md5, "sub": sub}


def test_match_sales_by_hash_then_by_time():
    runs = [
        run(SEND + timedelta(minutes=10), h(2)),
        run(SEND + timedelta(minutes=60), "", src="supplement-paradox-web"),
        run(SEND + timedelta(minutes=120), h(5)),
    ]
    sessions = [
        session(SEND - timedelta(hours=3), email_md5=h(99)),                       # pre-send test payment: ignored
        session(SEND + timedelta(minutes=11), email_md5=h(2), sub="sub_a"),        # email reader A pays
        session(SEND + timedelta(minutes=62), email_md5=h(7), sub="sub_b"),        # no run has hash 7: web run 2 min before
        session(SEND + timedelta(minutes=121), status="expired"),                  # abandoned, right after an email run
        session(SEND + timedelta(days=3), email_md5=h(8), sub="sub_c"),            # nothing near it
    ]
    sales = az.match_sales(sessions, runs, SEND)
    assert [(s["paid"], s["channel"]) for s in sales] == [
        (True, "email"), (True, "web"), (False, "email"), (True, "unknown")]


def post(recipients, delivered, opens, unsubs, spam, clicks=()):
    return {"stats": {"email": {"recipients": recipients, "delivered": delivered, "unique_opens": opens,
                                "unsubscribes": unsubs, "spam_reports": spam}, "clicks": list(clicks)}}


def click(url, verified):
    return {"url": url, "email": {"unique_clicks": 1, "unique_verified_clicks": verified}}


PAYWALL_URL = "https://programs.clearerthinking.org/members-only-content/?newsletter=X&src=supplement-paradox&h={}&utm_source=b"


def test_send_stats_sums_posts_and_rates_by_hand():
    s = az.send_stats([post(1000, 900, 300, 9, 3), post(1000, 1100, 100, 11, 1)])
    assert (s["recipients"], s["delivered"], s["unique_opens"], s["unsubscribes"], s["spam_reports"]) == (2000, 2000, 400, 20, 4)
    assert s["open_rate"] == pytest.approx(0.2)              # 400 / 2000
    assert s["unsub_per_delivered"] == pytest.approx(0.01)   # 20 / 2000
    assert s["unsub_per_open"] == pytest.approx(0.05)        # 20 / 400
    assert s["spam_per_delivered"] == pytest.approx(0.002) and s["spam_per_open"] == pytest.approx(0.01)
    assert az.send_stats([])["unsub_per_open"] == 0.0


def test_paywall_clickers_reads_the_hash_and_the_verified_flag():
    p = post(10, 10, 5, 0, 0, clicks=[
        click(PAYWALL_URL.format(h(1)), 1),
        click(PAYWALL_URL.format(h(2)), 0),                                    # scanner: clicked, not verified
        click("https://www.clearerthinking.org/post/the-supplement-paradox?utm_source=b", 4),
        click("https://programs.clearerthinking.org/members-only-content/?src=x", 1),   # no hash: not a subscriber row
    ])
    c = az.paywall_clickers([p, post(1, 1, 1, 0, 0, clicks=[click(PAYWALL_URL.format(h(1)), 1)])])
    assert c["all"] == {h(1), h(2)} and c["verified"] == {h(1)}
    rating = click("https://www.guidedtrack.com/programs/8uevt6x/rerun?article=" + az.WEB_POST_URL, 7)
    p["stats"]["clicks"].append(rating)                                        # carries the article URL inside its query
    assert az.link_clicks(p, az.WEB_POST_URL) == 4


def test_ratings_by_article_and_slug():
    assert az.article_slug("https://www.clearerthinking.org/post/the-supplement-paradox?utm_source=x") == "the-supplement-paradox"
    rows = [{"article": "https://www.clearerthinking.org/post/a?x=1", "final_rating": r}
            for r in ["Excellent", "Excellent", "Bad", "Subpar", "Okay"]]
    rows += [{"article": "https://www.clearerthinking.org/post/b", "final_rating": "Good"},
             {"article": "https://www.clearerthinking.org/post/b", "final_rating": ""},        # unfinished: skipped
             {"article": "ARTICLE_URL", "final_rating": "Bad"}]                               # unreplaced placeholder
    t = az.ratings_by_article(rows)
    assert t["a"]["n"] == 5 and t["a"]["low"] == 2 and t["a"]["Excellent"] == 2 and t["a"]["Good"] == 0
    assert t["b"] == {"Excellent": 0, "Good": 1, "Okay": 0, "Subpar": 0, "Bad": 0, "n": 1, "low": 0}
    assert "ARTICLE_URL" not in t


def sub(created, lookup="supporter", status="active", canceled_at=None, email_md5=None, id_="sub_x"):
    return {"id": id_, "created": created, "status": status, "canceled_at": canceled_at, "lookup": lookup,
            "amount": 900, "email_md5": email_md5}


def test_supporter_signups_drops_tests_other_tiers_and_out_of_window():
    subs = [
        sub("2026-10-17 02:25"),                                               # counted
        sub("2026-10-16 12:09", status="canceled", canceled_at="2026-10-16 12:17"),   # same-day cancel: a test
        sub("2026-10-17 01:17", status="incomplete_expired", canceled_at="2026-10-18 00:17"),   # never paid
        sub("2026-10-18 08:29", lookup="navigator"),                           # other tier
        sub("2026-10-20 10:00", status="canceled", canceled_at="2026-11-01 09:00"),   # real, later churned: counted
        sub("2026-09-21 14:15"),                                               # before the window
    ]
    got = az.supporter_signups(subs, SEND, datetime(2026, 11, 6, tzinfo=UTC))
    assert [s["created"] for s in got] == ["2026-10-17 02:25", "2026-10-20 10:00"]


def test_paywall_words_filter_ignores_remember_and_unsubscribe():
    assert az.PAYWALL_WORDS.search("Paywalling mid article makes me not want to open your emails")
    assert az.PAYWALL_WORDS.search("only for paid members?")
    assert not az.PAYWALL_WORDS.search("I don't remember signing up for this newsletter")
    assert not az.PAYWALL_WORDS.search("Unsubscribe")


# ---------------------------------------------------------------------------------------------
# 2. realistic synthetic worlds through the real pipeline
# ---------------------------------------------------------------------------------------------

def fmt(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S")


def make_world(*, email_payers: int, web_payers: int, unsub_multiplier: float, seed: int) -> dict:
    """A fake pull with the real shapes: 4 sends, 4 baseline editions, pitch-page runs, Stripe, ratings.

    100 distinct email visitors (10 of them members), 20 web visitors, 150 scanner-only clickers,
    8 team test runs before the send. `email_payers` / `web_payers` readers complete checkout and one
    more of each channel abandons it. The engaged send's unsubscribes are the baseline rate per open
    (1.2%) times `unsub_multiplier`. Baseline Supporter sign-ups: 5 between Jul 1 and Oct 12.
    """
    rng = random.Random(seed)
    posts, visitors = {}, [h(1000 + i) for i in range(100)]
    scanners = [h(5000 + i) for i in range(150)]
    sp_ids = list(az.SP_POSTS)
    rows = [click(PAYWALL_URL.format(x), 1) for x in visitors] + [click(PAYWALL_URL.format(x), 0) for x in scanners]
    rng.shuffle(rows)
    opens = {sp_ids[0]: 12000, sp_ids[1]: 50000, sp_ids[2]: 9000, sp_ids[3]: 6000}
    for i, pid in enumerate(sp_ids):
        unsubs = round(opens[pid] * 0.012 * (unsub_multiplier if pid == az.ENGAGED_SEND else 1))
        posts[pid] = post(opens[pid] * 5, opens[pid] * 5 - 500, opens[pid], unsubs, 4, clicks=rows[i::4])
    for (name, ids), rate in zip(az.BASELINE_EDITIONS.items(), [0.011, 0.012, 0.0125, 0.013]):
        for pid in ids:
            posts[pid] = post(330000 // len(ids), 328000 // len(ids), 90000 // len(ids), round(90000 * rate / len(ids)), 9)

    runs, sessions, subs = [], [], []
    for i in range(8):                                                         # team tests before the send
        runs.append({"t": fmt(SEND - timedelta(days=2, minutes=i)), "src": "agent-test", "h": h(1) if i < 4 else "",
                     "isMember": "0.0", "emailMember": ""})
    sessions.append({"id": "cs_test", "created": fmt(SEND - timedelta(days=2))[:16], "status": "complete",
                     "ref": "x", "sub": "sub_test", "email_md5": h(1)})
    subs.append(sub(fmt(SEND - timedelta(days=2))[:16], status="canceled", canceled_at=fmt(SEND - timedelta(days=2))[:16],
                    email_md5=h(1), id_="sub_test"))

    def checkout(when: datetime, paid: bool, email_md5, n: int) -> None:
        sid = f"sub_{n}" if paid else None
        sessions.append({"id": f"cs_{n}", "created": fmt(when + timedelta(minutes=1))[:16],
                         "status": "complete" if paid else "expired", "ref": "ga-1", "sub": sid,
                         "email_md5": email_md5 if paid else None})
        if paid:
            subs.append(sub(fmt(when + timedelta(minutes=1))[:16], email_md5=email_md5, id_=sid))

    for i, x in enumerate(visitors):
        when = SEND + timedelta(hours=1 + i * 4)                               # spread over ~17 days
        runs.append({"t": fmt(when), "src": "supplement-paradox", "h": x,
                     "isMember": "1.0" if i < 10 else "0.0", "emailMember": "0.0" if 10 <= i < 20 else ""})
        if i % 9 == 0:                                                         # some readers reload
            runs.append({"t": fmt(when + timedelta(seconds=3)), "src": "supplement-paradox", "h": x,
                         "isMember": "1.0" if i < 10 else "0.0", "emailMember": ""})
        if 20 <= i < 20 + email_payers:
            checkout(when, True, x, i)
        elif i == 60:
            checkout(when, False, None, i)
    for j in range(20):
        when = SEND + timedelta(hours=2 + j * 20, minutes=30)
        runs.append({"t": fmt(when), "src": "supplement-paradox-web", "h": "", "isMember": "0.0",
                     "emailMember": "1.0" if j < 2 else ""})
        if 5 <= j < 5 + web_payers:
            checkout(when, True, h(9000 + j), 500 + j)                         # Stripe email unknown to beehiiv
        elif j == 15:
            checkout(when, False, None, 500 + j)

    for k, day in enumerate(["2026-07-19", "2026-08-02", "2026-08-08", "2026-09-01", "2026-09-21"]):
        subs.append(sub(f"{day} 10:00", email_md5=h(7000 + k), id_=f"sub_base{k}"))
    subs.append(sub("2026-10-18 08:29", lookup="navigator", email_md5=h(7100), id_="sub_nav"))   # unrelated tier

    ratings = []
    for slug, dist in {"the-supplement-paradox": [30, 10, 4, 3, 3], "another-article": [60, 25, 5, 5, 5],
                       "third-article": [20, 12, 2, 3, 3]}.items():
        for rating, n in zip(az.RATING_ORDER, dist):
            ratings += [{"t": "2026-10-17 10:00:00", "article": f"https://www.clearerthinking.org/post/{slug}?u=1",
                         "final_rating": rating, "feedback": ""}] * n
    return {"posts": posts, "pitch_runs": runs,
            "full_version_runs": [{"t": fmt(SEND + timedelta(hours=3)), "src": "stripe-link", "has_key": True}],
            "sessions": sessions, "subscriptions": subs, "ratings": ratings,
            "ga4": {"web_post_views": 250, "web_post_users": 200, "pitch_page_users": 118}}


NOW = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)


def test_null_world_finds_no_sales_and_no_unsubscribe_change():
    d = az.build_datapoints(make_world(email_payers=0, web_payers=0, unsub_multiplier=1.0, seed=1), NOW)
    f = d["funnel"]
    assert f["email_visitors"] == 100 and f["email_members_by_hash"] == 10 and f["email_non_member_visitors"] == 90
    assert f["web_runs"] == 20 and f["web_typed_member"] == 2
    assert f["paywall_clickers_all"] == 250 and f["paywall_clickers_verified"] == 100
    assert f["pre_send_runs_excluded"] == 8
    assert f["checkouts_paid"] == 0 and f["checkouts_abandoned"] == 2 and f["checkouts_opened"] == 2
    assert d["revenue"]["new_mrr_usd"] == 0 and d["rates"]["email_paid_per_non_member_visitor"] == 0
    assert d["supporter_baseline"]["test_signups"] == 0 and d["supporter_baseline"]["baseline_signups"] == 5
    assert d["supporter_baseline"]["p_one_sided"] == pytest.approx(1.0)            # zero sign-ups can never look faster
    assert d["engaged_send_vs_baseline"]["unsub_per_open"]["verdict"] == "within"  # 1.2% inside the 1.1-1.3% baseline
    assert d["cross_checks"]["verified_clickers_with_gt_run"] == 100


def test_positive_world_recovers_every_planted_sale_and_the_unsubscribe_jump():
    d = az.build_datapoints(make_world(email_payers=6, web_payers=2, unsub_multiplier=3.0, seed=2), NOW)
    f = d["funnel"]
    assert f["checkouts_paid"] == 8 and f["paid_email"] == 6 and f["paid_web"] == 2
    assert f["checkouts_abandoned"] == 2 and f["paid_still_active"] == 8
    assert d["revenue"]["new_mrr_usd"] == 72                                       # 8 x $9
    assert d["rates"]["email_paid_per_non_member_visitor"] == pytest.approx(6 / 90)
    assert d["cross_checks"]["paid_hashes_among_gt_visitors"] == 6                 # web payers have no beehiiv hash
    assert f["checkout_refs_overwritten"] == 10                                    # every synthetic checkout carries ref "ga-1"
    assert f["existing_members_reached_max"] == 12                                 # 10 by hash + 2 typed on the web
    sb = d["supporter_baseline"]
    assert sb["test_signups"] == 8 and sb["baseline_signups"] == 5                 # test payment and navigator excluded
    assert sb["ratio"] > 5 and sb["p_one_sided"] < 0.01
    u = d["engaged_send_vs_baseline"]["unsub_per_open"]
    assert u["value"] == pytest.approx(0.036) and u["verdict"] == "above"          # 3.6% vs a 1.1-1.3% baseline
    assert d["ratings"]["supplement_paradox"]["n"] == 50 and d["ratings"]["low_share"] == pytest.approx(0.12)


def test_worlds_differ_only_where_planted():
    a = az.build_datapoints(make_world(email_payers=0, web_payers=0, unsub_multiplier=1.0, seed=3), NOW)
    b = az.build_datapoints(make_world(email_payers=6, web_payers=2, unsub_multiplier=3.0, seed=3), NOW)
    for key in ("email_visitors", "email_members_by_hash", "web_runs", "paywall_clickers_verified", "checkouts_abandoned"):
        assert a["funnel"][key] == b["funnel"][key]


def test_weekly_bins_by_hand():
    anchor = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    events = [anchor - timedelta(days=8),            # bin -2 (days -14 to -7)
              anchor - timedelta(hours=1),           # bin -1
              anchor, anchor + timedelta(days=6, hours=23),   # bin 0 (its first instant and its last hour)
              anchor + timedelta(days=7)]            # bin 1
    bins = az.weekly_bins(events, anchor, first=anchor - timedelta(days=14), now=anchor + timedelta(days=15))
    assert [(b["index"], b["count"], b["after"]) for b in bins] == [
        (-2, 1, False), (-1, 1, False), (0, 2, True), (1, 1, True), (2, 0, True)]
    assert bins[0]["start"] == "2026-10-02" and bins[2]["start"] == "2026-10-16"


def test_weekly_bins_drops_a_sliver_at_the_end_unless_it_has_events():
    anchor = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    now = anchor + timedelta(days=21, hours=5)       # 5 hours into bin 3
    quiet = az.weekly_bins([anchor], anchor, anchor, now)
    assert [b["index"] for b in quiet] == [0, 1, 2]
    busy = az.weekly_bins([anchor, now - timedelta(hours=1)], anchor, anchor, now)
    assert [b["index"] for b in busy] == [0, 1, 2, 3] and busy[-1]["count"] == 1
