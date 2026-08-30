"""Shared Ahrefs API v3 client — thin REST wrapper for the SEO advisor.

Requires AHREFS_API_KEY (Ahrefs account → Settings → API access). Unlike the Ahrefs MCP
connector (only reachable inside an interactive Claude session), this hits Ahrefs' REST API
directly so it works from headless cron (GitHub Actions). Each call consumes Ahrefs API
units — keep call volume to the handful needed for the monthly report, not per-keyword loops.
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.ahrefs.com/v3"
API_KEY = os.getenv("AHREFS_API_KEY", "").strip()


def _get(path: str, params: dict) -> dict:
    if not API_KEY:
        raise SystemExit("AHREFS_API_KEY not set in .env")
    r = requests.get(
        f"{BASE_URL}/{path}",
        headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def rank_tracker_overview(
    project_id: int,
    date: str,
    date_compared: str,
    select: str,
    device: str = "desktop",
    order_by: str | None = None,
    limit: int = 1000,
) -> list[dict]:
    """Position/traffic deltas for every keyword tracked in an Ahrefs Rank Tracker project."""
    params = {
        "select": select,
        "date": date,
        "date_compared": date_compared,
        "device": device,
        "project_id": project_id,
        "limit": limit,
    }
    if order_by:
        params["order_by"] = order_by
    return _get("rank-tracker/overview", params).get("overviews", [])


def organic_keywords(
    target: str,
    date: str,
    select: str,
    country: str = "us",
    mode: str = "subdomains",
    order_by: str | None = None,
    limit: int = 1000,
) -> list[dict]:
    """Full organic keyword universe a domain ranks for (broader than a Rank Tracker project)."""
    params = {
        "select": select,
        "target": target,
        "mode": mode,
        "country": country,
        "date": date,
        "limit": limit,
    }
    if order_by:
        params["order_by"] = order_by
    return _get("site-explorer/organic-keywords", params).get("keywords", [])


def organic_competitors(
    target: str,
    date: str,
    select: str,
    country: str = "us",
    mode: str = "subdomains",
    order_by: str | None = None,
    limit: int = 15,
) -> list[dict]:
    """Domains competing for the same organic keywords, with overlap + domain rating."""
    params = {
        "select": select,
        "target": target,
        "mode": mode,
        "country": country,
        "date": date,
        "limit": limit,
    }
    if order_by:
        params["order_by"] = order_by
    return _get("site-explorer/organic-competitors", params).get("competitors", [])
