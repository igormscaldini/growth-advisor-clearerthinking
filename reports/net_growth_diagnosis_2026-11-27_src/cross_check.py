"""Independent recount of the main numbers in datapoints.json, the simplest valid way, in separate code.

    .venv/bin/python reports/net_growth_diagnosis_2026-11-27_src/cross_check.py

analysis.py works on compacted records and pooled cells; this file goes back to the raw walk rows and
recounts with plain loops, then compares. It also checks the walk itself against beehiiv's own series:
- completeness: every id of the Nov 18 snapshot should come back, and the walk's subscribers per month
  should equal beehiiv's "subscribed" figure for that month;
- the exits of 2026 joiners in the window cannot exceed the whole list's unsubscribes on those days.
Writes cross_check_results.json and prints one line per check. Exit code 1 if any check fails.
"""
import importlib.util
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
OLD_DIR = ROOT / "reports" / "subscribers_by_month_2026-11-18_src"
UTC = timezone.utc

_spec = importlib.util.spec_from_file_location("subscribers_by_month_rules_xc", OLD_DIR / "analysis.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

ORGANIC_BUCKETS = {rules.TOOLS, rules.FORMS, rules.PODCAST, rules.RECOMMENDATIONS}
checks = []


def check(name, ours, theirs, tolerance=0.0, relative=False):
    gap = abs(ours - theirs)
    limit = tolerance * max(abs(theirs), 1) if relative else tolerance
    ok = gap <= limit
    checks.append({"check": name, "analysis": ours, "recount": theirs, "ok": ok})
    print(f"{'ok  ' if ok else 'FAIL'} {name}: analysis {ours:,} vs recount {theirs:,}")


def note(name, value):
    checks.append({"check": name, "value": value, "ok": True})
    print(f"info {name}: {value}")


def main():
    dp = json.loads((HERE / "datapoints.json").read_text())
    growth = json.loads((HERE / "growth.json").read_text())
    posts = json.loads((HERE / "posts.json").read_text())["posts"]
    meta = json.loads((HERE / "data" / "walk_meta.json").read_text())
    as_of = meta["as_of_ts"]

    old = {}
    old_newest = 0
    with (OLD_DIR / "data" / "subscriptions.jsonl").open() as f:
        for line in f:
            row = json.loads(line)
            old[row["id"]] = row["status"]
            old_newest = max(old_newest, row["created"])

    seen = set()
    per_month = Counter()
    exits_total, exits_organic, at_risk_total = 0, 0, 0
    young = [0, 0]    # [at risk, exits] for people subscribed under 30 days at the old snapshot
    settled = [0, 0]  # the same for 120+ days
    organic_mature = Counter()
    with (HERE / "data" / "subscriptions_now.jsonl").open() as f:
        for line in f:
            row = json.loads(line)
            seen.add(row["id"])
            status = row["status"]
            is_sub = status not in ("invalid", "pending")
            month = datetime.fromtimestamp(row["created"], tz=UTC).strftime("%Y-%m")
            if is_sub:
                per_month[month] += 1
            b = rules.bucket(row)
            if old.get(row["id"]) == "active":
                at_risk_total += 1
                left = status == "inactive"
                exits_total += left
                exits_organic += left and b in ORGANIC_BUCKETS
                tenure = (old_newest - row["created"]) / 86400
                if tenure < 30:
                    young[0] += 1
                    young[1] += left
                elif tenure >= 120:
                    settled[0] += 1
                    settled[1] += left
            # Reader yield, organic, 90+ days old, created after the tools wrote their list.
            if (is_sub and b in ORGANIC_BUCKETS and row["created"] >= rules.TOOLS_FROM.timestamp()
                    and (as_of - row["created"]) / 86400 >= 90):
                organic_mature["joined"] += 1
                if status == "active":
                    organic_mature["active"] += 1
                    received, opened = row["st"][1] or 0, row["st"][2] or 0
                    if received >= 4:
                        organic_mature["never" if opened == 0 else ("reader" if opened / received >= 0.3 else "occasional")] += 1

    # --- the walk against beehiiv ---
    missing = sum(1 for i in old if i not in seen)
    check("old snapshot ids missing from the new walk", dp["window"]["missing_from_new_walk"], missing)
    note("share of the old snapshot's ids found again", f"{100 * (1 - missing / len(old)):.3f}%")
    worst = 0.0
    for m in dp["list_movement"]:
        ours = per_month.get(m["month"], 0)
        gap = (ours - m["subscribed"]) / m["subscribed"]
        worst = max(worst, abs(gap))
        note(f"walk vs beehiiv subscribed, {m['month']}", f"{ours:,} vs {m['subscribed']:,} ({100 * gap:+.2f}%)")
    checks.append({"check": "walk within 2% of beehiiv's subscribed count every month", "value": round(worst, 4), "ok": worst <= 0.02})
    print(f"{'ok  ' if worst <= 0.02 else 'FAIL'} largest monthly gap between the walk and beehiiv: {100 * worst:.2f}%")

    # --- window exits ---
    check("window: people at risk", dp["window"]["at_risk"], at_risk_total)
    check("window: exits of 2026 joiners", dp["window"]["exits"], exits_total)
    check("window: exits, organic", dp["window_by_group"]["organic"]["exits"], exits_organic)
    nov = growth["unsubscribed_daily"]["2026-11"]
    whole_list_floor, whole_list_ceiling = sum(nov[18:26]), sum(nov[17:26])  # Nov 19-26, and with Nov 18
    ok = exits_total <= whole_list_ceiling * 1.15  # Nov 27 is not in the series yet
    checks.append({"check": "2026 joiners' exits do not exceed the whole list's unsubscribes in the window",
                   "value": [exits_total, whole_list_floor, whole_list_ceiling], "ok": ok})
    print(f"{'ok  ' if ok else 'FAIL'} window exits of 2026 joiners {exits_total:,} vs whole-list unsubscribes "
          f"{whole_list_floor:,} (Nov 19-26) to {whole_list_ceiling:,} (Nov 18-26)")

    # Simplest test of "new subscribers leave faster": two proportions, pooled z.
    p1, p2 = young[1] / young[0], settled[1] / settled[0]
    pooled = (young[1] + settled[1]) / (young[0] + settled[0])
    z = (p1 - p2) / math.sqrt(pooled * (1 - pooled) * (1 / young[0] + 1 / settled[0]))
    note("exit share in the window, subscribed under 30 days vs 120+ days",
         f"{100 * p1:.2f}% of {young[0]:,} vs {100 * p2:.2f}% of {settled[0]:,} (ratio {p1 / p2:.1f}, z = {z:.1f})")

    # --- sends ---
    by_month = Counter()
    for p in posts:
        by_month[datetime.fromtimestamp(p["publish_ts"], tz=UTC).strftime("%Y-%m")] += p["unsubscribes"]
    for row in dp["send_load"]:
        if row["month"] >= "2026-08":
            check(f"unsubscribes booked on sends, {row['month']}", row["send_unsubscribes"], by_month[row["month"]])
    # Simplest view of whole-list vs part-of-list emails: the median email of each kind, not the pooled rate.
    medians = {}
    for kind in ("whole_list", "segment"):
        picked = [s for s in dp["editions_since_oct"] if s["kind"] == kind and not s["promo"]]
        medians[kind] = {"emails": len(picked),
                         "median_unsubscribes": round(statistics.median(s["unsubscribes"] for s in picked)) if picked else None,
                         "median_per_1000": round(statistics.median(s["per_1000_recipients"] for s in picked), 2) if picked else None}
    note("editions since Oct 1, whole-list vs part of the list (medians)", medians)

    # --- reader yield ---
    ours = next(r for r in dp["reader_yield_by_group"] if r["key"] == "organic")
    check("organic sign-ups 90+ days old", ours["joined"], organic_mature["joined"])
    check("...still subscribed", ours["active"], organic_mature["active"])
    check("...readers per 100", ours["per_100"]["reader"], round(100 * organic_mature["reader"] / organic_mature["joined"], 1))
    check("...never opened per 100", ours["per_100"]["never_opened"], round(100 * organic_mature["never"] / organic_mature["joined"], 1))

    (HERE / "cross_check_results.json").write_text(json.dumps(checks, indent=1))
    failed = [c for c in checks if not c["ok"]]
    print(f"\n{len(checks) - len(failed)} of {len(checks)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
