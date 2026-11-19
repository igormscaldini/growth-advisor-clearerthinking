"""Unique users per Clearer Thinking tool (GA4) -> data.json.

    .venv/bin/python reports/top_tools_ranking_2026-11-19_src/fetch_data.py [--end YYYY-MM-DD]

1. The tool list is read from the live tools page (the same reader the Get Coaching button uses); names, short
   descriptions and launch dates come from the Airtable programs base.
2. One GA4 report per window gives users per page path on programs.clearerthinking.org; ranking.py says which
   paths belong to which tool.
3. Users cannot be added across pages (one person can open two spellings of the same page), so every tool that could
   reach the top 10 gets its own GA4 query over exactly its paths, which returns each person once.
Every window is stored twice: the tool's own pages ("own"), and those plus partner-branded copies ("with_partner").
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT), str(ROOT / "gtm")]

import ranking as R  # noqa: E402

HOST = R.TOOLS_HOST
TOP_N = 10
# GA4 user counts are estimates (HyperLogLog++), so two queries over the same people can differ a little:
# the Who Attracts You pages gave 1,199,001 in one query against 1,198,888 to 1,198,903 from the page report.
TOLERANCE = 0.02


def windows(end: date) -> dict[str, tuple[date, date]]:
    return {
        "12m": (end.replace(year=end.year - 1) + timedelta(days=1), end),
        "ytd": (date(end.year, 1, 1), end),
        "90d": (end - timedelta(days=89), end),
    }


def ga4_users(client, prop, start: date, end: date, paths: list[str] | None = None) -> list[tuple[str, int]] | int:
    """Without `paths`: (pagePath, totalUsers) for every page of HOST. With `paths`: the number of distinct users
    who viewed ANY of those exact paths (one row, no page dimension, so each person counts once)."""
    from google.analytics.data_v1beta.types import (DateRange, Dimension, Filter, FilterExpression,
                                                    FilterExpressionList, Metric, RunReportRequest)
    host = FilterExpression(filter=Filter(field_name="hostName", string_filter=Filter.StringFilter(value=HOST)))
    request = dict(property=prop, date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
                   metrics=[Metric(name="totalUsers")])
    if paths is None:
        resp = client.run_report(RunReportRequest(dimensions=[Dimension(name="pagePath")], dimension_filter=host,
                                                  limit=250000, **request), timeout=180)
        meta = resp.metadata
        if meta.data_loss_from_other_row or meta.subject_to_thresholding or list(meta.sampling_metadatas):
            raise SystemExit(f"GA4 returned an incomplete page report for {start}..{end}: {meta}")
        return [(r.dimension_values[0].value, int(r.metric_values[0].value)) for r in resp.rows]
    in_list = FilterExpression(filter=Filter(field_name="pagePath",
                                             in_list_filter=Filter.InListFilter(values=paths, case_sensitive=True)))
    resp = client.run_report(RunReportRequest(
        dimension_filter=FilterExpression(and_group=FilterExpressionList(expressions=[host, in_list])), **request),
        timeout=180)
    return int(resp.rows[0].metric_values[0].value) if resp.rows else 0


def window_counts(client, prop, start: date, end: date, bases) -> dict:
    grouped = R.group_paths(ga4_users(client, prop, start, end), bases)
    out = {"start": str(start), "end": str(end), "tools": {b: {} for b in bases}, "certain": {}}
    for variant, kinds in (("own", ("own",)), ("with_partner", ("own", "partner"))):
        paths = {b: {p: u for k in kinds for p, u in grouped[b][k].items()} for b in bases}
        limits = {b: R.bounds(paths[b]) for b in bases}
        candidates = R.pick_candidates({b: hi for b, (_, hi) in limits.items()}, TOP_N)
        exact = {}
        for b in candidates:
            lo, hi = limits[b]
            # one page: its own count is already exact; own-pages count reused when the tool has no partner copy
            if variant == "with_partner" and not grouped[b]["partner"] and "users" in out["tools"][b].get("own", {}):
                exact[b] = out["tools"][b]["own"]["users"]
            else:
                exact[b] = lo if len(paths[b]) <= 1 else ga4_users(client, prop, start, end, sorted(paths[b]))
            if not lo * (1 - TOLERANCE) <= exact[b] <= hi * (1 + TOLERANCE):
                raise SystemExit(f"{b} ({variant}, {start}..{end}): {exact[b]} users is outside its bounds {lo}..{hi}")
        for b in bases:
            lo, hi = limits[b]
            entry = {"lower": lo, "upper": hi, "pages": len(paths[b])}
            if b in exact:
                entry["users"] = exact[b]
            out["tools"][b][variant] = entry
        rest = {b: hi for b, (_, hi) in limits.items() if b not in exact}
        out["certain"][variant] = R.ranking_is_certain(exact, rest, TOP_N)
        if variant == "own":
            out["partner_pages"] = {p: u for b in bases for p, u in grouped[b]["partner"].items()}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1),
                    help="last full day counted (default: yesterday)")
    args = ap.parse_args()

    import airtable_client
    import coaching_fab_tools_list as tools_page
    from ga4_client import get_client, property_path

    tools, elsewhere = R.tools_from_cards(tools_page.fetch_cards())
    if len(tools) < 50:
        raise SystemExit(f"Only {len(tools)} tools found on the tools page: it probably did not render fully.")
    matched = 0
    for rec in airtable_client.launched_tools():
        f = rec["fields"]
        base = R.base_of(f.get("Public program URL") or "")
        if base in tools:
            matched += 1
            tools[base].update(name=f.get("Name") or tools[base]["name"],
                               description=(f.get("Short Description (for website and newsletter)") or "").strip(),
                               launch_date=f.get("Launch date"))
    print(f"{len(tools)} tools on {HOST} ({matched} matched in Airtable), {len(elsewhere)} hosted elsewhere: {elsewhere}")

    client, prop = get_client(), property_path()
    data = {"fetched": datetime.now().isoformat(timespec="minutes"), "host": HOST, "top_n": TOP_N,
            "tools": tools, "elsewhere": elsewhere, "excluded": list(R.EXCLUDED.values()), "windows": {}}
    for name, (start, end) in windows(args.end).items():
        data["windows"][name] = w = window_counts(client, prop, start, end, set(tools))
        print(f"\n{name}: {start} to {end}   (ranking certain: {w['certain']})")
        for variant in ("own", "with_partner"):
            users = {b: t[variant]["users"] for b, t in w["tools"].items() if "users" in t[variant]}
            print(f"  {variant}")
            for i, (b, u) in enumerate(R.rank(users, TOP_N + 3), 1):
                print(f"    {i:2d}. {tools[b]['name'][:44]:44s} {u:>10,}   bounds {w['tools'][b][variant]['lower']:,}..{w['tools'][b][variant]['upper']:,}")
    (HERE / "data.json").write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {HERE / 'data.json'}")


if __name__ == "__main__":
    main()
