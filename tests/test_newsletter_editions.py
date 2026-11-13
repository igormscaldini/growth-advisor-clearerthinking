"""Tests for newsletter_editions.py: the edition classifier behind the Average Unique Opens Per Campaign
goal (and the sponsorship price sheet). Synthetic data with hand-worked answers."""
from datetime import date

import pytest

import newsletter_editions as ne


def post(date_, recipients, opens, subject="One Helpful Idea: X", title=None):
    return {"date": date_, "recipients": recipients, "unique_opens": opens, "subject": subject,
            "title": title if title is not None else subject}


def api_post(ts, recipients, opens, subject, title=None, pid="p"):
    """A beehiiv post object as the posts endpoint returns it (expand[]=stats)."""
    return {"id": pid, "publish_date": ts, "subject_line": subject, "title": title or subject,
            "stats": {"email": {"recipients": recipients, "unique_opens": opens}}}


# --- simple synthetic case 1: two plain editions, average worked by hand -------------------------
def test_average_of_two_plain_editions():
    rows = [post("2026-10-01", 300_000, 90_000, "Article one"),
            post("2026-10-08", 300_000, 70_000, "One Helpful Idea: two")]
    out = ne.average_unique_opens(rows, today=date(2026, 10, 20))
    assert out["campaigns_count"] == 2
    assert out["avg_unique_opens"] == 80_000           # (90,000 + 70,000) / 2
    assert out["since"] == "2026-07-23"                 # 90 days ending Oct 20, inclusive
    assert out["until"] == "2026-10-17"                 # the last 3 days are left out
    assert [e["date"] for e in out["editions"]] == ["2026-10-01", "2026-10-08"]


# --- simple synthetic case 2: a split test is ONE edition, a promo the same day is not merged ------
def test_split_test_sums_into_one_edition_and_promo_stays_out():
    rows = [post("2026-10-08", 164_000, 50_000, "[Variant A] Is what you've been taught about biases wrong?"),
            post("2026-10-08", 164_000, 30_000, "[Variant B] When cognitive biases aren't biases at all"),
            post("2026-10-08", 150_000, 60_000, "Limited spots for the rest of 2026",
                 title="Coaching spots for the rest of 2026")]
    out = ne.average_unique_opens(rows, today=date(2026, 10, 20))
    assert out["campaigns_count"] == 1
    assert out["editions"][0]["posts"] == 2
    assert out["editions"][0]["recipients"] == 328_000
    assert out["avg_unique_opens"] == 80_000           # 50,000 + 30,000, the coaching blast excluded


# --- every exclusion rule, one row each ---------------------------------------------------------
def test_exclusions_window_freshness_size_open_rate_and_promos():
    today = date(2026, 11, 13)
    rows = [
        post("2026-08-15", 300_000, 90_000, "Too old"),                                   # day before the window
        post("2026-08-16", 300_000, 90_000, "First day of the window"),                   # Nov 13 - 89 days, kept
        post("2026-11-10", 300_000, 90_000, "Last day old enough"),                       # kept
        post("2026-11-11", 300_000, 90_000, "One Helpful Idea: too fresh"),               # 2 days old
        post("2026-10-30", 252_000, 6_600, "The supplement paradox"),                     # re-send, 2.6% opens
        post("2026-10-19", 48_000, 8_700, "The supplement paradox"),                      # under 100k
        post("2026-11-07", 119_000, 47_000, "Diets, supplements and the AI bubble",
             title="Monthly Debrief - October"),                                           # debrief, by title
        post("2026-09-14", 232_000, 13_000, "Free tool: What's your type?"),               # promo, by subject
        post("2026-08-29", 106_000, 37_000, "Stuck with some projects? Check this.",
             title="Reconstellation Invitation"),                                          # promo, both
        post("2026-09-26", 78_000, 34_000, "You're invited to our upcoming workshop"),     # promo + small
        post("2026-08-27", 544, 374, "We're about to start!",
             title="Productivity Workshop - 10min Reminder"),                              # reminder
        post("2026-10-15", 4, 3, "[Real Test] The supplement paradox"),                   # test send
    ]
    out = ne.average_unique_opens(rows, today=today)
    assert [e["subject"] for e in out["editions"]] == ["First day of the window", "Last day old enough"]
    assert out["avg_unique_opens"] == 90_000


