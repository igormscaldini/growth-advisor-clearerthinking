"""Connection verification — pulls one concrete, easily cross-checkable data point per source."""
import os
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()


# ---------- GA4 ----------
def verify_ga4() -> dict:
    from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
    from ga4_client import get_client, property_path

    yesterday = date.today() - timedelta(days=1)
    req = RunReportRequest(
        property=property_path(),
        date_ranges=[DateRange(start_date=str(yesterday), end_date=str(yesterday))],
        metrics=[
            Metric(name="totalUsers"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
        ],
    )
    resp = get_client().run_report(req)
    vals = [v.value for v in resp.rows[0].metric_values] if resp.rows else ["0", "0", "0"]
    return {
        "window": f"yesterday ({yesterday})",
        "users": vals[0],
        "sessions": vals[1],
        "pageviews": vals[2],
        "verify_at": f"https://analytics.google.com → Reports → set date to {yesterday}",
    }


# ---------- GSC ----------
def verify_gsc() -> dict:
    from gsc_client import SITE_URL, get_client

    # GSC has ~2-3 day lag, so go back 4 days for a settled value
    target = date.today() - timedelta(days=4)
    resp = get_client().searchanalytics().query(
        siteUrl=SITE_URL,
        body={"startDate": str(target), "endDate": str(target), "dimensions": [], "rowLimit": 1},
    ).execute()
    rows = resp.get("rows", [])
    clicks = int(rows[0]["clicks"]) if rows else 0
    impr = int(rows[0]["impressions"]) if rows else 0
    return {
        "window": f"single day ({target})",
        "site": SITE_URL,
        "clicks": clicks,
        "impressions": impr,
        "verify_at": f"GSC → Performance on Search results → set date range to {target}–{target}",
    }


# ---------- Stripe ----------
def verify_stripe() -> dict:
    from stripe_client import get_client

    s = get_client()
    active = sum(1 for _ in s.Subscription.list(status="active", limit=100).auto_paging_iter())
    return {
        "snapshot": "right now",
        "active_subscriptions": active,
        "verify_at": "https://dashboard.stripe.com/subscriptions (filter: Active)",
    }


# ---------- Google Sheets ----------
def verify_sheets() -> dict:
    from sheets_client import get_client

    sheet_id = os.getenv("SHEETS_NEWSLETTER_FEEDBACK_ID")
    svc = get_client()
    rows = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="'Data'!A:F"
    ).execute().get("values", [])
    # Sheet structure: row 1 = "Means", row 2 = headers, row 3+ = data
    data_rows = [r for r in rows[2:] if r and r[0]]
    most_recent = data_rows[0] if data_rows else []
    return {
        "snapshot": "right now",
        "data_row_count": len(data_rows),
        "most_recent_title": most_recent[0] if most_recent else "(none)",
        "most_recent_date": most_recent[2] if len(most_recent) > 2 else "(unknown)",
        "most_recent_avg_rating": most_recent[5] if len(most_recent) > 5 else "(unknown)",
        "verify_at": "Open the sheet → 'Data' tab → row 3 (the topmost data row)",
    }


# ---------- Google Ads ----------
def verify_google_ads() -> dict:
    from google_ads_client import CUSTOMER_ID, get_client

    yesterday = date.today() - timedelta(days=1)
    query = f"""
        SELECT
          customer.descriptive_name,
          metrics.cost_micros,
          metrics.impressions,
          metrics.clicks
        FROM customer
        WHERE segments.date = '{yesterday}'
    """
    svc = get_client().get_service("GoogleAdsService")
    cost = 0.0
    impr = 0
    clicks = 0
    name = ""
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
        for row in batch.results:
            cost += row.metrics.cost_micros / 1_000_000
            impr += row.metrics.impressions
            clicks += row.metrics.clicks
            name = row.customer.descriptive_name
    return {
        "window": f"yesterday ({yesterday})",
        "account": name,
        "cost_usd": round(cost, 2),
        "impressions": impr,
        "clicks": clicks,
        "verify_at": f"https://ads.google.com → Campaigns → date filter {yesterday}",
    }


if __name__ == "__main__":
    import json

    results = {
        "GA4": verify_ga4(),
        "GSC": verify_gsc(),
        "Stripe": verify_stripe(),
        "Sheets": verify_sheets(),
        "Google Ads": verify_google_ads(),
    }
    print(json.dumps(results, indent=2))
