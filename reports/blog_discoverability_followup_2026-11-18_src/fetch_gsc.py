"""Search Console side of the follow-up.

1. URL Inspection (Google's own index verdict) for every blog post in the sitemap or the Wix API, plus
   every row of the Aug 2026 tracking sheet "CT - Pages Not Indexed" (the baseline).
2. Search Analytics: weekly clicks/impressions per /post/ page since June 2026, and the queries of the
   article Markus flagged.

Writes data/gsc_inspection.json, data/baseline_sheet.json, data/gsc_weekly_pages.json, data/gsc_markus.json.
Resumable: URLs already inspected are skipped. The Inspection API allows 2,000 calls a day per property.
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))

import gsc_client  # noqa: E402
import sheets_client  # noqa: E402

DATA = HERE / "data"
SITE = "sc-domain:clearerthinking.org"
SHEET = "18PunTg8tkSMcwKphwCzSkAdlpFsM2mylgAIWTuo2Wg4"
MARKUS = "https://www.clearerthinking.org/post/what-20-000-people-taught-us-about-entrepreneurship-and-startups"
FIRST_WEEK = date(2026, 6, 1)  # a Monday
_local = threading.local()


def svc():
    if not hasattr(_local, "svc"):
        _local.svc = gsc_client.get_client()  # httplib2 is not thread-safe: one client per thread
    return _local.svc


def inspect(url: str) -> dict:
    try:
        res = svc().urlInspection().index().inspect(
            body={"inspectionUrl": url, "siteUrl": SITE}).execute()
        return {"url": url, **res.get("inspectionResult", {}).get("indexStatusResult", {})}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": str(e)[:300]}


def baseline_rows() -> list[dict]:
    rows = sheets_client.get_values(SHEET, "'Not Indexed'!A2:F1000")
    return [{"domain": r[0], "url": r[1], "reason": r[2] if len(r) > 2 else "",
             "last_crawl": r[4] if len(r) > 4 else "", "sitemap": r[5] if len(r) > 5 else ""}
            for r in rows if len(r) > 1 and r[1].startswith("http")]


def run_inspections(urls: list[str]) -> None:
    out = DATA / "gsc_inspection.json"
    done = json.loads(out.read_text()) if out.exists() else {}
    todo = [u for u in dict.fromkeys(urls) if u not in done or "error" in done[u]]
    print(f"{len(urls)} URLs, {len(todo)} to inspect", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for n, rec in enumerate(ex.map(inspect, todo), 1):
            done[rec["url"]] = rec
            if n % 50 == 0 or n == len(todo):
                out.write_text(json.dumps(done))
                print(f"  {n}/{len(todo)}", flush=True)
    out.write_text(json.dumps(done))


def query(body: dict) -> list[dict]:
    rows, start = [], 0
    while True:
        res = svc().searchanalytics().query(
            siteUrl=SITE, body={**body, "rowLimit": 25000, "startRow": start}).execute()
        batch = res.get("rows", [])
        rows += batch
        start += len(batch)
        if len(batch) < 25000:
            return rows


def weekly_pages(last_day: date) -> list[dict]:
    """One row per (ISO week starting Monday, /post/ page). Only complete weeks."""
    out, wk = [], FIRST_WEEK
    while wk + timedelta(days=6) <= last_day:
        rows = query({"startDate": wk.isoformat(), "endDate": (wk + timedelta(days=6)).isoformat(),
                      "dimensions": ["page"], "type": "web",
                      "dimensionFilterGroups": [{"filters": [
                          {"dimension": "page", "operator": "contains", "expression": "clearerthinking.org/post/"}]}]})
        out += [{"week": wk.isoformat(), "page": r["keys"][0], "clicks": r["clicks"],
                 "impressions": r["impressions"]} for r in rows]
        print(f"  week {wk}: {len(rows)} pages", flush=True)
        wk += timedelta(days=7)
    return out


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    base = baseline_rows()
    (DATA / "baseline_sheet.json").write_text(json.dumps(base, indent=1))
    crawl = json.loads((DATA / "crawl.json").read_text()) if (DATA / "crawl.json").exists() else {}
    wix = json.loads((DATA / "wix_posts.json").read_text())
    sitemap_posts = [e["url"] for e in crawl.get("sitemaps", {}).get("posts", [])]
    run_inspections(sitemap_posts + [p["url"] for p in wix["posts"]] + [b["url"] for b in base])

    last = date.today() - timedelta(days=3)  # Search Console lags about three days
    (DATA / "gsc_weekly_pages.json").write_text(json.dumps(weekly_pages(last)))
    markus = {
        "by_week": query({"startDate": "2025-07-07", "endDate": last.isoformat(), "dimensions": ["date"],
                          "type": "web", "dimensionFilterGroups": [{"filters": [
                              {"dimension": "page", "operator": "equals", "expression": MARKUS}]}]}),
        "queries_since_oct": query({"startDate": "2026-10-01", "endDate": last.isoformat(),
                                    "dimensions": ["query"], "type": "web", "dimensionFilterGroups": [{"filters": [
                                        {"dimension": "page", "operator": "equals", "expression": MARKUS}]}]}),
    }
    (DATA / "gsc_markus.json").write_text(json.dumps(markus))
    print("done", flush=True)
