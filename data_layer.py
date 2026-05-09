"""Data fetching layer for the dashboard. All functions are date-range scoped and cached for 10 minutes."""
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

CACHE_TTL = 600  # 10 minutes


# =============================================================================
# GA4
# =============================================================================
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ga4_audience_metrics(start: date, end: date) -> dict:
    """Top-line GA4 metrics + custom event counts."""
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Filter,
        FilterExpression,
        Metric,
        RunReportRequest,
    )
    from ga4_client import get_client, property_path

    client = get_client()
    rng = DateRange(start_date=str(start), end_date=str(end))

    # Top-line: users + sessions
    top = client.run_report(RunReportRequest(
        property=property_path(),
        date_ranges=[rng],
        metrics=[Metric(name="totalUsers"), Metric(name="sessions"), Metric(name="screenPageViews")],
    ))
    if top.rows:
        users = int(top.rows[0].metric_values[0].value)
        sessions = int(top.rows[0].metric_values[1].value)
        pageviews = int(top.rows[0].metric_values[2].value)
    else:
        users = sessions = pageviews = 0

    # Custom events: "Viewed Privacy Policy" + "Submitted Email"
    def event_count(name: str) -> int:
        resp = client.run_report(RunReportRequest(
            property=property_path(),
            date_ranges=[rng],
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            dimension_filter=FilterExpression(
                filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value=name)),
            ),
        ))
        return int(resp.rows[0].metric_values[0].value) if resp.rows else 0

    return {
        "users": users,
        "sessions": sessions,
        "pageviews": pageviews,
        "modules_started": event_count("Viewed Privacy Policy"),
        "modules_finished": event_count("Submitted Email"),
    }


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ga4_daily_users(start: date, end: date) -> list[dict]:
    """Daily users for the time series chart."""
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, OrderBy, RunReportRequest
    from ga4_client import get_client, property_path

    resp = get_client().run_report(RunReportRequest(
        property=property_path(),
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="totalUsers")],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    ))
    out = []
    for row in resp.rows:
        d = row.dimension_values[0].value  # YYYYMMDD
        out.append({
            "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
            "users": int(row.metric_values[0].value),
        })
    return out


# =============================================================================
# Stripe
# =============================================================================
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def stripe_metrics(start: date, end: date) -> dict:
    from stripe_client import get_client

    s = get_client()
    start_ts = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp()) + 86400  # inclusive

    gross = 0
    refunded = 0
    daily = defaultdict(int)
    for ch in s.Charge.list(created={"gte": start_ts, "lt": end_ts}, limit=100).auto_paging_iter():
        if ch.status != "succeeded":
            continue
        gross += ch.amount
        refunded += ch.amount_refunded or 0
        d = datetime.fromtimestamp(ch.created, tz=timezone.utc).date()
        daily[d.isoformat()] += (ch.amount - (ch.amount_refunded or 0))

    return {
        "revenue_usd": (gross - refunded) / 100,
        "gross_usd": gross / 100,
        "refunded_usd": refunded / 100,
        "daily": [{"date": d, "revenue": v / 100} for d, v in sorted(daily.items())],
    }


# =============================================================================
# Google Ads
# =============================================================================
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def google_ads_metrics(start: date, end: date) -> dict:
    try:
        from google_ads_client import CUSTOMER_ID, get_client

        svc = get_client().get_service("GoogleAdsService")
        query = f"""
            SELECT
              segments.date,
              metrics.cost_micros,
              metrics.impressions,
              metrics.clicks,
              metrics.conversions
            FROM customer
            WHERE segments.date BETWEEN '{start}' AND '{end}'
        """
        cost = 0.0
        impr = 0
        clicks = 0
        conv = 0.0
        daily: dict[str, float] = defaultdict(float)
        for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
            for row in batch.results:
                d_cost = row.metrics.cost_micros / 1_000_000
                cost += d_cost
                impr += row.metrics.impressions
                clicks += row.metrics.clicks
                conv += row.metrics.conversions
                daily[row.segments.date] += d_cost

        return {
            "spend_usd": cost,
            "impressions": impr,
            "clicks": clicks,
            "conversions": conv,
            "daily": [{"date": d, "spend": v} for d, v in sorted(daily.items())],
            "error": None,
        }
    except Exception as e:
        return {"spend_usd": 0, "impressions": 0, "clicks": 0, "conversions": 0, "daily": [], "error": str(e)}


# =============================================================================
# beehiiv (direct REST API)
# =============================================================================
BEEHIIV_BASE = "https://api.beehiiv.com/v2"


