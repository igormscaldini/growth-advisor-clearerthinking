"""Tests for reports/subscribers_by_month_2026-11-18_src/analysis.py.

Three layers, as the project's data-science rules ask:
  1. the reading rules one by one, then small data sets whose monthly table is worked out by hand;
  2. two realistic synthetic "worlds" shaped like the real beehiiv records: a null one (nobody came from
     ads or the study, so nothing may be removed) and a positive one (known numbers planted per month,
     hidden among look-alikes that must NOT be removed, plus ad sign-ups from before the tags existed
     that only the GA4-based estimate can find);
  3. the independent recount lives in cross_check.py beside the analysis (it needs the real data).
"""
import importlib.util
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "reports" / "subscribers_by_month_2026-11-18_src"
spec = importlib.util.spec_from_file_location("subs_by_month_analysis", SRC / "analysis.py")
az = importlib.util.module_from_spec(spec)
spec.loader.exec_module(az)

UTC = timezone.utc


def ts(y, m, d, hour=12, minute=0):
    return int(datetime(y, m, d, hour, minute, tzinfo=UTC).timestamp())


LATE = ts(2026, 6, 15)   # well after every cut-off: both lists describe the sign-up visit
EARLY = ts(2026, 2, 10)  # before the tools wrote either list

_ids = iter(range(10**9))


def sub(created=LATE, tools=None, media=None, channel="api", status="active", medium="", source="direct", **flags):
    """A slim subscription row as fetch_data.py writes it."""
    cf = dict(flags)
    if tools is not None:
        cf[az.TOOLS_FIELD] = tools
    if media is not None:
        cf[az.MEDIA_FIELD] = media
    return {"id": f"sub_{next(_ids)}", "created": created, "status": status, "utm_channel": channel,
            "utm_medium": medium, "utm_source": source, "utm_campaign": "", "cf": cf}


DATING = {az.DATING_FIELD: True}
MLA = {az.MLA_FIELD: "ace___worlds_biggest_problems_quiz"}
OLD_TOOL = {az.OLD_TOOLS_FIELD: ["Unique Traits Test"]}


# ---------- 1a. reading rules ----------

def test_tokens_skip_blanks_and_keep_order():
    assert az.tokens("A| B |(none)||C", "|") == ["a", "b", "c"]
    assert az.tokens(None, "|") == []
    assert az.tokens(True, "|") == []


def test_media_keeps_none_visits_in_position():
    assert az.media(sub(media="(none),cpc")) == ["", "cpc"]
    assert az.media(sub(media="cpc,(none)")) == ["cpc", ""]


def test_leading_separator_bug_is_skipped():
    assert az.media(sub(media=",cpc")) == ["cpc"]
    assert az.media(sub(media=",(none)")) == [""]
    assert az.tools_tried(sub(tools="|Who Attracts You|Unique Traits Test")) == ["who attracts you", "unique traits test"]


@pytest.mark.parametrize("row, first, anywhere", [
    (sub(media="cpc"), True, True),
    (sub(media="cpc,(none)"), True, True),
    (sub(media=",cpc"), True, True),
    (sub(media="paid_social"), True, True),
    (sub(media="(none),cpc"), False, True),             # a reader who clicked an ad LATER
    (sub(media="(none)", medium="cpc"), True, True),    # beehiiv's own field, set at creation
    (sub(media="(none),email"), False, False),
    (sub(media="CPC"), True, True),
    (sub(), False, False),
    # Created before the tools wrote UTM media: the list's first entry is a later visit, not the sign-up.
    (sub(EARLY, media="cpc"), False, True),
    (sub(EARLY, media="(none)", medium="cpc"), True, True),
])
def test_ads_is_the_sign_up_visit(row, first, anywhere):
    assert az.from_ads(row) is first
    assert az.touched_ads(row) is anywhere


def test_media_cut_off_is_to_the_hour():
    assert az.from_ads(sub(ts(2026, 3, 27, 14, 59), media="cpc")) is False
    assert az.from_ads(sub(ts(2026, 3, 27, 15, 0), media="cpc")) is True


@pytest.mark.parametrize("row, first, anywhere", [
    (sub(tools="Who Attracts You"), True, True),
    (sub(tools="|Who Attracts You"), True, True),
    (sub(tools="Who Attracts You|Unique Traits Test"), True, True),
    (sub(tools="The Ultimate Personality Test|Who Attracts You"), False, True),  # came for the UPT
    (sub(**DATING), True, True),                                                  # waitlist, no tool
    (sub(tools="Intrinsic Values Test", **DATING), False, True),
    (sub(tools="Intrinsic Values Test"), False, False),
    (sub(), False, False),
    # Created before the tools list existed: a January reader who took the study in the autumn.
    (sub(EARLY, tools="Who Attracts You", channel="import"), False, True),
    (sub(EARLY, **DATING), False, True),
])
def test_study_is_the_first_tool(row, first, anywhere):
    assert az.from_study(row) is first
    assert az.touched_study(row) is anywhere


def test_tools_cut_off_is_to_the_hour():
    assert az.from_study(sub(ts(2026, 3, 31, 9, 59), tools="Who Attracts You")) is False
    assert az.from_study(sub(ts(2026, 3, 31, 10, 0), tools="Who Attracts You")) is True


