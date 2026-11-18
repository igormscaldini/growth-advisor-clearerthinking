"""Tests for reports/subscribers_by_month_2026-11-18_src/analysis.py.

Three layers, as the project's data-science rules ask:
  1. the reading rules one by one, then two tiny data sets whose monthly table is worked out by hand;
  2. two realistic synthetic "worlds" shaped like the real beehiiv records: a null one (nobody came from
     ads or the study, so nothing may be removed) and a positive one (known numbers planted per month,
     hidden among look-alikes that must NOT be removed);
  3. the independent recount lives in cross_check.py beside the analysis (it needs the real data).
"""
import importlib.util
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "reports" / "subscribers_by_month_2026-11-18_src"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"subs_by_month_{name}", SRC / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


az = _load("analysis")


def ts(y, m, d, hour=12):
    return int(datetime(y, m, d, hour, tzinfo=timezone.utc).timestamp())


_ids = iter(range(10**9))


def sub(created, tools=None, media=None, channel="api", status="active", medium="", source="direct", **flags):
    """A slim subscription row as fetch_data.py writes it."""
    cf = dict(flags)
    if tools is not None:
        cf[az.TOOLS_FIELD] = tools
    if media is not None:
        cf[az.MEDIA_FIELD] = media
    return {"id": f"sub_{next(_ids)}", "created": created, "status": status, "utm_channel": channel,
            "utm_medium": medium, "utm_source": source, "utm_campaign": "", "cf": cf}


# ---------- 1a. reading rules ----------

def test_tokens_skip_blanks_and_keep_order():
    assert az.tokens("A| B |(none)||C", "|") == ["a", "b", "c"]
    assert az.tokens(None, "|") == []
    assert az.tokens(True, "|") == []


def test_media_keeps_none_visits_in_position():
    assert az.media(sub(0, media="(none),cpc")) == ["", "cpc"]
    assert az.media(sub(0, media="cpc,(none)")) == ["cpc", ""]


def test_media_drops_the_leading_separator_bug():
    # Sep 29 to Oct 8, 2026: the tools wrote ",cpc" and "|Tool".
    assert az.media(sub(0, media=",cpc")) == ["cpc"]
    assert az.media(sub(0, media=",(none)")) == [""]
    assert az.tools_tried(sub(0, tools="|Who Attracts You|Unique Traits Test")) == ["who attracts you", "unique traits test"]


@pytest.mark.parametrize("row, first, anywhere", [
    (sub(0, media="cpc"), True, True),
    (sub(0, media="cpc,(none)"), True, True),
    (sub(0, media=",cpc"), True, True),
    (sub(0, media="(none),cpc"), False, True),        # a reader who clicked an ad LATER
    (sub(0, media="(none)", medium="cpc"), True, True),  # beehiiv's own field, set at creation
    (sub(0, media="(none),email"), False, False),
    (sub(0, media="CPC"), True, True),
    (sub(0), False, False),
])
def test_ads_is_the_first_visit(row, first, anywhere):
    assert az.from_ads(row) is first
    assert az.touched_ads(row) is anywhere


@pytest.mark.parametrize("row, first, anywhere", [
    (sub(0, tools="Who Attracts You"), True, True),
    (sub(0, tools="|Who Attracts You"), True, True),
    (sub(0, tools="Who Attracts You|Unique Traits Test"), True, True),
    (sub(0, tools="The Ultimate Personality Test|Who Attracts You"), False, True),  # came for the UPT
    (sub(0, **{"Dating App Updates": True}), True, True),                            # waitlist, no tool
    (sub(0, tools="Intrinsic Values Test", **{"Dating App Updates": True}), False, True),
    (sub(0, tools="Intrinsic Values Test"), False, False),
    (sub(0), False, False),
])
def test_study_is_the_first_tool(row, first, anywhere):
    assert az.from_study(row) is first
    assert az.touched_study(row) is anywhere


