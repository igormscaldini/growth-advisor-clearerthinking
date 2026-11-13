"""Turn beehiiv sends into newsletter EDITIONS and pick the regular ones (One Helpful Idea + the main
article newsletter), the unit behind the "Average Unique Opens Per Campaign" goal and the sponsorship
price sheet. Pure functions, no I/O: tests/test_newsletter_editions.py works them with synthetic data.

Why editions and not posts: beehiiv stores one send as two or three posts when it is split by segment,
A/B variant or sending domain, so counting posts understates both recipients and unique opens. Sends on
the same US Eastern day are summed into one edition (CT sends in the US evening, so a UTC date would cut
a 6 pm + 8 pm split test in two). Test sends, workshop reminders, the Monthly Debrief, tool launches,
coaching and event promos are dropped per post first, by subject line or internal title.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SEND_TZ = ZoneInfo("America/New_York")

# Subject lines of Clearer Thinking's own promotions (tool launches, workshops, coaching, the monthly
# debrief, book launch asks, tests). Anchored at the start on purpose: "Debunking meditation myths (and a
# new tool for meditation)" is a regular article, "New Tool: Who attracts you?" is a launch blast.
PROMO = re.compile(
    r"^\s*(\[[^\]]*\]\s*)?(free tool|new tool|early access|you['’]re invited|our most important ideas|"
    r"limited spots|a personal ask|what['’]s next|stuck with|we['’]re about to start|free live workshop|"
    r"missed our workshop|details about your workshop|career change workshop|quick note|igor testing|"
    r"\[(real )?test\]|\[regular\]|\[no html\]|\[fixed\])",
    re.I,
)
# Internal post titles (never seen by readers, so the team names them plainly) of the same kinds of send.
# Unanchored: "Monthly Debrief - October", "Productivity Workshop - 10min Reminder", "Reconstellation
# Invitation", "Discover who attracts you - Re-launch", "Recording + FollowUp - ...", "[Igor Testing] ...".
PROMO_TITLE = re.compile(
    r"monthly debrief|reminder|invitation|inviting readers|testing|\[(real )?test\]|re-launch|launching|"
    r"early access|recording \+|follow ?up|everyone else|dating app - email|coaching spots|testing paywall",
    re.I,
)


def is_promo(subject: str, title: str = "") -> bool:
    return bool(PROMO.search(subject or "")) or bool(PROMO_TITLE.search(title or ""))


def post_rows(posts: list[dict], tz: ZoneInfo = SEND_TZ) -> list[dict]:
    """Flatten beehiiv post objects (expand[]=stats) into the rows group_editions wants: the send date in
    `tz` (YYYY-MM-DD), subject, title, recipients, unique_opens, id. Posts without email stats or a
    publish date (web-only, drafts) are skipped."""
    out = []
    for p in posts:
        em = (p.get("stats") or {}).get("email") or {}
        ts = p.get("publish_date")
        if not ts or not em:
            continue
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(tz)
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "subject": p.get("subject_line") or p.get("title") or "",
            "title": p.get("title") or "",
            "recipients": int(em.get("recipients") or 0),
            "unique_opens": int(em.get("unique_opens") or 0),
            "id": p.get("id"),
        })
    return out


def group_editions(posts: list[dict], min_post_recipients: int = 20_000) -> list[dict]:
    """Group same-day sends (segment splits, A/B variants, re-sends) into one edition.

    Test sends, workshop reminders and other posts under `min_post_recipients`, and our own promo blasts
    (is_promo on subject or title), are dropped per post first, so a small promo sent the same day cannot
    swallow a real edition. Each post needs date (YYYY-MM-DD), recipients, unique_opens and subject;
    title is optional.
    """
    by_day: dict[str, list[dict]] = defaultdict(list)
    for p in posts:
        if int(p.get("recipients") or 0) < min_post_recipients or is_promo(p.get("subject") or "", p.get("title") or ""):
            continue
        by_day[p["date"]].append(p)
    out = []
    for day, ps in sorted(by_day.items()):
        recipients = sum(int(p.get("recipients") or 0) for p in ps)
        opens = sum(int(p.get("unique_opens") or 0) for p in ps)
        subjects = sorted({(p.get("subject") or "").strip() for p in ps if (p.get("subject") or "").strip()})
        out.append({
            "date": day,
            "weekday": datetime.strptime(day, "%Y-%m-%d").strftime("%a"),
            "posts": len(ps),
            "recipients": recipients,
            "unique_opens": opens,
            "open_rate": (opens / recipients) if recipients else 0.0,
            "subject": " | ".join(subjects),
        })
    return out


def regular_editions(editions: list[dict], min_recipients: int = 200_000, min_open_rate: float = 0.15,
                     until: str | None = None, since: str | None = None) -> list[dict]:
    """The One Helpful Idea and main-article editions: sent to at least `min_recipients`, with a normal
    open rate (a re-send to dormant readers opens under 10%), not one of our own promos, and dated inside
    [since, until] (until = old enough for the opens to have accrued)."""
    out = []
    for e in editions:
        if until and e["date"] > until:
            continue
        if since and e["date"] < since:
            continue
        if e["recipients"] < min_recipients or e["open_rate"] < min_open_rate or is_promo(e["subject"]):
            continue
        out.append(e)
    return out


def average_unique_opens(rows: list[dict], today: date, window_days: int = 90, fresh_days: int = 3,
                         min_recipients: int = 100_000, min_open_rate: float = 0.15) -> dict:
    """The goal metric: mean unique opens per regular edition over the last `window_days`, leaving out the
    last `fresh_days` (opens still accruing). `rows` come from post_rows()."""
    since = (today - timedelta(days=window_days - 1)).isoformat()
    until = (today - timedelta(days=fresh_days)).isoformat()
    regular = regular_editions(group_editions(rows), min_recipients=min_recipients, min_open_rate=min_open_rate,
                               since=since, until=until)
    n = len(regular)
    return {
        "avg_unique_opens": round(sum(e["unique_opens"] for e in regular) / n) if n else 0,
        "campaigns_count": n,
        "window_days": window_days,
        "since": since,
        "until": until,
        "min_recipients": min_recipients,
        "min_open_rate": min_open_rate,
        "editions": [{k: e[k] for k in ("date", "posts", "recipients", "unique_opens", "subject")} for e in regular],
        "error": None,
    }
