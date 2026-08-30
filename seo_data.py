"""SEO opportunity mining for seo_advisor.py — GSC query/page analysis + Ahrefs data.

GSC side productionizes the manual investigation done while planning this feature: query-level
gains/losses, striking-distance keywords, low-CTR-despite-good-position, and page-level click
decay, comparing the last 28 days (offset 3 days for GSC's reporting lag) to the prior 28.

Ahrefs side pulls the Rank Tracker project's position deltas, a broader keyword-opportunity
scan beyond the tracked set, and the organic-competitor landscape.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import ahrefs_client

GSC_LAG_DAYS = 3
WINDOW_DAYS = 28


# --- small error-isolation helpers (same shape as weekly_advisor._safe/_is_err) --------------
def _safe(label, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {label} failed: {e}", file=sys.stderr)
        return ("__error__", f"{type(e).__name__}: {e}")


def _is_err(v) -> bool:
    return isinstance(v, tuple) and len(v) == 2 and v[0] == "__error__"


# --- GSC ----------------------------------------------------------------------------------
def _gsc_query(dimensions: list[str], start: date, end: date) -> list[dict]:
    from gsc_client import SITE_URL, get_client

    resp = get_client().searchanalytics().query(
        siteUrl=SITE_URL,
        body={"startDate": str(start), "endDate": str(end), "dimensions": dimensions, "rowLimit": 25000},
    ).execute()
    return resp.get("rows", [])


def gsc_query_movers(
    cur_start: date,
    cur_end: date,
    prev_start: date,
    prev_end: date,
    min_impressions: int = 10,
    min_delta: float = 3.0,
    striking_lo: int = 8,
    striking_hi: int = 20,
    striking_min_impr: int = 50,
    low_ctr_max_pos: int = 5,
    low_ctr_min_impr: int = 100,
    low_ctr_threshold: float = 0.03,
) -> dict:
    """Query-level gains/losses, striking-distance, and low-CTR-despite-good-position opportunities."""
    cur_rows = _gsc_query(["query"], cur_start, cur_end)
    prev_rows = _gsc_query(["query"], prev_start, prev_end)
    cur = {r["keys"][0]: r for r in cur_rows}
    prev = {r["keys"][0]: r for r in prev_rows}

    gains, losses = [], []
    for k, c in cur.items():
        p = prev.get(k)
        if not p or (c["impressions"] < min_impressions and p["impressions"] < min_impressions):
            continue
        delta = p["position"] - c["position"]  # positive = improved
        if abs(delta) < min_delta:
            continue
        row = {
            "query": k,
            "cur_position": round(c["position"], 1),
            "prev_position": round(p["position"], 1),
            "delta": round(delta, 1),
            "cur_clicks": int(c["clicks"]),
            "prev_clicks": int(p["clicks"]),
            "cur_impressions": int(c["impressions"]),
        }
        (gains if delta > 0 else losses).append(row)
    gains.sort(key=lambda r: -r["cur_impressions"])
    losses.sort(key=lambda r: -r["cur_impressions"])

    striking = [
        {
            "query": k,
            "position": round(c["position"], 1),
            "clicks": int(c["clicks"]),
            "impressions": int(c["impressions"]),
            "ctr": round(c["ctr"], 4),
        }
        for k, c in cur.items()
        if striking_lo <= c["position"] <= striking_hi and c["impressions"] >= striking_min_impr
    ]
    striking.sort(key=lambda r: -r["impressions"])

    low_ctr = [
        {
            "query": k,
            "position": round(c["position"], 1),
            "clicks": int(c["clicks"]),
            "impressions": int(c["impressions"]),
            "ctr": round(c["ctr"], 4),
        }
        for k, c in cur.items()
        if c["position"] <= low_ctr_max_pos and c["impressions"] >= low_ctr_min_impr and c["ctr"] < low_ctr_threshold
    ]
    low_ctr.sort(key=lambda r: -r["impressions"])

    total_cur_clicks = sum(r["clicks"] for r in cur_rows)
    total_prev_clicks = sum(r["clicks"] for r in prev_rows)
    total_cur_impr = sum(r["impressions"] for r in cur_rows)
    total_prev_impr = sum(r["impressions"] for r in prev_rows)

    return {
        "gains": gains[:15],
        "losses": losses[:15],
        "striking_distance": striking[:20],
        "low_ctr_top_positions": low_ctr[:15],
        "totals": {
            "cur_clicks": total_cur_clicks,
            "prev_clicks": total_prev_clicks,
            "cur_impressions": total_cur_impr,
            "prev_impressions": total_prev_impr,
            "click_change_pct": round((total_cur_clicks - total_prev_clicks) / total_prev_clicks * 100, 1)
            if total_prev_clicks
            else None,
            "impression_change_pct": round((total_cur_impr - total_prev_impr) / total_prev_impr * 100, 1)
            if total_prev_impr
            else None,
        },
    }


def gsc_page_decay(
    cur_start: date,
    cur_end: date,
    prev_start: date,
    prev_end: date,
    min_prior_clicks: int = 5,
    min_drop_pct: float = 25.0,
) -> list[dict]:
    """Pages whose clicks dropped by at least min_drop_pct — content decay / cannibalization candidates."""
    cur_rows = {r["keys"][0]: r for r in _gsc_query(["page"], cur_start, cur_end)}
    prev_rows = {r["keys"][0]: r for r in _gsc_query(["page"], prev_start, prev_end)}

    decayed = []
    for k, c in cur_rows.items():
        p = prev_rows.get(k)
        if not p or p["clicks"] < min_prior_clicks:
            continue
        drop = c["clicks"] - p["clicks"]
        if drop < 0 and (abs(drop) / p["clicks"] * 100) >= min_drop_pct:
            decayed.append({
                "page": k,
                "cur_clicks": int(c["clicks"]),
                "prev_clicks": int(p["clicks"]),
                "pct_change": round(drop / p["clicks"] * 100, 1),
                "cur_position": round(c["position"], 1),
                "prev_position": round(p["position"], 1),
            })
    decayed.sort(key=lambda r: r["pct_change"])
    return decayed[:15]


# --- Ahrefs ---------------------------------------------------------------------------------
def ahrefs_rank_tracker_snapshot(
    project_id: int, cur_date: str, prev_date: str, min_delta: int = 2, not_ranking_min_volume: int = 200
) -> dict:
    """Position deltas for the Ahrefs Rank Tracker project + high-volume tracked keywords we don't rank for."""
    rows = ahrefs_client.rank_tracker_overview(
        project_id=project_id,
        date=cur_date,
        date_compared=prev_date,
        select="keyword,position,position_prev,position_diff,volume,url,traffic,traffic_diff",
        order_by="volume:desc",
    )
    movers = [
        r
        for r in rows
        if r.get("position") is not None
        and r.get("position_diff") not in (None, 0)
        and abs(r["position_diff"]) >= min_delta
    ]
    movers.sort(key=lambda r: -(r.get("volume") or 0))

    not_ranking = [
        r for r in rows if r.get("position") is None and (r.get("volume") or 0) >= not_ranking_min_volume
    ]
    not_ranking.sort(key=lambda r: -(r.get("volume") or 0))

    return {
        "tracked_keyword_count": len(rows),
        "movers": movers[:15],
        "not_ranking_high_volume": not_ranking[:10],
    }


