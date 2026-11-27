"""Tests for reports/net_growth_diagnosis_2026-11-27_src/analysis.py.

Three layers, as the project's data-science rules ask:
  1. each measurement on tiny data sets whose answer is worked out by hand (two per measurement);
  2. realistic synthetic "worlds" shaped like the real records: a null one built so that the effect is
     absent (a flat exit hazard; sends that all lose readers at one rate) and a positive one with a known
     effect planted (new subscribers leave five times faster; whole-list sends lose twice as many);
  3. the independent recount lives in cross_check.py beside the analysis (it needs the real data).
"""
import importlib.util
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "reports" / "net_growth_diagnosis_2026-11-27_src"
spec = importlib.util.spec_from_file_location("net_growth_analysis", SRC / "analysis.py")
az = importlib.util.module_from_spec(spec)
spec.loader.exec_module(az)

UTC = timezone.utc
DAY = 86400


def ts(y, m, d, hour=12):
    return int(datetime(y, m, d, hour, tzinfo=UTC).timestamp())


_ids = iter(range(10**9))


def rec(status="active", created=ts(2026, 6, 15), group=az.ORGANIC, tool=None, received=10, opened=5, id=None):
    return {"id": id or f"sub_{next(_ids)}", "status": status, "created": created, "group": group,
            "tool": tool, "received": received, "opened": opened}


def post(recipients, unsubscribes, unique_opens=0, when=ts(2026, 9, 10), spam=0, subject="An article", title=""):
    return {"publish_ts": when, "recipients": recipients, "unsubscribes": unsubscribes,
            "unique_opens": unique_opens, "spam_reports": spam, "subject": subject, "title": title}


# ---------- 1. by hand ----------

class TestCompact:
    def raw(self, **over):
        row = {"id": "sub_1", "status": "active", "created": ts(2026, 6, 15), "utm_channel": "api",
               "utm_medium": "", "utm_source": "direct", "st": [12, 11, 4, 1],
               "cf": {"Tools Tried (Pipe-Separated)": "How Rational Are You, Really?|Who Attracts You"}}
        row.update(over)
        return row

    def test_organic_tool_signup_keeps_first_tool_and_stats(self):
        c = az.compact(self.raw())
        assert (c["group"], c["tool"], c["received"], c["opened"]) == (az.ORGANIC, "how rational are you, really?", 11, 4)

    def test_study_first_is_study_and_missing_stats_are_zero(self):
        c = az.compact(self.raw(st=None, cf={"Tools Tried (Pipe-Separated)": "|Who Attracts You"}))
        assert (c["group"], c["received"], c["opened"]) == (az.STUDY, 0, 0)

    def test_ad_medium_on_the_first_visit_is_ads(self):
        c = az.compact(self.raw(cf={"Tools Tried (Pipe-Separated)": "The Ultimate Personality Test",
                                    "UTM Media (Comma-Separated)": "cpc"}))
        assert c["group"] == az.ADS

    def test_tool_is_unknown_before_the_tools_wrote_their_list(self):
        c = az.compact(self.raw(created=ts(2026, 2, 10)))
        assert c["tool"] is None and c["group"] == az.ORGANIC


class TestReading:
    @pytest.mark.parametrize("received,opened,expected", [
        (3, 3, "too_new"), (4, 0, "never_opened"), (10, 2, "occasional"), (10, 3, "reader"), (40, 40, "reader")])
    def test_states(self, received, opened, expected):
        assert az.reading(rec(received=received, opened=opened)) == expected


class TestListMovement:
    def test_two_months_by_hand(self):
        out = az.list_movement({"2026-05": [10, 20, 30], "2026-06": [5, 5]}, {"2026-05": [40, 10, 20], "2026-06": [1, 2]})
        assert out == [{"month": "2026-05", "days": 3, "subscribed": 60, "unsubscribed": 70, "net": -10},
                       {"month": "2026-06", "days": 2, "subscribed": 10, "unsubscribed": 3, "net": 7}]

    def test_joined_by_month_skips_invalid_records(self):
        recs = [rec(created=ts(2026, 5, 3)), rec(created=ts(2026, 5, 9), group=az.STUDY),
                rec(created=ts(2026, 5, 9), status="invalid"), rec(created=ts(2026, 6, 1), status="inactive")]
        assert az.joined_by_month(recs) == {"2026-05": {az.ORGANIC: 1, az.STUDY: 1}, "2026-06": {az.ORGANIC: 1}}


