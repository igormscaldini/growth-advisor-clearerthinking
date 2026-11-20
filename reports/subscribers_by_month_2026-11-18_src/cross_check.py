"""Independent checks of analysis.py. Shares no code with it.

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/cross_check.py

1. Recount: the simplest valid way to get the same table. pandas, a handful of boolean columns and two
   regular expressions on the raw strings ("does the tools list START with the study?", "does the media
   list START with an ad medium?"), then subscribers minus removed per month. Must equal the record-level
   count in datapoints.json exactly (the GA4-based estimate for Jan-Mar is not part of the recount).
2. Completeness of the walk: subscribers per day against beehiiv's own growth series (beehiiv_growth.json,
   from its connector) and, for non-imports, against the dashboard's incremental cache.
3. Shape: tool sign-ups kept per month against GA4 "Submitted Email" events outside cpc sessions and off
   the study page, and the ad buckets against GA4 events in cpc sessions (cross_checks.json). Events are
   not subscribers, so only the stability of the ratios is informative.
4. Unsubscribes: beehiiv's weekly list size against its own daily new-subscriber and unsubscribe figures.
   Week by week, the change in list size must equal subscribed minus unsubscribed; a week that does not
   reconcile means a mistyped figure or a movement beehiiv reports nowhere. Also recomputes the monthly
   unsubscribe totals with pandas and compares them with datapoints.json.

Writes cross_check_results.json and exits non-zero if the recount disagrees.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent.parent

STUDY_FIRST = r"^[\s|]*who attracts you\s*(?:\||$)"
AD_FIRST = r"^[\s,]*(?:cpc|paid_social)\s*(?:,|$)"
END = pd.Timestamp("2026-11-18", tz="UTC")
BACKLOG_UNTIL = pd.Timestamp("2026-01-01 02:00", tz="UTC")
MEDIA_FROM = pd.Timestamp("2026-03-27 15:00", tz="UTC")
TOOLS_FROM = pd.Timestamp("2026-03-31 10:00", tz="UTC")
NOT_SUBSCRIBERS = ["invalid", "pending"]
WEEK_TOLERANCE = 10  # subscribers; beehiiv's history drifts by a handful as people resubscribe


def load() -> pd.DataFrame:
    recs = []
    with (HERE / "data" / "subscriptions.jsonl").open() as f:
        for line in f:
            r = json.loads(line)
            cf = r.get("cf") or {}
            recs.append({
                "created": r["created"],
                "status": r.get("status"),
                "channel": (r.get("utm_channel") or "").lower(),
                "native_medium": (r.get("utm_medium") or "").strip().lower(),
                "tools": cf.get("Tools Tried (Pipe-Separated)") or "",
                "old_tools": bool(cf.get("Tools Tried (DEPRECATED)")),
                "media": cf.get("UTM Media (Comma-Separated)") or "",
                "dating": bool(cf.get("Dating App Updates")),
                "mla": bool(cf.get("MLA Tags (Comma-Separated)")),
                "leaf": bool(cf.get("Leaf")),
            })
    df = pd.DataFrame(recs)
    df["when"] = pd.to_datetime(df["created"], unit="s", utc=True)
    df = df[df["when"] < END].copy()
    df["month"] = df["when"].dt.strftime("%Y-%m")
    df["day"] = df["when"].dt.strftime("%Y-%m-%d")
    return df


def recount(df: pd.DataFrame) -> pd.DataFrame:
    df = df[~df["status"].isin(NOT_SUBSCRIBERS)]  # beehiiv counts neither as subscribers
    no_tool = df["tools"].str.replace(r"[\s|]|\(none\)", "", regex=True, case=False) == ""
    backlog = (df["channel"] == "import") & (df["when"] < BACKLOG_UNTIL)
    study = (df["when"] >= TOOLS_FROM) & (
        df["tools"].str.contains(STUDY_FIRST, case=False, regex=True) | (no_tool & df["dating"]))
    ads = df["native_medium"].isin(["cpc", "paid_social"]) | (
        (df["when"] >= MEDIA_FROM) & df["media"].str.contains(AD_FIRST, case=False, regex=True))
    partner = df["mla"] & no_tool & ~df["old_tools"]
    out = df.assign(removed=backlog | study | ads | partner).groupby("month").agg(
        total=("removed", "size"), removed=("removed", "sum"))
    out["kept"] = out["total"] - out["removed"]
    return out


def main():
    df = load()
    main_result = json.loads((HERE / "datapoints.json").read_text())
    results = {}

    # 1. recount
    rc = recount(df)
    rows, ok = [], True
    for m in main_result["months"]:
        mine, total = int(rc.loc[m["month"], "kept"]), int(rc.loc[m["month"], "total"])
        rows.append({"month": m["month"], "analysis": m["kept_on_record"], "recount": mine,
                     "diff": mine - m["kept_on_record"], "subscribers_diff": total - m["total"]})
        ok &= mine == m["kept_on_record"] and total == m["total"]
    results["recount"] = {"agrees": bool(ok), "rows": rows}
    print("recount agrees with analysis.py:", ok)
    for r in rows:
        print("  ", r)

    # 2. completeness
    growth = json.loads((HERE / "beehiiv_growth.json").read_text())["subscribed_daily"]
    cache = json.loads((ROOT / "frontend" / "public" / "beehiiv_new_subs_cache.json").read_text())["daily"]
    valid = df[~df["status"].isin(NOT_SUBSCRIBERS)].groupby("day").size()
    non_import = df[df["channel"] != "import"].groupby("day").size()  # the cache keeps invalid addresses
    comp, days_off = [], []
    for month, days in growth.items():
        keys = [f"{month}-{i + 1:02d}" for i in range(len(days))]
        days_off += [{"day": k, "walk": int(valid.get(k, 0)), "beehiiv": g}
                     for k, g in zip(keys, days) if int(valid.get(k, 0)) != g]
        walk = sum(int(valid.get(k, 0)) for k in keys)
        comp.append({"month": month, "walk_valid": walk, "beehiiv_growth_subscribed": sum(days),
                     "diff": walk - sum(days),
                     "walk_non_import_all_statuses": sum(int(non_import.get(k, 0)) for k in keys),
                     "dashboard_cache": sum(int(cache.get(k, 0)) for k in keys)})
    results["completeness"] = comp
    results["days_compared"] = sum(len(d) for d in growth.values())
    results["days_not_matching_beehiiv"] = days_off
    print("\nwalk (invalid and pending removed) vs beehiiv growth 'subscribed'; non-imports vs the dashboard cache:")
    for c in comp:
        print("  ", c)
    print(f"days where the walk differs from beehiiv: {len(days_off)} of {results['days_compared']}")
    for d in days_off[:40]:
        print("  ", d)

    # 3. shape vs GA4
    xc = json.loads((HERE / "cross_checks.json").read_text())
    ga4 = xc.get("ga4_submitted_email")
    if isinstance(ga4, list):
        events = {r["month"]: r["events"] for r in ga4 if r["medium"] == "not_cpc" and r["page"] == "other_tools"}
        cpc_events = {}
        for r in ga4:
            if r["medium"] == "cpc":
                cpc_events[r["month"]] = cpc_events.get(r["month"], 0) + r["events"]
        shape = []
        for m in main_result["months"]:
            ev = events.get(m["month"])
            shape.append({"month": m["month"], "kept_tools": m["kept_tools"], "ga4_events_non_cpc_non_study": ev,
                          "ratio": round(m["kept_tools"] / ev, 2) if ev else None,
                          "ads_all": m["ads_all"], "ga4_events_in_cpc_sessions": cpc_events.get(m["month"], 0)})
        results["ga4_shape"] = shape
        print("\ntool sign-ups kept vs GA4 Submitted Email (non-cpc sessions, non-study pages); ads vs cpc sessions:")
        for s in shape:
            print("  ", s)

    # 4. unsubscribes: weekly reconciliation of beehiiv's own series, and the monthly totals recomputed
    g = json.loads((HERE / "beehiiv_growth.json").read_text())
    daily = pd.DataFrame(
        [{"day": pd.Timestamp(f"{month}-{i + 1:02d}"), "subscribed": n, "unsubscribed": g["unsubscribed_daily"][month][i]}
         for month, days in g["subscribed_daily"].items() for i, n in enumerate(days)]).set_index("day").sort_index()
    daily["net"] = daily["subscribed"] - daily["unsubscribed"]
    sizes = pd.Series({pd.Timestamp(d): n for d, n in g["active_at_start_of_day"].items()}).sort_index()
    weeks = []
    for start, end in zip(sizes.index[:-1], sizes.index[1:]):
        span = daily.loc[start:end - pd.Timedelta(days=1)]
        if len(span) != (end - start).days:  # the week reaches outside the daily series
            continue
        weeks.append({"week": str(start.date()), "list_change": int(sizes[end] - sizes[start]),
                      "subscribed_minus_unsubscribed": int(span["net"].sum()),
                      "unexplained": int(sizes[end] - sizes[start] - span["net"].sum())})
    off = [w for w in weeks if abs(w["unexplained"]) > WEEK_TOLERANCE]
    monthly = daily.groupby(daily.index.strftime("%Y-%m"))["unsubscribed"].sum()
    mine = {m["month"]: m["unsubscribed"] for m in main_result["list_movement"]}
    unsub_ok = all(int(monthly[m]) == n for m, n in mine.items())
    results["unsubscribes"] = {"weeks_checked": len(weeks), "weeks_not_reconciling": off,
                               "total_unexplained": sum(w["unexplained"] for w in weeks),
                               "monthly_totals_agree": bool(unsub_ok)}
    print(f"\nweekly list size vs subscribed - unsubscribed: {len(weeks)} weeks, {len(off)} off by more than "
          f"{WEEK_TOLERANCE}, total unexplained {results['unsubscribes']['total_unexplained']}")
    for w in off:
        print("  ", w)
    print("monthly unsubscribe totals agree with analysis.py:", unsub_ok)
    ok &= unsub_ok

    # 5. net change without manual imports, recounted with a cruder rule: every import is manual except
    # those between the Jan 1 backlog and Mar 10 without the Leaf flag. analysis.py also treats the
    # workshop lists and partner-ad records uploaded in that window as manual, so it may be lower by those.
    subs = df[~df["status"].isin(NOT_SUBSCRIBERS)]
    imp = subs["channel"] == "import"
    routine = imp & (subs["when"] >= BACKLOG_UNTIL) & (subs["when"] < pd.Timestamp("2026-03-10", tz="UTC")) & ~subs["leaf"]
    crude_manual = (imp & ~routine).groupby(subs["month"]).sum()
    net_rows = []
    for m in main_result["net_without_imports"]:
        crude = m["subscribed"] - int(crude_manual.get(m["month"], 0)) - m["unsubscribed"]
        net_rows.append({"month": m["month"], "analysis_net": m["net"], "crude_net": crude, "diff": crude - m["net"]})
    results["net_without_imports"] = net_rows
    print("\nnet change without manual imports: analysis.py vs the crude rule")
    for r in net_rows:
        print("  ", r)

    (HERE / "cross_check_results.json").write_text(json.dumps(results, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