def ahrefs_keyword_opportunities(
    domain: str, cur_date: str, min_volume: int = 200, pos_lo: int = 4, pos_hi: int = 20, limit_return: int = 25
) -> list[dict]:
    """Non-branded keywords ranking position 4-20 with meaningful volume, beyond the tracked set."""
    rows = ahrefs_client.organic_keywords(
        target=domain,
        date=cur_date,
        country="us",
        mode="subdomains",
        select="keyword,best_position,volume,is_branded,best_position_url,keyword_difficulty",
        order_by="volume:desc",
        limit=300,
    )
    opportunities = [
        r
        for r in rows
        if not r.get("is_branded")
        and r.get("best_position") is not None
        and pos_lo <= r["best_position"] <= pos_hi
        and (r.get("volume") or 0) >= min_volume
    ]
    opportunities.sort(key=lambda r: -(r.get("volume") or 0))
    return opportunities[:limit_return]


def ahrefs_competitor_landscape(domain: str, cur_date: str, limit: int = 12, beatable_dr_max: int = 55) -> list[dict]:
    """Organic competitors by keyword overlap, tagged 'beatable' vs 'giant' by domain rating."""
    rows = ahrefs_client.organic_competitors(
        target=domain,
        date=cur_date,
        country="us",
        mode="subdomains",
        select="competitor_domain,domain_rating,keywords_common,keywords_competitor,keywords_target,traffic",
        order_by="keywords_common:desc",
        limit=limit,
    )
    for r in rows:
        r["tier"] = "beatable" if (r.get("domain_rating") or 100) <= beatable_dr_max else "giant"
    return rows


# --- gather everything ------------------------------------------------------------------------
def gather_seo_snapshot(project_id: int | None = None, domain: str | None = None) -> dict:
    project_id = project_id or int(os.getenv("AHREFS_PROJECT_CLEARERTHINKING") or 0)
    domain = domain or os.getenv("SITE_DOMAIN", "clearerthinking.org")

    gsc_end = date.today() - timedelta(days=GSC_LAG_DAYS)
    gsc_cur_start = gsc_end - timedelta(days=WINDOW_DAYS - 1)
    gsc_prev_end = gsc_cur_start - timedelta(days=1)
    gsc_prev_start = gsc_prev_end - timedelta(days=WINDOW_DAYS - 1)

    ahrefs_cur_date = date.today().isoformat()
    ahrefs_prev_date = (date.today() - timedelta(days=30)).isoformat()

    errors: dict[str, str] = {}

    def grab(label, fn, *a, **k):
        v = _safe(label, fn, *a, **k)
        if _is_err(v):
            errors[label] = v[1]
            return None
        return v

    query_movers = grab("gsc_queries", gsc_query_movers, gsc_cur_start, gsc_end, gsc_prev_start, gsc_prev_end)
    page_decay = grab("gsc_pages", gsc_page_decay, gsc_cur_start, gsc_end, gsc_prev_start, gsc_prev_end)
    rank_tracker = (
        grab("ahrefs_rank_tracker", ahrefs_rank_tracker_snapshot, project_id, ahrefs_cur_date, ahrefs_prev_date)
        if project_id
        else None
    )
    keyword_opps = grab("ahrefs_keywords", ahrefs_keyword_opportunities, domain, ahrefs_cur_date)
    competitors = grab("ahrefs_competitors", ahrefs_competitor_landscape, domain, ahrefs_cur_date)

    return {
        "period": {
            "current": [str(gsc_cur_start), str(gsc_end)],
            "prior": [str(gsc_prev_start), str(gsc_prev_end)],
        },
        "gsc_query_movers": query_movers,
        "gsc_page_decay": page_decay,
        "ahrefs_rank_tracker": rank_tracker,
        "ahrefs_keyword_opportunities": keyword_opps,
        "ahrefs_competitors": competitors,
        "errors": errors,
    }