class TestSendLoad:
    def test_one_month_by_hand(self):
        # 300,000 + 100,000 emails, 900 + 300 unsubscribes -> 3.0 per 1,000; list lost 1,500 -> 300 outside sends.
        posts = [post(300_000, 900), post(100_000, 300), post(50, 0)]
        (m,) = az.monthly_send_load(posts, {"2026-09": 1500})
        assert (m["sends"], m["emails"], m["send_unsubscribes"]) == (2, 400_050, 1200)
        assert m["per_1000_emails"] == pytest.approx(3.0, abs=0.01)
        assert (m["all_unsubscribes"], m["outside_sends"]) == (1500, 300)

    def test_month_without_a_list_total_reports_none(self):
        (m,) = az.monthly_send_load([post(200_000, 500, when=ts(2025, 9, 1))], {})
        assert m["per_1000_emails"] == 2.5 and m["all_unsubscribes"] is None and m["outside_sends"] is None

    def test_send_kind_thresholds(self):
        assert az.send_kind(post(19_999, 0), 600_000) == "small"
        assert az.send_kind(post(509_999, 0), 600_000) == "segment"
        assert az.send_kind(post(510_000, 0), 600_000) == "whole_list"

    def test_send_rates_pool_instead_of_averaging(self):
        # whole list: (2,000 + 1,000) / (600k + 400k) = 3.0 per 1,000 (the mean of the two rates would be 2.92).
        posts = [post(600_000, 2000, 100_000), post(400_000, 1000, 50_000), post(100_000, 100, 40_000), post(10, 5)]
        rows = {r["key"]: r for r in az.send_rates(posts, lambda p: "big" if p["recipients"] >= 400_000 else "seg")}
        assert rows["big"]["per_1000_recipients"] == 3.0 and rows["big"]["per_1000_opens"] == 20.0
        assert rows["big"]["unsubscribes_per_send"] == 1500 and rows["big"]["sends"] == 2
        assert rows["seg"]["per_1000_recipients"] == 1.0 and rows["seg"]["open_rate"] == 0.4

    def test_open_band_edges(self):
        assert [az.open_band(x) for x in (0.0, 0.0999, 0.10, 0.2999, 0.30, 0.9)] == \
            ["under 10%", "under 10%", "10-20%", "20-30%", "30%+", "30%+"]


class TestWhoLeaves:
    def test_retention_by_hand(self):
        recs = [rec(), rec(), rec(status="inactive"), rec(status="invalid"), rec(group=az.STUDY, status="inactive")]
        rows = {r["key"]: r for r in az.retention(recs, lambda r: r["group"])}
        assert rows[az.ORGANIC] == {"key": az.ORGANIC, "joined": 3, "active": 2, "left": 1, "left_share": 0.3333}
        assert rows[az.STUDY]["left_share"] == 1.0

    def test_exits_by_emails_received_by_hand(self):
        recs = [rec(status="inactive", received=0, opened=0), rec(status="inactive", received=1, opened=1),
                rec(status="inactive", received=3, opened=0), rec(status="inactive", received=30, opened=9),
                rec(received=50), rec(status="invalid", received=1)]
        out = az.exits_by_emails_received(recs)[az.ORGANIC]
        assert (out["joined"], out["left"], out["left_never_opened"]) == (5, 4, 2)
        assert {b["emails"]: b["left"] for b in out["bins"]} == \
            {"0": 1, "1": 1, "2-3": 1, "4-6": 0, "7-12": 0, "13-24": 0, "25+": 1}

    def test_exits_by_emails_received_empty_group(self):
        out = az.exits_by_emails_received([rec()])
        assert out[az.STUDY] == {"joined": 0, "left": 0, "left_never_opened": 0,
                                 "bins": [{"emails": label, "left": 0} for _, _, label in az.RECEIVED_BINS]}

    def test_window_exits_by_hand(self):
        asof = ts(2026, 11, 18)
        old = {"a": "active", "b": "active", "c": "active", "d": "inactive", "e": "active", "gone": "active"}
        recs = [rec(id="a", created=asof - 5 * DAY),                      # stayed, under 2 weeks
                rec(id="b", created=asof - 5 * DAY, status="inactive"),   # left, under 2 weeks
                rec(id="c", created=asof - 300 * DAY, status="inactive"),  # left, 8+ months
                rec(id="d", created=asof - 300 * DAY, status="inactive"),  # had already left: not at risk
                rec(id="e", created=asof - 300 * DAY, status="invalid"),   # bounced: at risk, not an exit
                rec(id="new", created=asof + DAY)]                        # joined after the old snapshot
        out = az.window_exits(old, recs, asof, window_days=10)
        cells = {(c["group"], c["tenure"]): c for c in out["cells"]}
        # 1 of 2 left in 10 days -> 50 per 100, x3 for 30 days.
        assert cells[(az.ORGANIC, "under 2 weeks")] == {"group": az.ORGANIC, "tenure": "under 2 weeks",
                                                         "at_risk": 2, "exits": 1, "rate_30d": 150.0}
        assert cells[(az.ORGANIC, "8+ months")]["at_risk"] == 2 and cells[(az.ORGANIC, "8+ months")]["exits"] == 1
        assert (out["at_risk"], out["exits"], out["turned_invalid"], out["missing_from_new_walk"]) == (4, 2, 1, 1)

    def test_pooled_rate_by_hand(self):
        cells = [{"group": "a", "tenure": "x", "at_risk": 100, "exits": 1},
                 {"group": "a", "tenure": "y", "at_risk": 300, "exits": 7},
                 {"group": "b", "tenure": "x", "at_risk": 50, "exits": 5}]
        assert az.pooled_rate(cells, 15, group="a") == {"at_risk": 400, "exits": 8, "rate_30d": 4.0}
        assert az.pooled_rate(cells, 15, tenure="x") == {"at_risk": 150, "exits": 6, "rate_30d": 8.0}
        assert az.pooled_rate(cells, 15, group="zzz")["rate_30d"] is None


