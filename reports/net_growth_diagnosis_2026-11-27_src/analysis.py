"""Why the newsletter's net subscriber growth goes negative: the exits and the inflow, measured.

    .venv/bin/python reports/net_growth_diagnosis_2026-11-27_src/analysis.py

Reads (all next to this file unless noted) and writes datapoints.json:
- data/subscriptions_now.jsonl   every 2026 subscription with its engagement stats (fetch_subscriptions.py)
- the Nov 18 snapshot of the same people (reports/subscribers_by_month_2026-11-18_src/data/subscriptions.jsonl)
- posts.json                     every email sent since Jul 2025 with its unsubscribes (fetch_posts.py)
- growth.json                    beehiiv's own daily subscribed / unsubscribed series
- funnel.json                    GA4 tool funnel and Search Console clicks by month (fetch_funnel.py)
- automation_stats.json          the welcome sequence's per-email numbers (beehiiv connector)

Where a subscriber came from is decided by ONE set of rules, the `bucket` function of the Nov 18 report
(reports/subscribers_by_month_2026-11-18_src/analysis.py), imported here as `rules`. This file only folds
its ten buckets into four groups and adds the measurements that report did not have.

Definitions used throughout
- A subscriber = a record whose status is not "invalid" or "pending" (the Nov 18 rule).
- Left = status "inactive" (unsubscribed by any route: a click, the preferences page, an automation).
- Emails received = beehiiv's `total_received` for that person (newsletters and automation emails).
- Reader = at least MIN_RECEIVED emails received and at least READER_OPEN_RATE of them opened.
  Apple Mail opens every email by itself, so "reader" overstates real reading; "never opened" does not.
- Window = the days between the two snapshots. A window exit is someone active in the first snapshot
  and inactive in the second, so it measures who is leaving NOW, by how long they had been subscribed.
"""
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
OLD_DIR = ROOT / "reports" / "subscribers_by_month_2026-11-18_src"
NOW_FILE = HERE / "data" / "subscriptions_now.jsonl"
OLD_FILE = OLD_DIR / "data" / "subscriptions.jsonl"
WALK_META = HERE / "data" / "walk_meta.json"
OUT = HERE / "datapoints.json"
UTC = timezone.utc

sys.path.insert(0, str(ROOT))
import newsletter_editions as editions  # noqa: E402