@pytest.mark.parametrize("row, expected", [
    (sub(tools="Who Attracts You", media="cpc"), az.STUDY),   # both: study wins, overlap counted apart
    (sub(tools="How Rational Are You, Really?", media="cpc"), az.ADS),
    (sub(tools="How Rational Are You, Really?", media="(none)"), az.TOOLS),
    (sub(**MLA), az.PARTNER_ADS),
    (sub(EARLY, **MLA), az.PARTNER_ADS),
    (sub(tools="Intrinsic Values Test", media="(none)", **MLA), az.TOOLS),   # a tool reader who also met a partner page
    (sub(EARLY, **MLA, **OLD_TOOL), az.TOOLS),
    (sub(channel="import", Leaf=True), az.LEAF),
    (sub(channel="import"), az.UPLOADS),
    (sub(EARLY, channel="import"), az.TOOLS),                 # twice-weekly uploads of tool sign-ups, pre-API
    (sub(ts(2026, 3, 9, 18, 51), channel="import"), az.TOOLS),
    (sub(ts(2026, 3, 10, 0, 1), channel="import"), az.UPLOADS),
    (sub(EARLY, channel="import", **{"Form New Habits Workshop": True}), az.FORMS),
    (sub(ts(2026, 1, 1, 1, 15), channel="import"), az.BACKLOG),
    (sub(ts(2026, 1, 1, 1, 15), channel="embed"), az.FORMS),  # a real sign-up in the first hours of the year
    (sub(ts(2026, 1, 5, 18, 33), channel="import"), az.TOOLS),
    (sub(channel="import", tools="Who Attracts You"), az.STUDY),
    (sub(channel="import", **DATING), az.STUDY),
    (sub(channel="import", tools="Intrinsic Values Test"), az.TOOLS),
    (sub(channel="recommendation", source="www.example.com"), az.RECOMMENDATIONS),
    (sub(source="podcast"), az.PODCAST),
    (sub(channel="embed"), az.FORMS),
    (sub(channel="api"), az.FORMS),
    (sub(EARLY, **OLD_TOOL), az.TOOLS),
])
def test_bucket(row, expected):
    assert az.bucket(row) == expected


def test_pending_and_invalid_are_not_subscribers():
    """beehiiv counts neither an address that failed validation nor one that never confirmed."""
    rows = [sub(tools="Intrinsic Values Test"), sub(tools="Intrinsic Values Test", status="pending"),
            sub(tools="Intrinsic Values Test", status="invalid"), sub(tools="Intrinsic Values Test", status="inactive")]
    (m,) = az.summarize(rows)["months"]
    assert (m["records"], m["invalid"], m["pending"], m["total"], m["kept"], m["kept_active"]) == (4, 1, 1, 2, 2, 1)


def test_left_since_counts_unsubscribed_by_where_they_came_from():
    """Six people joined in June and have since unsubscribed: 2 from the study, 1 tagged ad, 1 partner ad,
    2 kept (a tool sign-up and a Leaf student). Three who are still active must not be counted."""
    gone = dict(status="inactive")
    rows = [sub(tools="Who Attracts You", **gone), sub(**DATING, **gone), sub(tools="X", media="cpc", **gone),
            sub(**MLA, **gone), sub(tools="X", **gone), sub(channel="import", Leaf=True, **gone),
            sub(tools="Who Attracts You"), sub(tools="X", media="cpc"), sub(tools="X")]
    (m,) = az.summarize(rows)["months"]
    assert m["left_since"] == {"study": 2, "ads": 2, "kept": 2, "backlog": 0}


def test_every_bucket_is_either_kept_or_removed():
    assert set(az.EXCLUDED) | set(az.INCLUDED) == set(az.LABELS)
    assert not set(az.EXCLUDED) & set(az.INCLUDED)


def test_month_is_utc():
    assert az.month_of({"created": ts(2026, 3, 31, 23, 30)}) == "2026-03"
    assert az.month_of({"created": ts(2026, 4, 1, 0, 30)}) == "2026-04"


# ---------- 1b. small data sets, answers worked out by hand ----------

def test_hand_worked_set_a():
    """June: 6 records, one of them an invalid address that beehiiv never counted, so 5 subscribers:
    2 organic tool sign-ups (one since unsubscribed), 1 ad click, 1 study, 1 Leaf upload.
    Kept = 5 - 1 ad - 1 study = 3, of which still active = 2.
    July: 2 records, both study -> kept 0."""
    rows = [
        sub(ts(2026, 6, 3), tools="Intrinsic Values Test", media="(none)"),
        sub(ts(2026, 6, 9), tools="Intrinsic Values Test", media="(none)", status="inactive"),
        sub(ts(2026, 6, 9), tools="How Rational Are You, Really?", media="cpc"),
        sub(ts(2026, 6, 20), tools="Who Attracts You", media="(none)"),
        sub(ts(2026, 6, 30), channel="import", Leaf=True),
        sub(ts(2026, 6, 30), tools="Intrinsic Values Test", media="(none)", status="invalid"),
        sub(ts(2026, 7, 1), tools="Who Attracts You", media="(none)"),
        sub(ts(2026, 7, 28), channel="import", tools="Who Attracts You"),
    ]
    jun, jul = az.summarize(rows)["months"]
    assert (jun["month"], jun["records"], jun["invalid"], jun["total"]) == ("2026-06", 6, 1, 5)
    assert (jun["kept"], jun["kept_active"], jun["ads_all"]) == (3, 2, 1)
    assert jun["buckets"][az.TOOLS] == 2 and jun["buckets"][az.LEAF] == 1
    assert jun["buckets"][az.ADS] == 1 and jun["buckets"][az.STUDY] == 1
    assert jun["estimated"] is False and jun["kept_low"] == jun["kept_high"] == 3
    assert (jul["month"], jul["total"], jul["kept"], jul["kept_active"]) == ("2026-07", 2, 0, 0)


