"""Turn data/ (fresh beehiiv + GA4 pulls, see fetch_data.py) into datapoints.json for the
sponsor-facing audience report. The pure functions are unit-tested in
tests/test_sponsor_audience_report.py.

    .venv/bin/python reports/ct_sponsor_audience_report_2026-10-06_src/analysis.py

An "edition" is one newsletter as the reader experiences it: beehiiv often stores it as
2-3 posts (sender-domain splits, segment splits, a test send), so posts with the same
subject line within three days are merged before anything is counted.
"""
from __future__ import annotations

import json
import re
import statistics as st
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "datapoints.json"

FULL_LIST = 150_000  # an edition sent to at least this many addresses is a full-list send
WINDOW_START = date(2026, 7, 1)
YEAR_START = date(2026, 1, 1)
PROMO = re.compile(r"^(new tool|free tool|what's next|early access)", re.I)
ANGLOSPHERE = {"United States", "United Kingdom", "Canada", "Australia", "Ireland", "New Zealand"}
# Editions in which a sponsor's link ran, matched on the edition date and the link URL.
SPONSOR_PLACEMENTS = [
    {"date": "2026-04-17", "match": "80000hours.org/clearerthinking", "sponsor": "80,000 Hours",
     "format": "Sponsor spot inside a regular edition"},
    {"date": "2026-05-28", "match": "80000hours.org", "sponsor": "80,000 Hours",
     "format": "Dedicated edition: an extract from the sponsor's career guide"},
    {"date": "2026-07-01", "match": "80000hours.org/clearerthinking", "sponsor": "80,000 Hours",
     "format": "Sponsor spot inside a regular edition"},
    {"date": "2026-09-24", "match": "kickstarter.com/projects/schoolofthought/game-over",
     "sponsor": "Game Over (The School of Thought)", "format": "Sponsor spot inside a regular edition"},
]


# --------------------------------------------------------------------------- editions
def post_date(p: dict) -> date:
    return datetime.fromtimestamp(p["publish_date"], timezone.utc).date()


