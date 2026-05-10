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


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ga4_daily_users_and_events(start: date, end: date) -> list[dict]:
    """Daily users + Modules Started (Viewed Privacy Policy) + Modules Finished (Submitted Email)."""
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Filter,
        FilterExpression,
        FilterExpressionList,
        Metric,
        OrderBy,
        RunReportRequest,
    )
    from ga4_client import get_client, property_path

    client = get_client()
    rng = DateRange(start_date=str(start), end_date=str(end))

    users = client.run_report(RunReportRequest(
        property=property_path(),
        date_ranges=[rng],
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="totalUsers")],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    ))
    users_by_date = {r.dimension_values[0].value: int(r.metric_values[0].value) for r in users.rows}

    evts = client.run_report(RunReportRequest(
        property=property_path(),
        date_ranges=[rng],
        dimensions=[Dimension(name="date"), Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(or_group=FilterExpressionList(expressions=[
            FilterExpression(filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value="Viewed Privacy Policy"))),
            FilterExpression(filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value="Submitted Email"))),
        ])),
    ))
    events_by_date: dict[str, dict[str, int]] = {}
    for r in evts.rows:
        d = r.dimension_values[0].value
        e = r.dimension_values[1].value
        events_by_date.setdefault(d, {})[e] = int(r.metric_values[0].value)

    out = []
    all_dates = sorted(set(users_by_date) | set(events_by_date))
    for d in all_dates:
        out.append({
            "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
            "users": users_by_date.get(d, 0),
            "modules_started": events_by_date.get(d, {}).get("Viewed Privacy Policy", 0),
            "modules_finished": events_by_date.get(d, {}).get("Submitted Email", 0),
        })
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ga4_funnel_events(start: date, end: date) -> dict:
    """Counts for the 3-step funnel."""
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

    def count(event: str) -> int:
        resp = client.run_report(RunReportRequest(
            property=property_path(),
            date_ranges=[rng],
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            dimension_filter=FilterExpression(
                filter=Filter(field_name="eventName", string_filter=Filter.StringFilter(value=event)),
            ),
        ))
        return int(resp.rows[0].metric_values[0].value) if resp.rows else 0

    return {
        "viewed_privacy": count("Viewed Privacy Policy"),
        "accepted_privacy": count("Accepted Privacy Policy"),
        "submitted_email": count("Submitted Email"),
    }


# =============================================================================
# Stripe
# =============================================================================
def _to_monthly(unit_amount: int, interval: str, interval_count: int, quantity: int) -> float:
    """Normalize a Stripe price interval to a monthly USD figure."""
    months_in_period = {"day": 1 / 30.4, "week": 1 / 4.33, "month": 1, "year": 12}.get(interval, 1)
    period_months = months_in_period * (interval_count or 1)
    if period_months == 0:
        return 0.0
    return (unit_amount / 100.0) * quantity / period_months


