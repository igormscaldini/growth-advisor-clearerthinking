"""Independent checks of analysis.py. Shares no code with it.

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/cross_check.py

1. Recount: the simplest valid way to get the same table. pandas + two regular expressions on the raw
   strings ("does the tools list START with the study?", "does the media list START with cpc?"), then
   total minus removed per month. Must equal datapoints.json exactly.
2. Completeness of the walk: records per day against beehiiv's own growth series (beehiiv_growth.json,
   from its connector) and, for non-imports, against the dashboard's incremental cache.
3. Shape: the kept tool sign-ups per month against GA4 "Submitted Email" events outside cpc sessions and
   outside the study page (cross_checks.json). Events are not subscribers, so only the ratio's stability
   is informative.

Writes cross_check_results.json and exits non-zero if the recount disagrees.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent.parent

STUDY_FIRST = r"^[\s|]*who attracts you\s*(?:\||$)"
CPC_FIRST = r"^[\s,]*cpc\s*(?:,|$)"


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
                "media": cf.get("UTM Media (Comma-Separated)") or "",
                "dating": bool(cf.get("Dating App Updates")),
            })
    df = pd.DataFrame(recs)
    when = pd.to_datetime(df["created"], unit="s", utc=True)
    df["month"] = when.dt.strftime("%Y-%m")
    df["day"] = when.dt.strftime("%Y-%m-%d")
    return df


def recount(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["status"] != "invalid"]  # beehiiv does not count invalid addresses as subscribers
    no_tool = df["tools"].str.replace(r"[\s|]|\(none\)", "", regex=True, case=False) == ""
    study = df["tools"].str.contains(STUDY_FIRST, case=False, regex=True) | (no_tool & df["dating"])
    ads = (df["native_medium"] == "cpc") | df["media"].str.contains(CPC_FIRST, case=False, regex=True)
    out = df.assign(removed=study | ads).groupby("month").agg(total=("removed", "size"), removed=("removed", "sum"))
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
        mine = int(rc.loc[m["month"], "kept"])
        rows.append({"month": m["month"], "analysis": m["included"], "recount": mine, "diff": mine - m["included"]})
        ok &= mine == m["included"] and int(rc.loc[m["month"], "total"]) == m["total"]
    results["recount"] = {"agrees": bool(ok), "rows": rows}
    print("recount agrees with analysis.py:", ok)
    for r in rows:
        print("  ", r)

    # 2. completeness
    growth = json.loads((HERE / "beehiiv_growth.json").read_text())["subscribed_daily"]
    cache = json.loads((ROOT / "frontend" / "public" / "beehiiv_new_subs_cache.json").read_text())["daily"]
    valid = df[df["status"] != "invalid"].groupby("day").size()
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
    results["days_not_matching_beehiiv"] = days_off
    print("\nwalk (invalid addresses removed) vs beehiiv growth 'subscribed'; non-imports vs the dashboard cache:")
    for c in comp:
        print("  ", c)
    print(f"days where the walk differs from beehiiv: {len(days_off)} of {sum(len(d) for d in growth.values())}")
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
            tools = m["buckets"]["tools"]
            ev = events.get(m["month"])
            shape.append({"month": m["month"], "kept_tool_signups": tools, "ga4_events_non_cpc_non_study": ev,
                          "ratio": round(tools / ev, 2) if ev else None,
                          "ads_bucket": m["buckets"]["ads"], "ga4_events_in_cpc_sessions": cpc_events.get(m["month"], 0)})
        results["ga4_shape"] = shape
        print("\nkept tool sign-ups vs GA4 Submitted Email (non-cpc sessions, non-study pages):")
        for s in shape:
            print("  ", s)

    (HERE / "cross_check_results.json").write_text(json.dumps(results, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