def test_hand_worked_set_b_overlap_and_wide_reading():
    """One month, 7 records:
      1 study + ad on the same first visit      -> study bucket, overlap 1
      1 UPT first, study later                  -> kept (strict), dropped in the wide reading
      1 organic first, ad click later           -> kept (strict), dropped in the wide reading
      1 plain tool sign-up                      -> kept in both
      1 podcast form, 1 website form            -> kept in both
      1 partner (MLA) page sign-up              -> removed as ads
    Kept = 5, wide kept = 3, ad tag bucket = 0 (the only tagged ad click belongs to the study), ads_all = 1."""
    d = ts(2026, 10, 15)
    rows = [
        sub(d, tools="Who Attracts You", media="cpc"),
        sub(d, tools="The Ultimate Personality Test|Who Attracts You", media="(none),(none)"),
        sub(d, tools="Intrinsic Values Test|How Rational Are You, Really?", media="(none),cpc"),
        sub(d, tools="Intrinsic Values Test", media="(none)"),
        sub(d, source="podcast"),
        sub(d, channel="embed"),
        sub(d, **MLA),
    ]
    (m,) = az.summarize(rows)["months"]
    assert m["total"] == 7 and m["kept"] == 5
    assert m["kept_wide"] == 3
    assert m["study_and_ads"] == 1
    # Oct 15 sits outside every wave window, so no wave picks these rows up.
    assert all(w["signups"] == 0 and w["later_took_study"] == 0 for w in az.summarize(rows)["waves"])
    wave_day = [sub(ts(2026, 8, 5), tools="Unique Traits Test|Who Attracts You"), sub(ts(2026, 8, 5), tools="Unique Traits Test")]
    aug_wave = az.summarize(wave_day)["waves"][0]
    assert (aug_wave["signups"], aug_wave["later_took_study"]) == (2, 1)
    assert m["buckets"][az.STUDY] == 1 and m["buckets"][az.ADS] == 0 and m["buckets"][az.PARTNER_ADS] == 1
    assert m["ads_all"] == 1
    assert m["buckets"][az.TOOLS] == 3 and m["buckets"][az.PODCAST] == 1 and m["buckets"][az.FORMS] == 1
    assert sum(m["buckets"].values()) == m["total"]


def test_records_from_the_cut_day_onward_are_left_out():
    rows = [sub(ts(2026, 11, 17, 23, 59), tools="Intrinsic Values Test"), sub(ts(2026, 11, 18, 0, 0), tools="Intrinsic Values Test")]
    (m,) = az.summarize(rows)["months"]
    assert m["records"] == 1


def test_calibration_and_estimate_by_hand():
    """Calibration window Mar 28 to Apr 30: 24 + 56 = 80 tagged ad sign-ups against 30 + 70 = 100 GA4
    events -> 0.8 per event. Untagged days: January 100 events -> 80; February 50 -> 40; March 27 (the
    half-tagged day) 40 events -> 32, minus the 8 already tagged that day -> 24."""
    ga4 = {"2026-01-10": 100, "2026-02-10": 50, "2026-03-27": 40, "2026-03-28": 30, "2026-04-02": 70}
    tagged = {"2026-03-27": 8, "2026-03-28": 24, "2026-04-02": 56}
    ratio = az.calibration_ratio(tagged, ga4, date(2026, 3, 28), date(2026, 4, 30))
    assert ratio == pytest.approx(0.8)
    assert az.estimate_untagged_ads(ga4, tagged, ratio, date(2026, 3, 27)) == {"2026-01": 80, "2026-02": 40, "2026-03": 24}
    assert az.calibration_ratio({}, {}, date(2026, 3, 28), date(2026, 4, 30)) == 0.0


def test_monthly_ratios_skip_the_ga4_blackout_months():
    ga4 = {"2026-05-10": 100, "2026-07-10": 100, "2026-08-10": 100, "2026-09-10": 200}
    tagged = {"2026-05-10": 70, "2026-07-10": 100, "2026-08-10": 100, "2026-09-10": 120}
    assert az.monthly_ratios(tagged, ga4, date(2026, 4, 30)) == {"2026-05": 0.7, "2026-09": 0.6}