@pytest.mark.parametrize("row, expected", [
    (sub(0, tools="Who Attracts You", media="cpc"), az.STUDY),   # both: study wins, overlap counted apart
    (sub(0, tools="How Rational Are You, Really?", media="cpc"), az.ADS),
    (sub(0, tools="How Rational Are You, Really?", media="(none)"), az.TOOLS),
    (sub(0, channel="import", Leaf=True), az.LEAF),
    (sub(0, channel="import"), az.UPLOADS),
    (sub(0, channel="import", tools="Who Attracts You"), az.STUDY),
    (sub(0, channel="import", **{"Dating App Updates": True}), az.STUDY),
    (sub(0, channel="recommendation", source="www.example.com"), az.RECOMMENDATIONS),
    (sub(0, source="podcast"), az.PODCAST),
    (sub(0, channel="embed"), az.FORMS),
    (sub(0, channel="api"), az.FORMS),
    (sub(0, channel="something_new"), az.OTHER),
])
def test_bucket(row, expected):
    assert az.bucket(row) == expected


def test_month_is_utc():
    # 2026-03-31 23:30 UTC is still March; 00:30 UTC on Apr 1 is April.
    assert az.month_of({"created": int(datetime(2026, 3, 31, 23, 30, tzinfo=timezone.utc).timestamp())}) == "2026-03"
    assert az.month_of({"created": int(datetime(2026, 4, 1, 0, 30, tzinfo=timezone.utc).timestamp())}) == "2026-04"


# ---------- 1b. two tiny data sets, answers worked out by hand ----------

def test_hand_worked_set_a():
    """January: 6 records, one of them an invalid address that beehiiv never counted, so 5 subscribers:
    2 organic tool sign-ups (one since unsubscribed), 1 ad click, 1 study, 1 Leaf upload.
    Kept = 5 - 1 ad - 1 study = 3, of which active = 2 (one tool sign-up is inactive).
    February: 2 records, both study -> kept 0."""
    rows = [
        sub(ts(2026, 1, 3), tools="Intrinsic Values Test", media="(none)"),
        sub(ts(2026, 1, 9), tools="Intrinsic Values Test", media="(none)", status="inactive"),
        sub(ts(2026, 1, 9), tools="How Rational Are You, Really?", media="cpc"),
        sub(ts(2026, 1, 20), tools="Who Attracts You", media="(none)"),
        sub(ts(2026, 1, 31), channel="import", Leaf=True),
        sub(ts(2026, 1, 31), tools="Intrinsic Values Test", media="(none)", status="invalid"),
        sub(ts(2026, 2, 1), tools="Who Attracts You", media="(none)"),
        sub(ts(2026, 2, 28), channel="import", tools="Who Attracts You"),
    ]
    jan, feb = az.summarize(rows)["months"]
    assert (jan["month"], jan["total"], jan["excluded"], jan["included"], jan["included_active"]) == ("2026-01", 5, 2, 3, 2)
    assert jan["buckets"][az.TOOLS] == 2 and jan["buckets"][az.LEAF] == 1
    assert jan["buckets"][az.ADS] == 1 and jan["buckets"][az.STUDY] == 1
    assert jan["imports"] == 1
    assert (jan["records"], jan["invalid"]) == (6, 1)
    assert (feb["month"], feb["total"], feb["excluded"], feb["included"], feb["included_active"]) == ("2026-02", 2, 2, 0, 0)


def test_hand_worked_set_b_overlap_and_wide_reading():
    """One month, 6 records:
      1 study + ad on the same first visit      -> study bucket, overlap 1
      1 UPT first, study later                  -> kept (strict), dropped in the wide reading
      1 organic first, ad click later           -> kept (strict), dropped in the wide reading
      1 plain tool sign-up                      -> kept in both
      1 podcast form, 1 website form            -> kept in both
    Strict kept = 5, wide kept = 3, removed = 1, ads bucket = 0 (the only ad click belongs to the study)."""
    d = ts(2026, 10, 15)
    rows = [
        sub(d, tools="Who Attracts You", media="cpc"),
        sub(d, tools="The Ultimate Personality Test|Who Attracts You", media="(none),(none)"),
        sub(d, tools="Intrinsic Values Test|How Rational Are You, Really?", media="(none),cpc"),
        sub(d, tools="Intrinsic Values Test", media="(none)"),
        sub(d, source="podcast"),
        sub(d, channel="embed"),
    ]
    (m,) = az.summarize(rows)["months"]
    assert m["total"] == 6 and m["included"] == 5 and m["excluded"] == 1
    assert m["included_wide"] == 3
    assert m["study_and_ads"] == 1
    assert m["buckets"][az.STUDY] == 1 and m["buckets"][az.ADS] == 0
    assert m["buckets"][az.TOOLS] == 3 and m["buckets"][az.PODCAST] == 1 and m["buckets"][az.FORMS] == 1
    assert sum(m["buckets"].values()) == m["total"]


