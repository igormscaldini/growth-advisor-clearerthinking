"""Independent recount of the published ranking: the simplest other way to get the same numbers.

fetch_data.py lists a tool's exact page paths (ranking.classify) and asks GA4 for the people who saw any of them.
This script uses neither that list nor that rule: for each tool in the top 10 it builds one regular expression straight
from the tool's public link and lets GA4 match the pages itself. Counts must agree within GA4's estimation noise.

    .venv/bin/python reports/top_tools_ranking_2026-11-19_src/cross_check.py [--window 12m]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
TOLERANCE = 0.02
# Old addresses, written out by hand here on purpose (not read from ranking.ALIASES).
EXTRA_PAGES = {"The Ultimate Personality Test": ["/personality.html"]}


def page_pattern(link: str) -> str:
    stem = re.sub(r"(\.html|/)$", "", urllib.parse.urlsplit(link).path)
    return re.escape(stem) + r"(\.html|/.*)?"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--window", default="12m")
    args = ap.parse_args()
    from google.analytics.data_v1beta.types import (DateRange, Filter, FilterExpression, FilterExpressionList, Metric,
                                                    RunReportRequest)
    from ga4_client import get_client, property_path

    data = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
    w = data["windows"][args.window]
    mine = sorted(((t["own"]["users"], b) for b, t in w["tools"].items() if "users" in t["own"]), reverse=True)[:data["top_n"]]
    client, bad = get_client(), 0
    host = FilterExpression(filter=Filter(field_name="hostName", string_filter=Filter.StringFilter(value=data["host"])))
    print(f"{args.window}: {w['start']} to {w['end']}\n{'tool':38s}{'published':>12s}{'recount':>12s}{'diff':>8s}")
    for users, base in mine:
        tool = data["tools"][base]
        pattern = "|".join([page_pattern(tool["url"])] + [re.escape(p) for p in EXTRA_PAGES.get(tool["name"], [])])
        match = FilterExpression(filter=Filter(field_name="pagePath", string_filter=Filter.StringFilter(
            match_type=Filter.StringFilter.MatchType.FULL_REGEXP, value=pattern, case_sensitive=False)))
        resp = client.run_report(RunReportRequest(
            property=property_path(), date_ranges=[DateRange(start_date=w["start"], end_date=w["end"])],
            metrics=[Metric(name="totalUsers")],
            dimension_filter=FilterExpression(and_group=FilterExpressionList(expressions=[host, match]))), timeout=180)
        recount = int(resp.rows[0].metric_values[0].value) if resp.rows else 0
        diff = recount / users - 1
        bad += abs(diff) > TOLERANCE
        print(f"{tool['name'][:37]:38s}{users:>12,}{recount:>12,}{diff:>8.2%}{'   MISMATCH' if abs(diff) > TOLERANCE else ''}")
    print("all within tolerance" if not bad else f"{bad} tools differ by more than {TOLERANCE:.0%}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