def test_hand_worked_estimate_end_to_end():
    """January: 200 tool sign-ups uploaded in a batch (half since unsubscribed), none carrying a tag.
    GA4 saw 100 ad-session email submissions that month. Once tagging exists (Apr 2), 56 + 24 = 80 tagged
    ad sign-ups stand against 100 GA4 events, so 0.8 x 100 = 80 of January's 200 are taken as ad sign-ups:
    kept = 120, of which still active = 100 - 80 x 50% = 60. April keeps only its 10 organic sign-ups."""
    rows = [sub(ts(2026, 1, 10), channel="import", status="active" if i % 2 else "inactive") for i in range(200)]
    rows += [sub(ts(2026, 4, 2), tools="How Rational Are You, Really?", media="cpc") for _ in range(80)]
    rows += [sub(ts(2026, 4, 2), tools="Intrinsic Values Test", media="(none)") for _ in range(10)]
    ga4 = {"2026-01-10": 100, "2026-04-02": 100}
    out = az.summarize(rows, ga4)
    jan, apr = out["months"]
    assert out["calibration"]["ratio"] == 0.8
    assert (jan["ads_untagged_est"], jan["kept_on_record"], jan["kept"], jan["kept_active"]) == (80, 200, 120, 60)
    assert jan["estimated"] is True and jan["kept_tools"] == 120 and jan["ads_all"] == 80
    assert (apr["ads_untagged_est"], apr["kept"], apr["buckets"][az.ADS], apr["estimated"]) == (0, 10, 80, False)


def test_context_counts_leaf_batches_and_the_launch_days():
    """A Leaf batch of 120 on May 10 (plus 3 strays on another day, below the 100 cut), and on the launch
    days 5 subscribers of which 3 name only the Unique Traits Test; an invalid one is ignored."""
    rows = [sub(ts(2026, 5, 10), channel="import", Leaf=True) for _ in range(120)]
    rows += [sub(ts(2026, 5, 11), channel="import", Leaf=True) for _ in range(3)]
    rows += [sub(ts(2026, 3, 24), **{az.OLD_TOOLS_FIELD: ["Unique Traits Test"]}) for _ in range(3)]
    rows += [sub(ts(2026, 3, 24), **{az.OLD_TOOLS_FIELD: ["Unique Traits Test"]}, status="invalid")]
    rows += [sub(ts(2026, 3, 26), **{az.OLD_TOOLS_FIELD: ["Unique Traits Test", "Philosophical Beliefs"]}), sub(ts(2026, 3, 23))]
    rows += [sub(ts(2026, 3, 27))]
    c = az.context(rows)
    assert c["leaf_batches"] == {"2026-05-10": 120}
    assert (c["unique_traits_launch"]["subscribers"], c["unique_traits_launch"]["unique_traits_only"]) == (5, 3)


# ---------- the whole list: unsubscribes and deletions ----------

def test_by_day_flattens_monthly_lists():
    assert az.by_day({"2026-01": [5, 6], "2026-02": [7]}) == {"2026-01-01": 5, "2026-01-02": 6, "2026-02-01": 7}


NET = {"2026-01-01": 10, "2026-01-02": -5, "2026-01-03": 2, "2026-01-04": 3, "2026-01-05": 4, "2026-01-06": -1,
       "2026-01-07": 0, "2026-01-08": 6, "2026-01-09": 8, "2026-01-10": 10}
ANCHORS = {"2026-01-04": 1000, "2026-01-11": 1030}


def test_active_on_by_hand():
    """The list was 1,000 at the start of Jan 4 and 1,030 at the start of Jan 11 (3+4-1+0+6+8+10 = 30)."""
    assert az.active_on(date(2026, 1, 4), ANCHORS, NET) == 1000
    assert az.active_on(date(2026, 1, 6), ANCHORS, NET) == 1007          # + Jan 4 and Jan 5
    assert az.active_on(date(2026, 1, 1), ANCHORS, NET) == 993           # backwards: 1000 - (10 - 5 + 2)
    assert az.active_on(date(2026, 1, 9), ANCHORS, NET) == 1012          # from the nearer anchor: 1030 - 10 - 8
    with pytest.raises(KeyError):
        az.active_on(date(2026, 1, 13), ANCHORS, NET)                    # Jan 11 and 12 have no daily figure


def test_unexplained_by_week_by_hand():
    """Week of Jan 4: the list grew 30 and subscribed minus unsubscribed is 30 -> nothing unexplained.
    Week of Jan 11: the list fell 30 but the daily figures only explain -10 -> 20 people left the list
    without an unsubscribe. The week of Jan 18 reaches past the daily series and is skipped."""
    net = dict(NET, **{f"2026-01-{d}": -2 for d in range(11, 16)}, **{"2026-01-16": 0, "2026-01-17": 0})
    anchors = dict(ANCHORS, **{"2026-01-18": 1000, "2026-01-25": 990})
    assert az.unexplained_by_week(anchors, net) == [{"week": "2026-01-04", "unexplained": 0},
                                                    {"week": "2026-01-11", "unexplained": -20}]