_spec = importlib.util.spec_from_file_location("subscribers_by_month_rules", OLD_DIR / "analysis.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

STUDY, ADS, ORGANIC, BATCHES = "study", "ads", "organic", "batches"
GROUP_OF_BUCKET = {
    rules.STUDY: STUDY,
    rules.ADS: ADS, rules.PARTNER_ADS: ADS,
    rules.TOOLS: ORGANIC, rules.FORMS: ORGANIC, rules.PODCAST: ORGANIC, rules.RECOMMENDATIONS: ORGANIC,
    rules.LEAF: BATCHES, rules.UPLOADS: BATCHES, rules.BACKLOG: BATCHES,
}
GROUP_LABELS = {STUDY: "Who Attracts You study", ADS: "Ads", ORGANIC: "Organic (tools, forms, podcast)",
                BATCHES: "Bulk uploads (Leaf and others)"}

MIN_RECEIVED = 4          # fewer emails than this says nothing about whether someone reads
READER_OPEN_RATE = 0.30
RECEIVED_BINS = ((0, 0, "0"), (1, 1, "1"), (2, 3, "2-3"), (4, 6, "4-6"), (7, 12, "7-12"),
                 (13, 24, "13-24"), (25, 10**9, "25+"))
TENURE_BANDS = ((0, 13, "under 2 weeks"), (14, 29, "2-4 weeks"), (30, 59, "1-2 months"),
                (60, 119, "2-4 months"), (120, 239, "4-8 months"), (240, 10**9, "8+ months"))
MATURE_DAYS = 90          # cohorts at least this old have had time to show their early exits
WHOLE_LIST_SHARE = 0.85   # a send reaching this share of the active list counts as whole-list
MIN_SEND = 20_000         # smaller sends (tests, workshop reminders) are left out of send rates
OPEN_BANDS = ((0.0, 0.10, "under 10%"), (0.10, 0.20, "10-20%"), (0.20, 0.30, "20-30%"), (0.30, 9.9, "30%+"))
FUNNEL_STEPS = ("Viewed Privacy Policy", "Accepted Privacy Policy", "Reached Email Ask", "Submitted Email")


# ---------- one record ----------

def compact(row: dict) -> dict:
    """A raw walk row reduced to what the measurements need. `tool` is the tool that created the
    subscriber when the record can tell (created after the tools began writing their list)."""
    sent, received, opened, clicked = (row.get("st") or [0, 0, 0, 0])[:4]
    tools = rules.tools_tried(row)
    knows_tool = rules.created(row) >= rules.TOOLS_FROM and bool(tools)
    return {"id": row["id"], "status": row.get("status"), "created": row["created"],
            "group": GROUP_OF_BUCKET[rules.bucket(row)], "tool": tools[0] if knows_tool else None,
            "received": received or 0, "opened": opened or 0}


def is_subscriber(rec: dict) -> bool:
    return rec["status"] not in rules.NOT_SUBSCRIBERS


def month_of(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m")


def band(value, bands) -> str:
    for low, high, label in bands:
        if low <= value <= high:
            return label
    raise ValueError(f"{value} fits no band")


def open_band(rate: float) -> str:
    for low, high, label in OPEN_BANDS:
        if low <= rate < high:
            return label
    raise ValueError(f"{rate} fits no band")


def reading(rec: dict) -> str:
    """never_opened / occasional / reader, or too_new with fewer than MIN_RECEIVED emails."""
    if rec["received"] < MIN_RECEIVED:
        return "too_new"
    if rec["opened"] == 0:
        return "never_opened"
    return "reader" if rec["opened"] / rec["received"] >= READER_OPEN_RATE else "occasional"


# ---------- the months ----------

def list_movement(subscribed_daily: dict, unsubscribed_daily: dict) -> list:
    """Per month: days covered, subscribed, unsubscribed and the net change, from beehiiv's daily series."""
    out = []
    for month in sorted(subscribed_daily):
        s, u = sum(subscribed_daily[month]), sum(unsubscribed_daily[month])
        out.append({"month": month, "days": len(subscribed_daily[month]), "subscribed": s,
                    "unsubscribed": u, "net": s - u})
    return out


def joined_by_month(recs) -> dict:
    """{month: {group: subscribers created that month}}."""
    out = defaultdict(Counter)
    for r in recs:
        if is_subscriber(r):
            out[month_of(r["created"])][r["group"]] += 1
    return {m: dict(c) for m, c in sorted(out.items())}


# ---------- what the sends cost ----------

def post_month(post: dict) -> str:
    return month_of(post["publish_ts"])


def monthly_send_load(posts: list, unsubscribed_by_month: dict) -> list:
    """Per month: emails delivered (sum of recipients over every send), the unsubscribes beehiiv books
    on those sends, that as a rate per 1,000 emails, the whole list's unsubscribes that month and the
    part of them no send accounts for (automations, the preferences page, late clicks on older sends)."""
    agg = defaultdict(lambda: {"sends": 0, "emails": 0, "send_unsubscribes": 0, "unique_opens": 0, "spam": 0})
    for p in posts:
        a = agg[post_month(p)]
        a["sends"] += p["recipients"] >= MIN_SEND
        a["emails"] += p["recipients"]
        a["send_unsubscribes"] += p["unsubscribes"]
        a["unique_opens"] += p["unique_opens"]
        a["spam"] += p["spam_reports"]
    out = []
    for month in sorted(agg):
        a = dict(agg[month])
        total = unsubscribed_by_month.get(month)
        a.update({"month": month,
                  "per_1000_emails": round(1000 * a["send_unsubscribes"] / a["emails"], 2) if a["emails"] else None,
                  "all_unsubscribes": total,
                  "outside_sends": total - a["send_unsubscribes"] if total is not None else None})
        out.append(a)
    return out


def send_kind(post: dict, list_size: int) -> str:
    """whole_list (reaches WHOLE_LIST_SHARE of the active list), segment, or small (under MIN_SEND)."""
    if post["recipients"] < MIN_SEND:
        return "small"
    return "whole_list" if post["recipients"] >= WHOLE_LIST_SHARE * list_size else "segment"


def send_rates(posts: list, key) -> list:
    """Sends of MIN_SEND+ recipients grouped by `key(post)`: how many, recipients, unsubscribes, and the
    unsubscribe rate per 1,000 recipients and per 1,000 unique opens (pooled, not an average of rates)."""
    agg = defaultdict(lambda: {"sends": 0, "recipients": 0, "unique_opens": 0, "unsubscribes": 0, "spam": 0})
    for p in posts:
        if p["recipients"] < MIN_SEND:
            continue
        a = agg[key(p)]
        a["sends"] += 1
        a["recipients"] += p["recipients"]
        a["unique_opens"] += p["unique_opens"]
        a["unsubscribes"] += p["unsubscribes"]
        a["spam"] += p["spam_reports"]
    out = []
    for k, a in agg.items():
        out.append({"key": k, **a,
                    "open_rate": round(a["unique_opens"] / a["recipients"], 4),
                    "per_1000_recipients": round(1000 * a["unsubscribes"] / a["recipients"], 2),
                    "per_1000_opens": round(1000 * a["unsubscribes"] / a["unique_opens"], 2) if a["unique_opens"] else None,
                    "unsubscribes_per_send": round(a["unsubscribes"] / a["sends"])})
    return sorted(out, key=lambda r: str(r["key"]))


# ---------- who leaves ----------

def retention(recs, key) -> list:
    """Per `key(rec)`: subscribers who joined, how many are still active and how many left."""
    agg = defaultdict(lambda: {"joined": 0, "active": 0, "left": 0})
    for r in recs:
        if not is_subscriber(r):
            continue
        a = agg[key(r)]
        a["joined"] += 1
        a["active"] += r["status"] == "active"
        a["left"] += r["status"] == "inactive"
    return [{"key": k, **a, "left_share": round(a["left"] / a["joined"], 4)}
            for k, a in sorted(agg.items(), key=lambda kv: str(kv[0]))]


def exits_by_emails_received(recs) -> dict:
    """Per group, the people who left, binned by how many emails they had received when they left, with
    how many of them never opened one. `joined` is every subscriber of that group in `recs`."""
    out = {}
    for group in (STUDY, ADS, ORGANIC, BATCHES):
        members = [r for r in recs if r["group"] == group and is_subscriber(r)]
        leavers = [r for r in members if r["status"] == "inactive"]
        bins = Counter(band(r["received"], RECEIVED_BINS) for r in leavers)
        out[group] = {"joined": len(members), "left": len(leavers),
                      "bins": [{"emails": label, "left": bins.get(label, 0)} for _, _, label in RECEIVED_BINS],
                      "left_never_opened": sum(1 for r in leavers if r["opened"] == 0)}
    return out


def window_exits(old_status: dict, recs, old_asof_ts: int, window_days: float) -> dict:
    """Who left between the two snapshots, by group and by how long they had been subscribed.

    At risk = active in the old snapshot. Exit = inactive in the new one. `rate_30d` is exits per 100 at
    risk, scaled to 30 days. Also counts people who turned invalid (bounces) and old ids the new walk
    did not return (deleted, or a walk gap)."""
    cells = defaultdict(lambda: {"at_risk": 0, "exits": 0})
    turned_invalid, seen = 0, set()
    for r in recs:
        seen.add(r["id"])
        if old_status.get(r["id"]) != "active":
            continue
        tenure = (old_asof_ts - r["created"]) / 86400
        c = cells[(r["group"], band(int(max(tenure, 0)), TENURE_BANDS))]
        c["at_risk"] += 1
        c["exits"] += r["status"] == "inactive"
        turned_invalid += r["status"] in rules.NOT_SUBSCRIBERS
    rows = []
    for (group, tenure), c in cells.items():
        rows.append({"group": group, "tenure": tenure, **c,
                     "rate_30d": round(100 * c["exits"] / c["at_risk"] * 30 / window_days, 2)})
    order = {label: i for i, (_, _, label) in enumerate(TENURE_BANDS)}
    rows.sort(key=lambda r: (r["group"], order[r["tenure"]]))
    return {"window_days": round(window_days, 2), "cells": rows,
            "at_risk": sum(c["at_risk"] for c in cells.values()),
            "exits": sum(c["exits"] for c in cells.values()),
            "turned_invalid": turned_invalid,
            "missing_from_new_walk": sum(1 for i in old_status if i not in seen)}


def pooled_rate(cells: list, window_days: float, **match) -> dict:
    """Exits per 100 at risk per 30 days over the cells matching every key in `match`."""
    picked = [c for c in cells if all(c[k] == v for k, v in match.items())]
    at_risk, exits = sum(c["at_risk"] for c in picked), sum(c["exits"] for c in picked)
    return {"at_risk": at_risk, "exits": exits,
            "rate_30d": round(100 * exits / at_risk * 30 / window_days, 2) if at_risk else None}


# ---------- what the ones who stay are worth ----------

def reader_yield(recs, key, as_of_ts: int, min_age_days: int = MATURE_DAYS) -> list:
    """For sign-ups at least `min_age_days` old, per `key(rec)`: of every 100 who joined, how many are
    still subscribed and how many are readers / occasional / never opened an email."""
    agg = defaultdict(Counter)
    for r in recs:
        if not is_subscriber(r) or (as_of_ts - r["created"]) / 86400 < min_age_days:
            continue
        a = agg[key(r)]
        a["joined"] += 1
        if r["status"] == "active":
            a["active"] += 1
            a[reading(r)] += 1
    out = []
    for k, a in agg.items():
        j = a["joined"]
        out.append({"key": k, "joined": j, "active": a["active"],
                    "per_100": {s: round(100 * a[s] / j, 1) for s in ("active", "reader", "occasional", "never_opened", "too_new")}})
    return sorted(out, key=lambda r: -r["joined"])


# ---------- the arithmetic of a leaky list ----------

def breakeven_inflow(list_size: float, monthly_exit_rate: float) -> float:
    """New subscribers needed each month just to stay level."""
    return list_size * monthly_exit_rate


def equilibrium_list(monthly_inflow: float, monthly_exit_rate: float) -> float:
    """The list size at which a steady inflow equals the exits: inflow / exit rate."""
    return monthly_inflow / monthly_exit_rate


def project(list_size: float, monthly_inflow: float, monthly_exit_rate: float, months: int) -> list:
    """List size at the end of each of the next `months` months with a steady inflow and exit rate."""
    out = []
    for _ in range(months):
        list_size = list_size * (1 - monthly_exit_rate) + monthly_inflow
        out.append(round(list_size))
    return out


# ---------- the inflow ----------

def normalise_page(path: str) -> str:
    """One spelling per tool page: no query string, no trailing slash, no .html."""
    path = path.split("?")[0].rstrip("/")
    return path[:-5] if path.endswith(".html") else (path or "/")


def funnel_by_month(ga4: dict, paid: bool = False, page: str = None) -> list:
    """Per month, the four funnel steps for paid or non-paid sessions (optionally one tool page), with
    the share of starters who reach the email ask and the share of those who submit."""
    out = []
    for month in sorted(ga4):
        steps = Counter()
        for r in ga4[month]:
            if r["paid"] == paid and (page is None or normalise_page(r["page"]) == page):
                steps[r["event"]] += r["count"]
        starts, reached, submitted = (steps[s] for s in FUNNEL_STEPS[1:])
        out.append({"month": month, "landed": steps[FUNNEL_STEPS[0]], "started": starts, "reached_ask": reached,
                    "submitted": submitted,
                    "start_to_ask": round(reached / starts, 3) if starts else None,
                    "ask_to_submit": round(submitted / reached, 3) if reached else None})
    return out


def search_clicks_by_month(gsc: dict, page: str = None, exclude: tuple = ()) -> dict:
    """Google clicks to the tools host per month; with `page`, to that tool only (top-25 pages a month);
    `exclude` removes pages (e.g. the study) from the host total."""
    out = {}
    for month in sorted(gsc):
        pages = Counter()
        for r in gsc[month]["tool_pages"]:
            pages[normalise_page(r["page"].split("programs.clearerthinking.org")[-1])] += r["clicks"]
        if page is not None:
            out[month] = pages.get(page, 0)
        else:
            out[month] = gsc[month]["tools_clicks"] - sum(pages.get(p, 0) for p in exclude)
    return out


# ---------- run ----------

def load_now() -> list:
    with NOW_FILE.open() as f:
        return [compact(json.loads(line)) for line in f]


def load_old_status() -> tuple:
    status, newest = {}, 0
    with OLD_FILE.open() as f:
        for line in f:
            row = json.loads(line)
            status[row["id"]] = row["status"]
            newest = max(newest, row["created"])
    return status, newest


def main():
    growth = json.loads((HERE / "growth.json").read_text())
    posts = json.loads((HERE / "posts.json").read_text())["posts"]
    funnel = json.loads((HERE / "funnel.json").read_text())
    meta = json.loads(WALK_META.read_text())
    old_dp = json.loads((OLD_DIR / "datapoints.json").read_text())
    auto_file = HERE / "automation_stats.json"
    automation = json.loads(auto_file.read_text()) if auto_file.exists() else None

    recs = load_now()
    old_status, old_newest = load_old_status()
    as_of = meta["as_of_ts"]
    # The Nov 18 walk ran newest-first for about 50 minutes; its newest record marks when it started.
    old_asof = old_newest
    window_days = (as_of - old_asof) / 86400

    movement = list_movement(growth["subscribed_daily"], growth["unsubscribed_daily"])
    unsub_by_month = {m["month"]: m["unsubscribed"] for m in movement}
    unsub_by_month.update({m: v[1] for m, v in growth["monthly_2025"].items()})

    # List size at the start of each month, to tell a whole-list send from a segment.
    start_size = {m["month"]: m["active_at_start"] for m in old_dp["list_movement"]}
    start_size.setdefault("2026-11", old_dp["list_movement"][-1]["active_at_start"])
    posts_2026 = [p for p in posts if post_month(p) >= "2026-01"]
    recent = [p for p in posts if post_month(p) >= "2026-08"]

    def kind(p):
        return send_kind(p, start_size[post_month(p)])

    def promo(p):
        return "promo" if editions.is_promo(p["subject"], p["title"]) else "edition"

    mature = [r for r in recs if (as_of - r["created"]) / 86400 >= MATURE_DAYS]
    tagged = [r for r in recs if r["created"] >= rules.TOOLS_FROM.timestamp()]
    window = window_exits(old_status, recs, old_asof, window_days)
    cells = window["cells"]
    joined = joined_by_month(recs)

    dp = {
        "as_of": datetime.fromtimestamp(as_of, tz=UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "old_as_of": datetime.fromtimestamp(old_asof, tz=UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "records": len(recs),
        "active_now": growth["active_now"],
        "group_labels": GROUP_LABELS,
        "list_movement": movement,
        "monthly_2025": growth["monthly_2025"],
        "steady_flow_to_oct": [m for m in old_dp["steady_flow"] if m["month"] < "2026-11"],
        "joined_by_month": joined,
        "send_load": monthly_send_load(posts, unsub_by_month),
        "send_rates_by_kind_2026": send_rates(posts_2026, kind),
        "send_rates_by_kind_since_aug": send_rates(recent, kind),
        "send_rates_by_promo_since_aug": send_rates(recent, promo),
        "send_rates_by_open_band_since_aug": send_rates(recent, lambda p: open_band(p["unique_opens"] / p["recipients"])),
        "biggest_sends_since_oct": sorted(
            ({"date": datetime.fromtimestamp(p["publish_ts"], tz=UTC).strftime("%Y-%m-%d"), "subject": p["subject"],
              "recipients": p["recipients"], "unique_opens": p["unique_opens"], "unsubscribes": p["unsubscribes"],
              "spam": p["spam_reports"], "kind": kind(p), "promo": promo(p)}
             for p in posts if post_month(p) >= "2026-10" and p["recipients"] >= MIN_SEND),
            key=lambda r: r["date"]),
        "retention_by_month_group": retention(recs, lambda r: (month_of(r["created"]), r["group"])),
        "exits_by_emails_received_mature": exits_by_emails_received(mature),
        "window": window,
        "window_by_group": {g: pooled_rate(cells, window_days, group=g) for g in GROUP_LABELS},
        "window_by_tenure": {label: pooled_rate(cells, window_days, tenure=label) for _, _, label in TENURE_BANDS},
        "reader_yield_by_group": reader_yield(tagged, lambda r: r["group"], as_of),
        "reader_yield_by_tool": [r for r in reader_yield(
            [r for r in tagged if r["group"] == ORGANIC and r["tool"]], lambda r: r["tool"], as_of)
            if r["joined"] >= 300],
        "funnel_not_paid": funnel_by_month(funnel["ga4"], paid=False),
        "funnel_upt_not_paid": funnel_by_month(funnel["ga4"], paid=False, page="/personality-test"),
        "search_clicks_tools_without_study": search_clicks_by_month(funnel["gsc"], exclude=("/who_attracts_you_study",)),
        "search_clicks_upt": search_clicks_by_month(funnel["gsc"], page="/personality-test"),
        "automation": automation,
    }
    OUT.write_text(json.dumps(dp, indent=1))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
