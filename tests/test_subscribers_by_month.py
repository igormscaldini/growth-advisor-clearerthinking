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
from datetime import date, datetime, timezone
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