class TestReaderYield:
    def test_by_hand(self):
        asof = ts(2026, 11, 27)
        old_enough = asof - 100 * DAY
        recs = [rec(created=old_enough, received=20, opened=10),           # reader
                rec(created=old_enough, received=20, opened=1),            # occasional
                rec(created=old_enough, received=20, opened=0),            # never opened
                rec(created=old_enough, status="inactive"),               # left
                rec(created=asof - 10 * DAY, received=20, opened=20),      # too recent to count
                rec(created=old_enough, status="invalid")]                # not a subscriber
        (row,) = az.reader_yield(recs, lambda r: r["group"], asof)
        assert (row["joined"], row["active"]) == (4, 3)
        assert row["per_100"] == {"active": 75.0, "reader": 25.0, "occasional": 25.0, "never_opened": 25.0, "too_new": 0.0}

    def test_sorted_by_size_and_keyed(self):
        asof = ts(2026, 11, 27)
        recs = [rec(created=asof - 200 * DAY, tool="a")] + [rec(created=asof - 200 * DAY, tool="b") for _ in range(3)]
        assert [r["key"] for r in az.reader_yield(recs, lambda r: r["tool"], asof)] == ["b", "a"]


class TestLeakyListArithmetic:
    def test_breakeven_and_equilibrium_by_hand(self):
        assert az.breakeven_inflow(680_000, 0.015) == pytest.approx(10_200)
        assert az.equilibrium_list(6_000, 0.015) == pytest.approx(400_000)

    def test_projection_by_hand(self):
        # 680,000 x 0.985 + 6,000 = 675,800; then 675,800 x 0.985 + 6,000 = 671,663.
        assert az.project(680_000, 6_000, 0.015, 2) == [675_800, 671_663]

    def test_projection_is_flat_at_the_equilibrium(self):
        assert az.project(400_000, 6_000, 0.015, 3) == [400_000, 400_000, 400_000]


class TestInflow:
    GA4 = {"2026-05": [
        {"page": "/personality-test.html", "event": "Accepted Privacy Policy", "paid": False, "count": 100},
        {"page": "/personality-test.html?x=1", "event": "Reached Email Ask", "paid": False, "count": 60},
        {"page": "/personality-test", "event": "Submitted Email", "paid": False, "count": 54},
        {"page": "/other/", "event": "Accepted Privacy Policy", "paid": False, "count": 100},
        {"page": "/other/", "event": "Reached Email Ask", "paid": False, "count": 40},
        {"page": "/other/", "event": "Submitted Email", "paid": True, "count": 999},
        {"page": "/other/", "event": "Viewed Privacy Policy", "paid": False, "count": 500}]}

    def test_funnel_all_pages_not_paid(self):
        (m,) = az.funnel_by_month(self.GA4)
        assert (m["landed"], m["started"], m["reached_ask"], m["submitted"]) == (500, 200, 100, 54)
        assert (m["start_to_ask"], m["ask_to_submit"]) == (0.5, 0.54)

    def test_funnel_one_page_joins_its_spellings(self):
        (m,) = az.funnel_by_month(self.GA4, page="/personality-test")
        assert (m["started"], m["reached_ask"], m["submitted"], m["ask_to_submit"]) == (100, 60, 54, 0.9)

    def test_funnel_paid_only(self):
        (m,) = az.funnel_by_month(self.GA4, paid=True)
        assert m["submitted"] == 999 and m["started"] == 0 and m["start_to_ask"] is None

    def test_search_clicks(self):
        gsc = {"2026-08": {"tools_clicks": 1000, "tool_pages": [
            {"page": "https://programs.clearerthinking.org/who_attracts_you_study.html", "clicks": 700},
            {"page": "https://programs.clearerthinking.org/personality-test.html", "clicks": 200},
            {"page": "https://programs.clearerthinking.org/personality-test", "clicks": 10}]}}
        assert az.search_clicks_by_month(gsc) == {"2026-08": 1000}
        assert az.search_clicks_by_month(gsc, exclude=("/who_attracts_you_study",)) == {"2026-08": 300}
        assert az.search_clicks_by_month(gsc, page="/personality-test") == {"2026-08": 210}