# ---------- 2. realistic synthetic worlds ----------

TOOLS = ["The Ultimate Personality Test", "How Rational Are You, Really?", "Intrinsic Values Test",
         "Philosophical Beliefs", "Unique Traits Test", "Gender Continuum Test"]
MONTHS = [(2026, m) for m in range(1, 12)]


def organic_row(rng, y, m):
    """A record that must be KEPT, drawn from the shapes seen in the real data, including the look-alikes:
    readers who met the study or an ad only on a later visit."""
    created = ts(y, m, rng.randint(1, 28), rng.randint(0, 23))
    status = rng.choices(["active", "inactive", "invalid"], [88, 8, 4])[0]
    kind = rng.random()
    if kind < 0.70:
        first = rng.choice(TOOLS)
        later_tools, later_media = "", ""
        if rng.random() < 0.10:
            later_tools, later_media = "|Who Attracts You", ",(none)"
        elif rng.random() < 0.05:
            later_tools, later_media = "|" + rng.choice(TOOLS), ",cpc"
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
    """Nobody came from ads or the study: every month's kept count must equal its total."""
    rng = random.Random(1)
    rows = [organic_row(rng, y, m) for (y, m) in MONTHS for _ in range(rng.randint(200, 400))]
    out = az.summarize(rows)["months"]
    assert len(out) == len(MONTHS)
    for m in out:
        assert m["excluded"] == 0
        assert m["included"] == m["total"] == m["records"] - m["invalid"]
        assert m["buckets"][az.STUDY] == 0 and m["buckets"][az.ADS] == 0
        assert m["included_active"] <= m["included"]
    assert sum(m["records"] for m in out) == len(rows)
    assert sum(m["invalid"] for m in out) == sum(r["status"] == "invalid" for r in rows) > 0
    assert sum(m["included_active"] for m in out) == sum(r["status"] == "active" for r in rows)


def test_positive_world_recovers_the_planted_counts():
    """Known numbers of study and ad sign-ups planted per month among organic look-alikes."""
    rng = random.Random(2)
    rows, planted = [], {}
    for (y, m) in MONTHS:
        n_org, n_study, n_ads, n_both = rng.randint(200, 400), rng.randint(0, 500), rng.randint(0, 80), rng.randint(0, 5)
        organic = [organic_row(rng, y, m) for _ in range(n_org)]
        n_org = sum(r["status"] != "invalid" for r in organic)  # invalid addresses are nobody's subscribers
        planted[f"{y}-{m:02d}"] = (n_org, n_study, n_ads, n_both)
        rows += organic
        for _ in range(n_study):
            shape = rng.choice(["api", "import", "waitlist", "bug"])
            created = ts(y, m, rng.randint(1, 28))
            if shape == "api":
                rows.append(sub(created, tools="Who Attracts You|Unique Traits Test", media="(none),(none)"))
            elif shape == "import":
                rows.append(sub(created, channel="import", tools="Who Attracts You", **{"Dating App Updates": True}))
            elif shape == "waitlist":
                rows.append(sub(created, **{"Dating App Updates": True}))
            else:
                rows.append(sub(created, tools="|Who Attracts You", media=",(none)"))
        for _ in range(n_ads):
            created = ts(y, m, rng.randint(1, 28))
            if rng.random() < 0.5:
                rows.append(sub(created, tools=rng.choice(TOOLS), media="cpc,(none)"))
            else:
                rows.append(sub(created, tools=rng.choice(TOOLS), media="(none)", medium="cpc", source="google"))
        rows += [sub(ts(y, m, 15), tools="Who Attracts You", media="cpc") for _ in range(n_both)]
    rng.shuffle(rows)
    out = {m["month"]: m for m in az.summarize(rows)["months"]}
    assert set(out) == set(planted)
    for month, (n_org, n_study, n_ads, n_both) in planted.items():
        m = out[month]
        assert m["included"] == n_org
        assert m["buckets"][az.STUDY] == n_study + n_both
        assert m["buckets"][az.ADS] == n_ads
        assert m["study_and_ads"] == n_both
        assert m["total"] == n_org + n_study + n_ads + n_both
        assert m["included_wide"] <= m["included"]