def test_list_movement_by_hand():
    """Two months. January: 2 days, +30 and +10 new, 10 and 20 unsubscribed, list of 1,000 at the start ->
    40 new, 30 unsubscribed (3% of the list), net +10, 1,010 at the end. February: 1 day, 5 new and 15
    gone on a list of 1,010 -> net -10. No full week of anchors is covered, so nothing can be reconciled."""
    subscribed = {"2026-01-30": 30, "2026-01-31": 10, "2026-02-01": 5}
    unsubscribed = {"2026-01-30": 10, "2026-01-31": 20, "2026-02-01": 15}
    jan, feb = az.list_movement(subscribed, unsubscribed, {"2026-01-30": 1000})
    assert (jan["active_at_start"], jan["subscribed"], jan["unsubscribed"], jan["net"], jan["active_at_end"]) == (1000, 40, 30, 10, 1010)
    assert jan["unsubscribe_rate"] == 0.03 and jan["days"] == 2
    assert (feb["active_at_start"], feb["net"], feb["active_at_end"]) == (1010, -10, 1000)
    assert jan["unexplained"] is None and jan["removed_without_unsubscribe"] is None


def test_recorded_vs_history_interpolates_inside_the_day():
    """beehiiv says the list was 1,000 at the start of Jan 4 and gained 3 that day (in NET, Jan 4 = +3; here
    +300 to make the fraction visible). The dashboard recorded 1,070 at 06:00, a quarter into the day:
    history says 1,000 + 0.25 x 300 = 1,075, so the gap is -5."""
    net = dict(NET, **{"2026-01-04": 300})
    (row,) = az.recorded_vs_history([{"generated_at": "2026-01-04T06:00:00+00:00", "active": 1070}], ANCHORS, net)
    assert row == {"day": "2026-01-04", "recorded": 1070, "history": 1075, "gap": -5, "day_net": 300}
    # a snapshot from a day beehiiv's daily series does not cover is ignored
    assert az.recorded_vs_history([{"generated_at": "2026-03-01T06:00:00+00:00", "active": 1}], ANCHORS, net) == []


def synthetic_list(rng, first=date(2026, 6, 1), days=153, start=450_000, noisy_days=()):
    """A list as beehiiv would report it today: daily new subscribers and unsubscribes, the list size at
    the start of every 7th day, and the true size at the start of each day."""
    subscribed, unsubscribed, size_at, anchors, size = {}, {}, {}, {}, start
    for i in range(days):
        d = first + timedelta(days=i)
        size_at[str(d)] = size
        if i % 7 == 0:
            anchors[str(d)] = size
        subscribed[str(d)] = rng.randint(150, 600) + (40_000 if str(d) in noisy_days else 0)
        unsubscribed[str(d)] = rng.randint(100, 700)
        size += subscribed[str(d)] - unsubscribed[str(d)]
    return subscribed, unsubscribed, anchors, size_at


def dashboard_snapshots(rng, subscribed, unsubscribed, size_at, deleted=0, deleted_on=None, skip=()):
    """What the dashboard would have recorded once a day at a random time: the live list size, which
    before `deleted_on` still included the `deleted` subscribers beehiiv has since erased from its history."""
    out = []
    for day, size in size_at.items():
        if day in skip:
            continue
        hour, minute = rng.randint(0, 23), rng.randint(0, 59)
        live = size + round((hour * 3600 + minute * 60) / 86400 * (subscribed[day] - unsubscribed[day]))
        if deleted_on and day < deleted_on:
            live += deleted
        out.append({"generated_at": f"{day}T{hour:02d}:{minute:02d}:00+00:00", "active": live})
    return out


def test_deletion_scan_null_world_finds_nothing():
    """Nobody was deleted: what the dashboard recorded equals beehiiv's history on every day, so no month's
    gap falls by more than rounding, and the weekly books reconcile to zero."""
    rng = random.Random(3)
    subscribed, unsubscribed, anchors, size_at = synthetic_list(rng)
    net = {d: subscribed[d] - unsubscribed[d] for d in subscribed}
    scan = az.deletion_scan(dashboard_snapshots(rng, subscribed, unsubscribed, size_at), anchors, net)
    assert len(scan["months"]) == 5 and all(abs(m["median_gap"]) <= 1 for m in scan["months"])
    assert scan["largest_fall"] <= 1
    assert all(w["unexplained"] == 0 for w in az.unexplained_by_week(anchors, net))
    assert all(m["removed_without_unsubscribe"] in (0, None) for m in az.list_movement(subscribed, unsubscribed, anchors))


@pytest.mark.parametrize("deleted_on, month_of_fall", [("2026-08-01", "2026-08"), ("2026-08-20", "2026-09")])
def test_deletion_scan_positive_world_finds_an_erased_bulk_deletion(deleted_on, month_of_fall):
    """5,000 subscribers were deleted and beehiiv erased them from its history: before the deletion the
    dashboard's recorded size runs 5,000 above today's history, afterwards it matches. The scan must report
    a fall of 5,000 in the first month whose typical day is after the deletion."""
    rng = random.Random(4)
    subscribed, unsubscribed, anchors, size_at = synthetic_list(rng)
    net = {d: subscribed[d] - unsubscribed[d] for d in subscribed}
    snaps = dashboard_snapshots(rng, subscribed, unsubscribed, size_at, deleted=5000, deleted_on=deleted_on)
    scan = az.deletion_scan(snaps, anchors, net)
    falls = {m["month"]: m["fall"] for m in scan["months"]}
    assert abs(falls[month_of_fall] - 5000) <= 2
    assert abs(scan["largest_fall"] - 5000) <= 2
    assert all(f is None or f <= 2 for month, f in falls.items() if month != month_of_fall)