def _beehiiv_period(days: int) -> str:
    """Map a date-range size to beehiiv's nearest canned period."""
    if days <= 1:
        return "last_24_hours"
    if days <= 7:
        return "last_7_days"
    if days <= 30:
        return "last_4_weeks"
    if days <= 95:
        return "last_3_months"
    return "last_12_months"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def beehiiv_metrics(start: date, end: date) -> dict:
    api_key = os.getenv("BEEHIIV_API_KEY", "").strip()
    pub_id = os.getenv("BEEHIIV_PUB_CLEARER_THINKING", "").strip()

    if not api_key:
        return {"error": "BEEHIIV_API_KEY not set in .env. See https://app.beehiiv.com/settings/integrations/api"}
    if not pub_id:
        return {"error": "BEEHIIV_PUB_CLEARER_THINKING not set in .env"}

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    # ---- Total active subscribers (current state) ----
    r = requests.get(f"{BEEHIIV_BASE}/publications/{pub_id}", headers=headers, params={"expand[]": "stats"})
    if r.status_code == 401:
        return {"error": "BEEHIIV_API_KEY rejected (401). Regenerate the key in beehiiv settings."}
    r.raise_for_status()
    pub_data = r.json().get("data", {})
    pub_stats = pub_data.get("stats", {})
    total_subs = pub_stats.get("active_subscriptions") or pub_stats.get("active_subscribers") or 0

    # ---- List posts in date range ----
    posts = []
    page = 1
    while True:
        r = requests.get(
            f"{BEEHIIV_BASE}/publications/{pub_id}/posts",
            headers=headers,
            params={"page": page, "limit": 100, "expand[]": "stats", "platform": "email", "status": "confirmed"},
        )
        r.raise_for_status()
        data = r.json()
        posts.extend(data.get("data", []))
        if page >= data.get("total_pages", 1):
            break
        page += 1

    # Filter to date range
    in_range = []
    for p in posts:
        ts = p.get("publish_date")
        if isinstance(ts, int):
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        elif isinstance(ts, str):
            try:
                d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            except ValueError:
                continue
        else:
            continue
        if start <= d <= end:
            in_range.append({**p, "_date": d})

    # Aggregate per-post stats
    emails_sent = 0
    opens = 0
    clicks = 0
    unsubs = 0
    per_campaign: list[dict] = []
    for p in in_range:
        s = p.get("stats", {}) or {}
        em = s.get("email", {}) or {}
        sent = em.get("recipients", 0) or 0
        op = em.get("opens", 0) or 0
        cl = em.get("clicks", 0) or 0
        un = em.get("unsubscribes", 0) or 0
        emails_sent += sent
        opens += op
        clicks += cl
        unsubs += un
        per_campaign.append({
            "title": p.get("title", "(untitled)"),
            "date": p["_date"].isoformat(),
            "sent": sent,
            "opens": op,
            "clicks": cl,
            "open_rate": (op / sent) if sent else 0,
            "click_rate": (cl / sent) if sent else 0,
            "unsubs": un,
        })
    per_campaign.sort(key=lambda r: r["date"], reverse=True)

    # ---- New subs in window: use beehiiv stats endpoint with closest canned period ----
    days = (end - start).days + 1
    period_used = _beehiiv_period(days)
    new_subs = 0
    churned = 0
    try:
        # The stats endpoint returns publication-level period stats
        r = requests.get(
            f"{BEEHIIV_BASE}/publications/{pub_id}",
            headers=headers,
            params={"expand[]": "stats", "stats_period": period_used},
        )
        r.raise_for_status()
        ps = r.json().get("data", {}).get("stats", {})
        # beehiiv returns these under a period key sometimes; try both shapes
        period_block = ps.get(period_used) or ps
        new_subs = period_block.get("subscriptions", 0) if isinstance(period_block, dict) else 0
    except Exception:
        pass

    open_rate = (opens / emails_sent) if emails_sent else 0
    click_rate = (clicks / emails_sent) if emails_sent else 0
    unsub_rate = (unsubs / emails_sent) if emails_sent else 0

    return {
        "error": None,
        "total_subscribers": int(total_subs),
        "new_subscribers": int(new_subs),
        "campaigns_count": len(in_range),
        "emails_sent": emails_sent,
        "email_opens": opens,
        "email_clicks": clicks,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "unsubscribes": unsubs,
        "unsubscribe_rate": unsub_rate,
        "engaged_readers": int(total_subs * open_rate),
        "opens_per_campaign": int(opens / len(in_range)) if in_range else 0,
        "per_campaign": per_campaign,
        "period_used_for_new_subs": period_used,  # surfaced so the UI can show a footnote
    }
