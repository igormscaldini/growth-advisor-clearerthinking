"""Tests for reports/sponsorship_price_sheet_2026-11-02_src/pricing.py (pure functions, hand-worked answers)."""
import importlib.util
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "reports" / "sponsorship_price_sheet_2026-11-02_src" / "pricing.py"
spec = importlib.util.spec_from_file_location("pricing", SRC)
pz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pz)


def post(date, recipients, opens, subject="One Helpful Idea: X"):
    return {"date": date, "recipients": recipients, "unique_opens": opens, "subject": subject}


def test_group_editions_sums_same_day_splits_and_keeps_days_apart():
    eds = pz.group_editions([
        post("2026-10-16", 259406, 53100, "The supplement paradox"),
        post("2026-10-16", 125521, 11805, "Should you take supplements?"),
        post("2026-10-22", 624751, 125226, "Should you steelman people you disagree with?"),
        post("2026-10-22", 6, 4, "Should you steelman people you disagree with?"),   # test send, ignored
        post("2026-10-22", 544, 374, "We're about to start!"),                        # tiny reminder, ignored
    ])
    assert [e["date"] for e in eds] == ["2026-10-16", "2026-10-22"]
    assert eds[1]["posts"] == 1 and eds[1]["recipients"] == 624751
    assert eds[0]["recipients"] == 384927 and eds[0]["unique_opens"] == 64905 and eds[0]["posts"] == 2
    assert eds[0]["open_rate"] == pytest.approx(64905 / 384927)
    assert eds[0]["subject"] == "Should you take supplements? | The supplement paradox"
    assert eds[0]["weekday"] == "Fri" and eds[1]["weekday"] == "Thu"


def test_regular_editions_filters_promos_small_sends_dormant_blasts_and_fresh_sends():
    eds = pz.group_editions([
        post("2026-09-14", 232000, 13334, "Free tool: What's your type?"),      # promo AND 5.7% open rate
        post("2026-09-18", 336296, 102007, "What can science teach you about happiness?"),
        post("2026-09-26", 77647, 34456, "You're invited to our upcoming workshop"),  # small + promo
        post("2026-10-21", 371636, 74879, "One Helpful Idea: Great But Awful"),
        post("2026-10-30", 252169, 6235, "The supplement paradox"),            # too fresh, and 2.5% open rate
        post("2026-10-14", 18279, 6886, "Limited spots for the rest of 2026"),  # coaching blast, same day as...
        post("2026-10-14", 358641, 71471, "Too Many Stories"),                  # ...a real edition, which stays
        post("2026-08-13", 176146, 24529, "Debunking meditation myths (and a new tool for meditation)"),
        post("2026-08-13", 176761, 60560, "Debunking meditation myths (and a new tool for meditation)"),
    ])
    reg = pz.regular_editions(eds, until="2026-10-28")
    assert [e["date"] for e in reg] == ["2026-08-13", "2026-09-18", "2026-10-14", "2026-10-21"]
    aug13 = reg[0]
    assert aug13["posts"] == 2 and aug13["recipients"] == 352907 and aug13["unique_opens"] == 85089
    assert reg[2]["recipients"] == 358641   # the 18k coaching blast did not merge into it


def test_promo_detection_is_anchored_at_the_start():
    assert pz.is_promo("New Tool: Who attracts you?")
    assert pz.is_promo("[Fixed] Your free chapter of The 12 Levers")
    assert pz.is_promo("Our most important ideas from July, in 2 minutes.")
    assert not pz.is_promo("Debunking meditation myths (and a new tool for meditation)")
    assert not pz.is_promo("One Helpful Idea: Dating App Incentives")
    assert not pz.is_promo("[Variant A - Bad to Excellent] Is what you've been taught about habits wrong?")


def test_summarize_hand_worked():
    s = pz.summarize([10, 20, 30, 40, 50])
    assert s == {"n": 5, "median": 30, "mean": 30, "p25": 20, "p75": 40, "min": 10, "max": 50}
    assert pz.summarize([100, 300]) == {"n": 2, "median": 200, "mean": 200, "p25": 150, "p75": 250, "min": 100, "max": 300}
    assert pz.summarize([7]) == {"n": 1, "median": 7, "mean": 7, "p25": 7, "p75": 7, "min": 7, "max": 7}
    assert pz.summarize([]) == {"n": 0}


def test_by_month_and_editions_per_week():
    eds = [{"date": "2026-07-01", "unique_opens": 100}, {"date": "2026-07-03", "unique_opens": 300},
           {"date": "2026-08-05", "unique_opens": 200}]
    assert pz.by_month(eds) == [{"month": "2026-07", "n": 2, "median": 200, "mean": 200, "p25": 150, "p75": 250, "min": 100, "max": 300},
                                {"month": "2026-08", "n": 1, "median": 200, "mean": 200, "p25": 200, "p75": 200, "min": 200, "max": 200}]
    # Jul 1 and Jul 3 fall in the same ISO week, Aug 5 in another: 3 editions over 2 weeks
    assert pz.editions_per_week(eds) == 1.5
    assert pz.editions_per_week([]) == 0.0


def test_cost_is_cpm_arithmetic_with_optional_rounding():
    assert pz.cost(87375, 25) == 2184            # 87.375 x 25 = 2,184.375
    assert pz.cost(87375, 25, step=50) == 2200
    assert pz.cost(6000, 25) == 150
    assert pz.cost(12000, 25, step=50) == 300
    assert pz.cost(0, 25) == 0


def test_suggested_cap_matches_the_80k_hours_precedent():
    # $4,800 typical -> 20% headroom = $5,760 -> rounded up to $500 = $6,000
    assert pz.suggested_cap(4800) == 6000
    assert pz.suggested_cap(2200) == 3000        # 2,640 -> 3,000
    assert pz.suggested_cap(5000, headroom=0.0) == 5000  # exact multiple is not bumped
    assert pz.round_up(5001, 500) == 5500


def test_package_reach_counts_each_placement():
    reach = {"newsletter": 87375, "podcast": 6000, "youtube": 12000}
    assert pz.package_reach(reach, {"newsletter": 2, "podcast": 1, "youtube": 1}) == 192750
    assert pz.package_reach(reach, {"newsletter": 1}) == 87375


def test_formatting():
    assert pz.fmt_money(4818.75) == "$4,819" and pz.fmt_int(679119) == "679,119"
