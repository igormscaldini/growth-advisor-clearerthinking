"""Sanity-check report: confirm Google Ads access works end-to-end."""
from google.ads.googleads.errors import GoogleAdsException

from google_ads_client import CUSTOMER_ID, get_client


QUERY = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      metrics.cost_micros,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions
    FROM campaign
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.cost_micros DESC
    LIMIT 10
"""


def main() -> None:
    if not CUSTOMER_ID:
        raise SystemExit("GOOGLE_ADS_CUSTOMER_ID not set in .env")

    client = get_client()
    svc = client.get_service("GoogleAdsService")

    print(f"Customer ID:  {CUSTOMER_ID}")
    print("Window:       last 30 days\n")
    print("--- Top 10 campaigns by spend ---")
    print(f"  {'cost':>10}  {'impr':>10}  {'clicks':>8}  {'conv':>6}  status      campaign")

    total_cost = 0.0
    total_impr = 0
    total_clicks = 0
    total_conv = 0.0
    rows_seen = 0

    try:
        for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=QUERY):
            for row in batch.results:
                cost = row.metrics.cost_micros / 1_000_000
                impr = row.metrics.impressions
                clicks = row.metrics.clicks
                conv = row.metrics.conversions
                status = row.campaign.status.name
                name = row.campaign.name
                total_cost += cost
                total_impr += impr
                total_clicks += clicks
                total_conv += conv
                rows_seen += 1
                print(f"  ${cost:>8,.2f}  {impr:>10,}  {clicks:>8,}  {conv:>6.1f}  {status:<10}  {name}")
    except GoogleAdsException as e:
        print("\nGoogle Ads API rejected the request:")
        for err in e.failure.errors:
            print(f"  - {err.error_code}")
            print(f"    {err.message}")
        if any("DEVELOPER_TOKEN" in str(err.error_code) for err in e.failure.errors):
            print("\n  This usually means your developer token is still in 'Test access' mode.")
            print("  Real-account queries require Basic access approval (1–2 business days).")
        raise SystemExit(1)

    if rows_seen == 0:
        print("  (no campaign rows returned for the last 30 days)")
    else:
        print(f"\n  TOTAL: ${total_cost:,.2f} | {total_impr:,} impressions | {total_clicks:,} clicks | {total_conv:.1f} conversions")

    print("\nGoogle Ads connection OK.")


if __name__ == "__main__":
    main()