def test_books_positive_world_finds_removals_beehiiv_does_not_call_unsubscribes():
    """300 people dropped off the list in the week of Jul 6 without being counted as unsubscribed (the
    list size fell, the daily figures did not): that week is unexplained by -300 and July shows 300."""
    rng = random.Random(5)
    subscribed, unsubscribed, anchors, _ = synthetic_list(rng)
    net = {d: subscribed[d] - unsubscribed[d] for d in subscribed}
    anchors = {d: n - (300 if d > "2026-07-06" else 0) for d, n in anchors.items()}
    weeks = {w["week"]: w["unexplained"] for w in az.unexplained_by_week(anchors, net)}
    assert weeks["2026-07-06"] == -300 and sum(weeks.values()) == -300
    by_month = {m["month"]: m["removed_without_unsubscribe"] for m in az.list_movement(subscribed, unsubscribed, anchors)}
    assert by_month["2026-07"] == 300 and by_month["2026-06"] == 0 and by_month["2026-08"] == 0


def test_deletion_scan_skips_noisy_days_and_thin_months():
    """A day with a 40,000 import is not used (its time-of-day interpolation is meaningless), and a month
    with fewer than three usable days neither gets a fall nor serves as the comparison for the next one."""
    rng = random.Random(6)
    noisy = ("2026-08-12",)
    subscribed, unsubscribed, anchors, size_at = synthetic_list(rng, noisy_days=noisy)
    net = {d: subscribed[d] - unsubscribed[d] for d in subscribed}
    july_but_two = tuple(d for d in size_at if d[:7] == "2026-07" and d[8:] not in ("10", "20"))
    scan = az.deletion_scan(dashboard_snapshots(rng, subscribed, unsubscribed, size_at, skip=july_but_two), anchors, net)
    months = {m["month"]: m for m in scan["months"]}
    assert months["2026-08"]["calm_days"] == 30          # 31 days minus the import day
    assert months["2026-07"]["calm_days"] == 2 and months["2026-07"]["fall"] is None
    assert months["2026-06"]["fall"] is None             # the first month has nothing to compare with
    assert months["2026-08"]["fall"] is not None         # compared with June, not with thin July
    assert scan["first_day"] == "2026-06-01"


def test_wave_excess_by_hand():
    """Three wave days with 50, 80 and 20 sign-ups. Two baseline days on each side: 10, 12 before and
    14, 100 after (one outlier). Median of (10, 12, 14, 100) = 13 a day, so the wave's excess is
    150 - 3 x 13 = 111."""
    daily = {"2026-08-01": 10, "2026-08-02": 12, "2026-08-03": 50, "2026-08-04": 80, "2026-08-05": 20,
             "2026-08-06": 14, "2026-08-07": 100}
    w = az.wave_excess(daily, date(2026, 8, 3), date(2026, 8, 5), baseline_days=2)
    assert w == {"days": 3, "signups": 150, "baseline_per_day": 13, "excess": 111}


def test_wave_excess_is_zero_on_a_flat_series():
    daily = {f"2026-09-{d:02d}": 200 for d in range(1, 31)}
    assert az.wave_excess(daily, date(2026, 9, 12), date(2026, 9, 15), baseline_days=5)["excess"] == 0


# ---------- 2. realistic synthetic worlds ----------

TOOL_NAMES = ["The Ultimate Personality Test", "How Rational Are You, Really?", "Intrinsic Values Test",
              "Philosophical Beliefs", "Unique Traits Test", "Gender Continuum Test"]
MONTHS = [(2026, m) for m in range(1, 12)]


def day_ts(rng, y, m):
    day = rng.randint(2, 17 if m == 11 else 28)  # after the Jan 1 backlog batch, before the Nov 18 cut
    return ts(y, m, day, rng.randint(0, 23))


def organic_row(rng, y, m):
    """A record that must be KEPT, drawn from the shapes seen in the real data, including the look-alikes:
    readers who met the study or an ad only on a later visit."""
    created = day_ts(rng, y, m)
    status = rng.choices(["active", "inactive", "invalid"], [88, 8, 4])[0]
    kind = rng.random()
    if created < az.API_FROM.timestamp():  # the batch-upload era: no tool or UTM data on the record
        if kind < 0.80:
            row = sub(created, channel="import", status=status)
            if rng.random() < 0.05:  # took the study months later: the list's first entry is not the sign-up
                row["cf"][az.TOOLS_FIELD] = "Who Attracts You"
                row["cf"][az.MEDIA_FIELD] = "cpc"
            return row
        return sub(created, channel="embed", status=status)
    if kind < 0.70:
        first = rng.choice(TOOL_NAMES)
        later_tools, later_media = "", ""
        if rng.random() < 0.10:
            later_tools, later_media = "|Who Attracts You", ",(none)"
        elif rng.random() < 0.05:
            later_tools, later_media = "|" + rng.choice(TOOL_NAMES), ",cpc"
        lead = rng.choice(["", "", "", "|"])  # the leading-separator bug on some rows
        return sub(created, tools=lead + first + later_tools, media=("," if lead else "") + "(none)" + later_media,
                   status=status)
    if kind < 0.80:
        return sub(created, channel="embed", status=status)
    if kind < 0.85:
        return sub(created, source="podcast", status=status)
    if kind < 0.95:
        return sub(created, channel="import", status=status, Leaf=rng.random() < 0.5)
    return sub(created, channel="recommendation", source="www.example.com", status=status)