def norm_subject(s: str | None) -> str:
    """Subject line with any leading "[Regular]"-style tag removed, lower-cased, spaces collapsed."""
    s = re.sub(r"^\[[^\]]*\]\s*", "", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def classify(subject: str | None) -> str:
    """'ohi' (One Helpful Idea), 'promo' (a tool or product announcement) or 'main'."""
    s = norm_subject(subject)
    if s.startswith("one helpful idea"):
        return "ohi"
    if PROMO.match(s):
        return "promo"
    return "main"


def group_editions(posts: list[dict]) -> list[dict]:
    """Merge posts with the same subject line within three days into one edition.

    posts must be sorted by publish_date. Email stats are summed across the merged posts;
    links are concatenated so sponsor clicks can be counted per edition.
    """
    editions: list[dict] = []
    for p in posts:
        key = norm_subject(p.get("subject_line") or p.get("title"))
        d = post_date(p)
        target = next((e for e in reversed(editions) if e["key"] == key and (d - e["date"]).days <= 3), None)
        if target is None:
            target = {"key": key, "date": d, "subject": p.get("subject_line") or p.get("title") or "",
                      "kind": classify(p.get("subject_line") or p.get("title")), "posts": 0, "senders": [],
                      "recipients": 0, "unique_opens": 0, "unique_verified_clicks": 0, "links": []}
            editions.append(target)
        em = p.get("email") or {}
        target["posts"] += 1
        if p.get("from_address") and p["from_address"] not in target["senders"]:
            target["senders"].append(p["from_address"])
        target["recipients"] += int(em.get("recipients") or 0)
        target["unique_opens"] += int(em.get("unique_opens") or 0)
        target["unique_verified_clicks"] += int(em.get("unique_verified_clicks") or 0)
        target["links"] += p.get("links") or []
    return editions


def edition_row(e: dict) -> dict:
    """The per-edition record written to datapoints.json (no link list, ISO date)."""
    return {"date": e["date"].isoformat(), "subject": e["subject"], "kind": e["kind"], "posts": e["posts"],
            "senders": e["senders"], "recipients": e["recipients"], "unique_opens": e["unique_opens"],
            "open_rate": e["unique_opens"] / e["recipients"] if e["recipients"] else 0.0,
            "unique_verified_clicks": e["unique_verified_clicks"]}


# --------------------------------------------------------------------------- summaries
def summarize(eds: list[dict]) -> dict:
    """Median / mean / range of unique opens plus median recipients, open rate and verified clicks."""
    if not eds:
        return {"n": 0}
    uo = [e["unique_opens"] for e in eds]
    rates = [e["unique_opens"] / e["recipients"] for e in eds if e["recipients"]]
    cto = [e["unique_verified_clicks"] / e["unique_opens"] for e in eds if e["unique_opens"]]
    return {
        "n": len(eds),
        "median_unique_opens": round(st.median(uo)),
        "mean_unique_opens": round(st.mean(uo)),
        "min_unique_opens": min(uo),
        "max_unique_opens": max(uo),
        "median_recipients": round(st.median(e["recipients"] for e in eds)),
        "median_open_rate": st.median(rates) if rates else 0.0,
        "median_verified_clicks": round(st.median(e["unique_verified_clicks"] for e in eds)),
        "median_click_to_open": st.median(cto) if cto else 0.0,
    }


def sponsor_results(editions: list[dict], placements: list[dict] = SPONSOR_PLACEMENTS) -> list[dict]:
    """Unique clicks on the sponsor's links in each placement edition, and clicks per 1,000 unique opens.

    beehiiv reports unique clicks PER LINK, so an edition with several sponsor links sums them and a
    reader who clicked two links counts twice; `links` says how many links were summed.
    """
    out = []
    for pl in placements:
        d = date.fromisoformat(pl["date"])
        ed = next((e for e in editions if e["date"] == d), None)
        if ed is None:
            continue
        links = [l for l in ed["links"] if pl["match"] in (l.get("url") or "")]
        clicks = sum(int(l.get("unique_clicks") or 0) for l in links)
        out.append({**pl, "subject": ed["subject"], "recipients": ed["recipients"], "unique_opens": ed["unique_opens"],
                    "links": len(links), "unique_clicks": clicks,
                    "clicks_per_1000_opens": clicks / ed["unique_opens"] * 1000 if ed["unique_opens"] else 0.0})
    return out


def country_shares(ga4: dict, top: int = 10) -> dict:
    tot = ga4["total_sessions"] or 1
    rows = [{"country": r["country"], "sessions": r["sessions"], "share": r["sessions"] / tot} for r in ga4["rows"][:top]]
    anglo = sum(r["sessions"] for r in ga4["rows"] if r["country"] in ANGLOSPHERE) / tot
    return {"window_days": ga4["window_days"], "pulled": ga4["pulled"], "total_sessions": ga4["total_sessions"],
            "rows": rows, "anglosphere_share": anglo, "anglosphere": sorted(ANGLOSPHERE)}


# --------------------------------------------------------------------------- main
def build(posts: list[dict], engaged: dict, ga4: dict, pulled: str, today: date) -> dict:
    editions = group_editions(sorted(posts, key=lambda p: p.get("publish_date") or 0))
    full = [e for e in editions if e["recipients"] >= FULL_LIST]
    recent = [e for e in full if e["date"] >= WINDOW_START]
    ytd = [e for e in full if e["date"] >= YEAR_START]
    regular = lambda eds: [e for e in eds if e["kind"] in ("main", "ohi")]  # noqa: E731
    weeks = (today - WINDOW_START).days / 7
    return {
        "pulled": pulled,
        "full_list_threshold": FULL_LIST,
        "window": {"start": WINDOW_START.isoformat(), "end": today.isoformat(), "weeks": round(weeks, 1)},
        "editions_recent": [edition_row(e) for e in recent],
        "stats_recent": {"regular": summarize(regular(recent)),
                         "main": summarize([e for e in recent if e["kind"] == "main"]),
                         "ohi": summarize([e for e in recent if e["kind"] == "ohi"]),
                         "promo": summarize([e for e in recent if e["kind"] == "promo"])},
        "stats_ytd": {"regular": summarize(regular(ytd))},
        "regular_editions_per_week": round(len(regular(recent)) / weeks, 2) if weeks else 0,
        "sponsor_results": sponsor_results(editions),
        "engaged": {"count": engaged.get("engaged"), "segment": engaged.get("segment_name"),
                    "calculated": datetime.fromtimestamp(engaged["last_calculated"], timezone.utc).date().isoformat()
                    if engaged.get("last_calculated") else None},
        "country": country_shares(ga4),
    }


def main() -> None:
    P = json.load(open(DATA / "posts.json"))
    engaged = json.load(open(DATA / "engaged.json"))
    ga4 = json.load(open(DATA / "ga4_country.json"))
    dp = build(P["posts"], engaged, ga4, P["pulled"], date.today())
    OUT.write_text(json.dumps(dp, indent=1))
    s = dp["stats_recent"]
    print(f"regular editions since {dp['window']['start']}: {s['regular']['n']} "
          f"(main {s['main']['n']}, OHI {s['ohi']['n']}, promos {s['promo']['n']}); "
          f"median unique opens {s['regular']['median_unique_opens']:,} "
          f"(range {s['regular']['min_unique_opens']:,} to {s['regular']['max_unique_opens']:,})")
    for r in dp["sponsor_results"]:
        print(f"  {r['date']} {r['sponsor']}: {r['unique_clicks']} clicks / {r['unique_opens']:,} opens "
              f"= {r['clicks_per_1000_opens']:.1f} per 1,000 ({r['links']} links)")
    print(f"engaged {dp['engaged']['count']:,} (calc {dp['engaged']['calculated']}); "
          f"anglosphere {dp['country']['anglosphere_share']:.1%} of {dp['country']['total_sessions']:,} sessions")


if __name__ == "__main__":
    main()