# ---------- 2. realistic synthetic worlds ----------

def simulate_list(hazard, n=60_000, seed=7, asof=ts(2026, 11, 18), window=9):
    """Subscribers who joined over the 300 days before `asof`; each day alive they leave with probability
    `hazard(days_since_joining)`. Returns the old snapshot's statuses and the records nine days later."""
    rng = random.Random(seed)
    old, recs = {}, []
    for i in range(n):
        age = rng.randrange(1, 300)
        created = asof - age * DAY
        left_before = any(rng.random() < hazard(d) for d in range(age))
        left_in_window = (not left_before) and any(rng.random() < hazard(age + d) for d in range(window))
        sid = f"s{i}"
        old[sid] = "inactive" if left_before else "active"
        recs.append(rec(id=sid, created=created, status="inactive" if (left_before or left_in_window) else "active"))
    return old, recs, asof, window


class TestWindowWorlds:
    def test_null_world_flat_hazard_shows_no_tenure_effect(self):
        old, recs, asof, window = simulate_list(lambda d: 0.0006)  # about 1.8% a month at every age
        out = az.window_exits(old, recs, asof, window)
        rates = {label: az.pooled_rate(out["cells"], window, tenure=label)["rate_30d"] for _, _, label in az.TENURE_BANDS}
        overall = 100 * out["exits"] / out["at_risk"] * 30 / window
        assert overall == pytest.approx(1.8, abs=0.25)
        for label, rate in rates.items():
            assert rate == pytest.approx(1.8, abs=0.9), label  # small bands are noisy, none is several times higher

    def test_positive_world_new_subscribers_leave_five_times_faster(self):
        old, recs, asof, window = simulate_list(lambda d: 0.003 if d < 30 else 0.0006)
        out = az.window_exits(old, recs, asof, window)
        young = az.pooled_rate(out["cells"], window, tenure="under 2 weeks")["rate_30d"]
        settled = az.pooled_rate(out["cells"], window, tenure="4-8 months")["rate_30d"]
        assert young == pytest.approx(9.0, abs=1.8) and settled == pytest.approx(1.8, abs=0.4)
        assert young / settled > 3.5


def simulate_sends(whole_list_rate, segment_rate, seed=3):
    rng = random.Random(seed)
    posts = []
    for week in range(16):
        when = ts(2026, 8, 1) + week * 7 * DAY
        for size, rate in ((620_000, whole_list_rate), (155_000, segment_rate), (320_000, segment_rate)):
            n = size + rng.randrange(-5000, 5000)
            unsub = sum(1 for _ in range(n // 100) if rng.random() < rate * 100)  # coarse binomial
            posts.append(post(n, unsub, unique_opens=int(n * 0.25), when=when))
        posts.append(post(6, 2, when=when))  # a test send that must not count
    return posts


class TestSendWorlds:
    def kind(self, p):
        return az.send_kind(p, 650_000)

    def test_null_world_same_rate_everywhere(self):
        rows = {r["key"]: r for r in az.send_rates(simulate_sends(0.003, 0.003), self.kind)}
        assert set(rows) == {"whole_list", "segment"}
        assert rows["whole_list"]["per_1000_recipients"] == pytest.approx(3.0, abs=0.25)
        assert rows["segment"]["per_1000_recipients"] == pytest.approx(3.0, abs=0.25)

    def test_positive_world_whole_list_sends_lose_twice_as_many(self):
        rows = {r["key"]: r for r in az.send_rates(simulate_sends(0.006, 0.003), self.kind)}
        assert rows["whole_list"]["per_1000_recipients"] / rows["segment"]["per_1000_recipients"] == pytest.approx(2.0, abs=0.25)
        assert rows["whole_list"]["sends"] == 16 and rows["segment"]["sends"] == 32

    def test_monthly_load_recovers_the_planted_rate_and_the_outside_share(self):
        posts = simulate_sends(0.003, 0.003)
        from_sends = {}
        for p in posts:
            from_sends[az.post_month(p)] = from_sends.get(az.post_month(p), 0) + p["unsubscribes"]
        totals = {m: v + 2000 for m, v in from_sends.items()}  # 2,000 exits a month planted outside any send
        for m in az.monthly_send_load(posts, totals):
            assert m["outside_sends"] == 2000
            assert m["per_1000_emails"] == pytest.approx(3.0, abs=0.35)