def test_null_world_removes_nothing():
    """Nobody came from ads or the study, and GA4 saw no ad-session sign-ups: every month's kept count
    must equal its subscribers."""
    rng = random.Random(1)
    rows = [organic_row(rng, y, m) for (y, m) in MONTHS for _ in range(rng.randint(200, 400))]
    out = az.summarize(rows, {"2026-02-01": 0})["months"]
    assert len(out) == len(MONTHS)
    for m in out:
        assert m["kept"] == m["total"] == m["records"] - m["invalid"]
        assert all(m["buckets"][b] == 0 for b in az.EXCLUDED)
        assert m["ads_all"] == 0 and m["estimated"] is False
        assert m["kept_active"] <= m["kept"]
    assert sum(m["records"] for m in out) == len(rows)
    assert sum(m["invalid"] for m in out) == sum(r["status"] == "invalid" for r in rows) > 0
    assert sum(m["kept_active"] for m in out) == sum(r["status"] == "active" for r in rows)


def test_positive_world_recovers_the_planted_counts():
    """Known numbers of study, tagged-ad and partner-ad sign-ups planted per month among organic
    look-alikes; in Jan and Feb the ad sign-ups are planted WITHOUT tags (as in the real data) and GA4
    events are generated at a fixed 0.75 sign-ups per event, so the estimate must find them."""
    rng = random.Random(2)
    rows, planted, ga4 = [], {}, {}
    per_event = 0.75
    for (y, m) in MONTHS:
        key = f"{y}-{m:02d}"
        organic = [organic_row(rng, y, m) for _ in range(rng.randint(300, 500))]
        n_org = sum(r["status"] != "invalid" for r in organic)  # invalid addresses are nobody's subscribers
        rows += organic
        n_ads, n_partner = 12 * rng.randint(1, 8), rng.randint(0, 40)
        tagging_exists = m >= 4
        n_study, n_both = (rng.randint(0, 500), rng.randint(0, 5)) if tagging_exists else (0, 0)
        for _ in range(n_study):
            shape = rng.choice(["api", "import", "waitlist", "bug"])
            created = day_ts(rng, y, m)
            if shape == "api":
                rows.append(sub(created, tools="Who Attracts You|Unique Traits Test", media="(none),(none)"))
            elif shape == "import":
                rows.append(sub(created, channel="import", tools="Who Attracts You", **DATING))
            elif shape == "waitlist":
                rows.append(sub(created, **DATING))
            else:
                rows.append(sub(created, tools="|Who Attracts You", media=",(none)"))
        ad_day = f"{key}-15"
        ga4[ad_day] = round(n_ads / per_event)  # n_ads is a multiple of 12, so this is exact
        for _ in range(n_ads):
            created = ts(y, m, 15, rng.randint(0, 23))
            if not tagging_exists:  # an untagged upload row, indistinguishable from an organic one
                rows.append(sub(created, channel="import" if m < 3 else "api", **({} if m < 3 else OLD_TOOL)))
            elif rng.random() < 0.5:
                rows.append(sub(created, tools=rng.choice(TOOL_NAMES), media="cpc,(none)"))
            else:
                rows.append(sub(created, tools=rng.choice(TOOL_NAMES), media="(none)", medium="cpc", source="google"))
        rows += [sub(day_ts(rng, y, m), **MLA) for _ in range(n_partner)]
        rows += [sub(ts(y, m, 15), tools="Who Attracts You", media="cpc") for _ in range(n_both)]
        planted[key] = (n_org, n_study, n_ads, n_partner, n_both, tagging_exists)
    rng.shuffle(rows)
    result = az.summarize(rows, ga4)
    assert result["calibration"]["ratio"] == pytest.approx(per_event)
    assert result["calibration"]["low"] == result["calibration"]["high"] == pytest.approx(per_event)
    out = {m["month"]: m for m in result["months"]}
    assert set(out) == set(planted)
    for month, (n_org, n_study, n_ads, n_partner, n_both, tagging_exists) in planted.items():
        m = out[month]
        assert m["kept"] == n_org, month
        assert m["buckets"][az.STUDY] == n_study + n_both
        assert m["buckets"][az.PARTNER_ADS] == n_partner
        assert m["study_and_ads"] == n_both
        assert m["ads_all"] == n_ads + n_partner
        if tagging_exists:
            assert m["buckets"][az.ADS] == n_ads and m["ads_untagged_est"] == 0
        else:
            assert m["buckets"][az.ADS] == 0 and m["ads_untagged_est"] == n_ads and m["estimated"]
        assert m["total"] == n_org + n_study + n_ads + n_partner + n_both
        assert m["kept_wide"] <= m["kept_on_record"]