def _date_to_ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def stripe_metrics(start: date, end: date) -> dict:
    """Total + daily revenue, split by subscription (paid invoices) vs one-time (charges - invoices)."""
    from stripe_client import get_client

    s = get_client()
    start_ts = _date_to_ts(start)
    end_ts = _date_to_ts(end) + 86400

    # Total revenue from all successful charges (both subscription + one-time)
    gross = 0
    refunded = 0
    daily_total: dict[str, int] = defaultdict(int)
    for ch in s.Charge.list(created={"gte": start_ts, "lt": end_ts}, limit=100).auto_paging_iter():
        if ch.status != "succeeded":
            continue
        amt = ch.amount or 0
        refund = getattr(ch, "amount_refunded", 0) or 0
        gross += amt
        refunded += refund
        net = amt - refund
        d = datetime.fromtimestamp(ch.created, tz=timezone.utc).date().isoformat()
        daily_total[d] += net

    # Subscription revenue from paid invoices
    sub_total = 0
    daily_sub: dict[str, int] = defaultdict(int)
    for inv in s.Invoice.list(created={"gte": start_ts, "lt": end_ts}, limit=100, status="paid").auto_paging_iter():
        amt = getattr(inv, "amount_paid", 0) or 0
        sub_total += amt
        d = datetime.fromtimestamp(inv.created, tz=timezone.utc).date().isoformat()
        daily_sub[d] += amt

    daily_rows = []
    cur = start
    while cur <= end:
        di = cur.isoformat()
        total_d = daily_total.get(di, 0)
        sub_d = min(daily_sub.get(di, 0), total_d)  # cap so non_sub never goes negative
        non_sub_d = total_d - sub_d
        daily_rows.append({
            "date": di,
            "subscription": sub_d / 100,
            "non_subscription": non_sub_d / 100,
            "total": total_d / 100,
        })
        cur += timedelta(days=1)

    net_total = gross - refunded
    sub_net = min(sub_total, net_total)

    return {
        "revenue_usd": net_total / 100,
        "gross_usd": gross / 100,
        "refunded_usd": refunded / 100,
        "subscription_usd": sub_net / 100,
        "non_subscription_usd": (net_total - sub_net) / 100,
        "daily": [{"date": r["date"], "revenue": r["total"]} for r in daily_rows],
        "daily_split": daily_rows,
    }


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def stripe_mrr_history(start: date, end: date) -> list[dict]:
    """Daily MRR snapshot computed from current + canceled subscriptions."""
    from stripe_client import get_client

    s = get_client()
    subs: list[dict] = []
    for status in ("active", "canceled"):
        for sub in s.Subscription.list(status=status, limit=100).auto_paging_iter():
            for item in sub["items"]["data"]:
                price = item.price
                recurring = getattr(price, "recurring", None)
                interval = getattr(recurring, "interval", "month") if recurring else "month"
                interval_count = getattr(recurring, "interval_count", 1) if recurring else 1
                unit_amount = getattr(price, "unit_amount", 0) or 0
                quantity = getattr(item, "quantity", 1) or 1
                monthly = _to_monthly(unit_amount, interval, interval_count, quantity)
                created = datetime.fromtimestamp(sub.created, tz=timezone.utc).date()
                ended_ts = getattr(sub, "ended_at", None) or getattr(sub, "canceled_at", None)
                ended = datetime.fromtimestamp(ended_ts, tz=timezone.utc).date() if ended_ts else None
                subs.append({"created": created, "ended": ended, "mrr": monthly})

    rows = []
    cur = start
    while cur <= end:
        mrr = sum(x["mrr"] for x in subs if x["created"] <= cur and (x["ended"] is None or x["ended"] >= cur))
        rows.append({"date": cur.isoformat(), "mrr": round(mrr, 2)})
        cur += timedelta(days=1)
    return rows


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def stripe_current_mrr() -> float:
    """Current MRR snapshot summed across all active subscriptions, normalized to monthly."""
    from stripe_client import get_client

    s = get_client()
    mrr = 0.0
    for sub in s.Subscription.list(status="active", limit=100).auto_paging_iter():
        for item in sub["items"]["data"]:
            price = item.price
            recurring = getattr(price, "recurring", None)
            interval = getattr(recurring, "interval", "month") if recurring else "month"
            interval_count = getattr(recurring, "interval_count", 1) if recurring else 1
            unit_amount = getattr(price, "unit_amount", 0) or 0
            quantity = getattr(item, "quantity", 1) or 1
            mrr += _to_monthly(unit_amount, interval, interval_count, quantity)
    return round(mrr, 2)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def stripe_charges_daily_by_amounts(start: date, end: date, amounts_cents: tuple[int, ...]) -> dict:
    """Total + per-day count of successful charges whose `amount` matches any target (in cents)."""
    from stripe_client import get_client

    s = get_client()
    start_ts = _date_to_ts(start)
    end_ts = _date_to_ts(end) + 86400
    targets = set(amounts_cents)

    daily: dict[str, int] = defaultdict(int)
    total = 0
    for ch in s.Charge.list(created={"gte": start_ts, "lt": end_ts}, limit=100).auto_paging_iter():
        if ch.status != "succeeded":
            continue
        if (ch.amount or 0) in targets:
            d = datetime.fromtimestamp(ch.created, tz=timezone.utc).date().isoformat()
            daily[d] += 1
            total += 1

    rows = []
    cur = start
    while cur <= end:
        di = cur.isoformat()
        rows.append({"date": di, "count": daily.get(di, 0)})
        cur += timedelta(days=1)
    return {"total": total, "daily": rows}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def stripe_revenue_by_product(start: date, end: date) -> list[dict]:
    """Sum invoice line items by product over the date range."""
    from stripe_client import get_client

    s = get_client()
    start_ts = _date_to_ts(start)
    end_ts = _date_to_ts(end) + 86400

    # Group by line item description (e.g. "Clearer Thinking Plus - Navigator").
    # Stripe's invoice line items have inconsistent price.product population across
    # SDK versions, but the description field is reliably present and human-readable.
    import re

    by_label: dict[str, float] = defaultdict(float)
    for inv in s.Invoice.list(
        created={"gte": start_ts, "lt": end_ts},
        limit=100,
        status="paid",
    ).auto_paging_iter():
        for line in inv.lines.auto_paging_iter():
            desc = getattr(line, "description", None) or "(unlabeled)"
            # Normalize to just the product name. Stripe descriptions are like:
            #   "1 × Clearer Thinking Plus - Navigator (at $99.00 / month)"
            # Strip leading "N × " quantity prefix and trailing "(at $... / interval)" pricing suffix.
            label = re.sub(r"^\d+\s*[×x]\s*", "", desc)
            label = re.sub(r"\s*\(at\s+\$.+?\)\s*$", "", label).strip() or desc
            line_amt = getattr(line, "amount", None) or 0
            if line_amt > 0:  # skip $0 lines (proration credits, etc.)
                by_label[label] += line_amt / 100

    out = [{"product": k, "revenue": round(v, 2)} for k, v in by_label.items()]
    out.sort(key=lambda r: r["revenue"], reverse=True)
    return out


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
        daily: dict[str, dict] = defaultdict(lambda: {"spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0.0})
        for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
            for row in batch.results:
                d_cost = row.metrics.cost_micros / 1_000_000
                cost += d_cost
                impr += row.metrics.impressions
                clicks += row.metrics.clicks
                conv += row.metrics.conversions
                d = row.segments.date
                daily[d]["spend"] += d_cost
                daily[d]["impressions"] += row.metrics.impressions
                daily[d]["clicks"] += row.metrics.clicks
                daily[d]["conversions"] += row.metrics.conversions

        return {
            "spend_usd": cost,
            "impressions": impr,
            "clicks": clicks,
            "conversions": conv,
            "daily": [{"date": d, **v} for d, v in sorted(daily.items())],
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


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def beehiiv_daily_new_subscribers(start: date, end: date) -> dict:
    """Daily count of new beehiiv subscriptions created in the window."""
    api_key = os.getenv("BEEHIIV_API_KEY", "").strip()
    pub_id = os.getenv("BEEHIIV_PUB_CLEARER_THINKING", "").strip()
    if not api_key or not pub_id:
        return {"total": 0, "daily": [], "error": "BEEHIIV_API_KEY missing"}

    headers = {"Authorization": f"Bearer {api_key}"}
    start_ts = _date_to_ts(start)
    end_ts = _date_to_ts(end) + 86400

    daily: dict[str, int] = defaultdict(int)
    page = 1
    while True:
        r = requests.get(
            f"{BEEHIIV_BASE}/publications/{pub_id}/subscriptions",
            headers=headers,
            params={
                "limit": 100,
                "page": page,
                "created_after": start_ts,
                "created_before": end_ts,
            },
        )
        if r.status_code != 200:
            break
        data = r.json()
        for sub in data.get("data", []):
            ts = sub.get("created")
            if isinstance(ts, int):
                d = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
                daily[d] += 1
            elif isinstance(ts, str):
                try:
                    d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
                    daily[d] += 1
                except ValueError:
                    pass
        if page >= data.get("total_pages", 1):
            break
        page += 1

    rows = []
    cur = start
    while cur <= end:
        di = cur.isoformat()
        rows.append({"date": di, "count": daily.get(di, 0)})
        cur += timedelta(days=1)
    return {"total": sum(daily.values()), "daily": rows, "error": None}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def beehiiv_engaged_readers() -> dict:
    """Subscriber count from the beehiiv segment 'Engaged Reades - Open > 40%' (their existing segment)."""
    api_key = os.getenv("BEEHIIV_API_KEY", "").strip()
    pub_id = os.getenv("BEEHIIV_PUB_CLEARER_THINKING", "").strip()
    if not api_key or not pub_id:
        return {"engaged": 0, "segment_name": None, "error": "BEEHIIV_API_KEY missing"}

    headers = {"Authorization": f"Bearer {api_key}"}
    target = "engaged reades - open > 40%"  # note: existing segment has typo "Reades"

    page = 1
    while True:
        r = requests.get(
            f"{BEEHIIV_BASE}/publications/{pub_id}/segments",
            headers=headers,
            params={"limit": 100, "page": page},
        )
        if r.status_code != 200:
            return {"engaged": 0, "segment_name": None, "error": f"HTTP {r.status_code}"}
        data = r.json()
        for seg in data.get("data", []):
            if seg.get("name", "").strip().lower() == target:
                return {
                    "engaged": int(seg.get("total_results", 0) or 0),
                    "segment_name": seg.get("name"),
                    "last_calculated": seg.get("last_calculated"),
                    "error": None,
                }
        if page >= data.get("total_pages", 1):
            break
        page += 1

    return {"engaged": 0, "segment_name": None, "error": "Segment 'Engaged Reades - Open > 40%' not found"}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def beehiiv_daily_rates(start: date, end: date) -> list[dict]:
    """Daily aggregated email rates (open / click / unsubscribe) computed from posts in the window."""
    api_key = os.getenv("BEEHIIV_API_KEY", "").strip()
    pub_id = os.getenv("BEEHIIV_PUB_CLEARER_THINKING", "").strip()
    if not api_key or not pub_id:
        return []

    headers = {"Authorization": f"Bearer {api_key}"}
    posts = []
    page = 1
    while True:
        r = requests.get(
            f"{BEEHIIV_BASE}/publications/{pub_id}/posts",
            headers=headers,
            params={"page": page, "limit": 100, "expand[]": "stats", "platform": "email", "status": "confirmed"},
        )
        if r.status_code != 200:
            return []
        data = r.json()
        posts.extend(data.get("data", []))
        if page >= data.get("total_pages", 1):
            break
        page += 1

    by_day: dict[str, dict[str, int]] = {}
    for p in posts:
        ts = p.get("publish_date")
        d: Optional[date] = None
        if isinstance(ts, int):
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        elif isinstance(ts, str):
            try:
                d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            except ValueError:
                pass
        if d is None or not (start <= d <= end):
            continue
        em = (p.get("stats", {}) or {}).get("email", {}) or {}
        sent = em.get("recipients", 0) or 0
        opens = em.get("opens", 0) or 0
        clicks = em.get("clicks", 0) or 0
        unsubs = em.get("unsubscribes", 0) or 0
        di = d.isoformat()
        bucket = by_day.setdefault(di, {"sent": 0, "opens": 0, "clicks": 0, "unsubs": 0})
        bucket["sent"] += sent
        bucket["opens"] += opens
        bucket["clicks"] += clicks
        bucket["unsubs"] += unsubs

    out = []
    for di in sorted(by_day):
        b = by_day[di]
        sent = b["sent"]
        out.append({
            "date": di,
            "open_rate": (b["opens"] / sent) if sent else 0,
            "click_rate": (b["clicks"] / sent) if sent else 0,
            "unsubscribe_rate": (b["unsubs"] / sent) if sent else 0,
        })
    return out