# --- grouping is by US Eastern day: a 6 pm + 8 pm ET split test straddles UTC midnight ----------
def test_post_rows_use_eastern_dates_so_an_evening_split_test_is_one_edition():
    posts = [api_post(1793916800, 324_457, 41_306, "How to think more complexly", pid="a"),   # 2026-11-05 22:00 UTC
             api_post(1793924960, 324_369, 96_000, "How to think more complexly", pid="b"),   # 2026-11-06 00:16 UTC
             {"id": "web-only", "publish_date": 1793924960, "subject_line": "no email stats", "stats": {}}]
    rows = ne.post_rows(posts)
    assert [r["date"] for r in rows] == ["2026-11-05", "2026-11-05"]
    eds = ne.group_editions(rows)
    assert len(eds) == 1 and eds[0]["posts"] == 2
    assert eds[0]["unique_opens"] == 137_306
    assert eds[0]["open_rate"] == pytest.approx(137_306 / 648_826)
    # the halves alone would be 12.7% and 29.6%: only the merged edition clears the 15% floor
    reg = ne.regular_editions(eds, min_recipients=100_000)
    assert len(reg) == 1


def test_promo_detection_by_subject_is_anchored_and_by_title_is_not():
    assert ne.is_promo("New Tool: Who attracts you?")
    assert ne.is_promo("Our most important ideas from July, in 2 minutes.")
    assert not ne.is_promo("Debunking meditation myths (and a new tool for meditation)")
    assert not ne.is_promo("One Helpful Idea: Dating App Incentives")
    assert ne.is_promo("Diets, supplements and the AI bubble", "Monthly Debrief - October")
    assert ne.is_promo("Free live workshop today", "Reminder (6h) - Thinking Clearly About Career Change")
    assert ne.is_promo("The supplement paradox", "[Igor Testing] The Supplement Paradox")
    assert not ne.is_promo("Should you steelman people you disagree with?", "Should you steelman people you disagree with?")


# --- realistic structure: a quarter shaped like the real list (two sends a week, promos, tests) ------
def test_realistic_quarter_hand_worked():
    today = date(2026, 11, 13)
    rows = []
    expected = []
    # 12 weeks: an OHI on Monday (350k, opens 70k + 1k*w) and an article on Thursday (330k, opens 85k + 1k*w)
    for w in range(12):
        mon = date(2026, 8, 17) + timedelta_days(7 * w)
        thu = mon + timedelta_days(3)
        rows.append(post(mon.isoformat(), 350_000, 70_000 + 1_000 * w, f"One Helpful Idea: week {w}"))
        rows.append(post(thu.isoformat(), 330_000, 85_000 + 1_000 * w, f"Article week {w}"))
        rows.append(post(thu.isoformat(), 5, 3, f"Article week {w}"))                     # test send
        expected += [70_000 + 1_000 * w, 85_000 + 1_000 * w]
    rows.append(post("2026-09-05", 130, 65, "Our most important ideas from August", title="Monthly Debrief - August"))
    rows.append(post("2026-09-12", 232_000, 13_000, "Free tool: What's your type?"))
    rows.append(post("2026-10-24", 72_000, 28_000, "Limited spots for the rest of 2026"))
    out = ne.average_unique_opens(rows, today=today)
    # the last pair (Nov 2 Mon, Nov 5 Thu) is old enough; nothing reaches Nov 11+
    assert out["campaigns_count"] == 24
    assert out["avg_unique_opens"] == round(sum(expected) / 24)     # = (70k+85k)/2 + 5.5k = 83,000
    assert out["avg_unique_opens"] == 83_000


def timedelta_days(n):
    from datetime import timedelta
    return timedelta(days=n)