# ---------- net change without manual imports ----------

def test_routine_upload_rule():
    tool_batch = sub(created=EARLY, channel="import", tools="Rationality Test")
    plain_batch = sub(created=EARLY, channel="import")  # pre-Mar 10 tool uploads often carry no list
    backlog = sub(created=ts(2026, 1, 1, 1, 15), channel="import")
    leaf = sub(created=EARLY, channel="import", Leaf=True)
    workshop = sub(created=EARLY, channel="import", **{"Career workshop": True})
    later_upload = sub(created=ts(2026, 4, 2), channel="import")
    api = sub(created=EARLY, channel="api", tools="Rationality Test")
    assert az.is_routine_upload(tool_batch) and az.is_routine_upload(plain_batch)
    assert not any(az.is_routine_upload(r) for r in (backlog, leaf, workshop, later_upload, api))
    assert not az.is_import(api)


def test_net_without_imports_by_hand():
    # January: 3 genuine (1 api + 2 routine uploads), 2 manual (backlog + Leaf), 1 invalid import ignored.
    # Unsubscribes 4, so net = (5 - 2) - 4 = -1. February: 1 genuine, 1 manual upload after Mar 10 is in
    # March, so February = 1 - 0 - 0 = 1.
    rows = [sub(created=ts(2026, 1, 5)), sub(created=ts(2026, 1, 6), channel="import"),
            sub(created=ts(2026, 1, 7), channel="import", tools="UPT"),
            sub(created=ts(2026, 1, 1, 1, 15), channel="import"), sub(created=ts(2026, 1, 16), channel="import", Leaf=True, status="inactive"),
            sub(created=ts(2026, 1, 20), channel="import", status="invalid"),
            sub(created=ts(2026, 2, 3)), sub(created=ts(2026, 3, 12), channel="import")]
    movement = [{"month": "2026-01", "subscribed": 5, "unsubscribed": 4},
                {"month": "2026-02", "subscribed": 1, "unsubscribed": 0},
                {"month": "2026-03", "subscribed": 1, "unsubscribed": 3}]
    jan, feb, mar = az.net_without_imports(rows, movement)
    assert (jan["manual_imports"], jan["routine_tool_uploads"], jan["new_without_imports"], jan["net"]) == (2, 2, 3, -1)
    assert jan["manual_imports_unsubscribed_since"] == 1
    assert (feb["manual_imports"], feb["new_without_imports"], feb["net"]) == (0, 1, 1)
    assert (mar["manual_imports"], mar["new_without_imports"], mar["net"]) == (1, 0, -3)


def test_net_without_imports_null_and_positive_worlds():
    rng = random.Random(7)
    months = ["2026-%02d" % m for m in range(4, 10)]
    genuine = {m: rng.randint(200, 400) for m in months}
    gone = {m: rng.randint(100, 500) for m in months}
    rows = [sub(created=ts(2026, int(m[5:]), rng.randint(1, 28), rng.randint(0, 23)),
                tools=rng.choice(["UPT", "Rationality Test", ""])) for m in months for _ in range(genuine[m])]
    movement = [{"month": m, "subscribed": genuine[m], "unsubscribed": gone[m]} for m in months]
    # null world: no imports at all, so net = new - unsubscribed exactly
    for r in az.net_without_imports(rows, movement):
        assert r["manual_imports"] == 0 and r["net"] == genuine[r["month"]] - gone[r["month"]]
    # positive world: plant a bulk import in two months; it enters beehiiv's count but not the net
    planted = {"2026-05": 1310, "2026-08": 5000}
    for m, n in planted.items():
        rows += [sub(created=ts(2026, int(m[5:]), 10), channel="import", Leaf=(m == "2026-05")) for _ in range(n)]
        next(x for x in movement if x["month"] == m)["subscribed"] += n
    for r in az.net_without_imports(rows, movement):
        assert r["manual_imports"] == planted.get(r["month"], 0)
        assert r["net"] == genuine[r["month"]] - gone[r["month"]]


def test_steady_flow_by_hand():
    # March: 9,000 kept, of which 500 Leaf and a 3,000 launch -> organic 5,500; ads 2,000; 7,000 gone.
    # April: 6,000 kept, no one-offs; ads 0 (null world for ads: both nets equal).
    def month(m, kept, leaf, ads):
        return {"month": m, "kept": kept, "ads_all": ads, "estimated": False, "buckets": {az.LEAF: leaf}}
    months = [month("2026-03", 9000, 500, 2000), month("2026-04", 6000, 0, 0)]
    movement = [{"month": "2026-03", "unsubscribed": 7000}, {"month": "2026-04", "unsubscribed": 6500}]
    mar, apr = az.steady_flow(months, movement, {"first": "2026-03-23", "kept": 3000})
    assert (mar["organic"], mar["net_without_ads"], mar["net_with_ads"]) == (5500, -1500, 500)
    assert (apr["organic"], apr["launch"], apr["net_without_ads"], apr["net_with_ads"]) == (6000, 0, -500, -500)
