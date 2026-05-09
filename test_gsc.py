"""Sanity-check report: confirm Search Console access works end-to-end."""
from datetime import date, timedelta

from gsc_client import SITE_URL, get_client, list_sites


def main() -> None:
    svc = get_client()

    # --- Discover available properties ---
    sites = list_sites()
    print("--- Properties this account can access ---")
    for s in sites:
        print(f"  {s['permissionLevel']:<22}  {s['siteUrl']}")

    # --- Pick the property to query ---
    target = SITE_URL
    if not target:
        # Auto-pick a clearerthinking property if env is unset
        candidates = [s["siteUrl"] for s in sites if "clearerthinking" in s["siteUrl"].lower()]
        if not candidates:
            raise SystemExit("No clearerthinking property found and GSC_SITE_URL is empty.")
        target = candidates[0]
        print(f"\n(GSC_SITE_URL not set — defaulting to {target})")

    print(f"\nQuerying: {target}")

    # --- Last 7 days vs preceding 7 days, with 3-day data lag ---
    today = date.today()
    end = today - timedelta(days=3)
    start = end - timedelta(days=6)
    window = f"{start} to {end}"

    # Top queries
    print(f"\n--- Top 10 queries ({window}) ---")
    resp = svc.searchanalytics().query(
        siteUrl=target,
        body={
            "startDate": str(start),
            "endDate": str(end),
            "dimensions": ["query"],
            "rowLimit": 10,
            "orderBy": [{"field": "clicks", "descending": True}],
        },
    ).execute()
    print(f"  {'clicks':>8}  {'impr':>8}  {'ctr':>6}  {'pos':>5}  query")
    for row in resp.get("rows", []):
        q = row["keys"][0]
        clicks = row["clicks"]
        impr = row["impressions"]
        ctr = row["ctr"] * 100
        pos = row["position"]
        print(f"  {int(clicks):>8}  {int(impr):>8}  {ctr:>5.1f}%  {pos:>5.1f}  {q}")

    # Top pages
    print(f"\n--- Top 10 pages ({window}) ---")
    resp = svc.searchanalytics().query(
        siteUrl=target,
        body={
            "startDate": str(start),
            "endDate": str(end),
            "dimensions": ["page"],
            "rowLimit": 10,
            "orderBy": [{"field": "clicks", "descending": True}],
        },
    ).execute()
    print(f"  {'clicks':>8}  {'impr':>8}  {'ctr':>6}  {'pos':>5}  page")
    for row in resp.get("rows", []):
        p = row["keys"][0]
        clicks = row["clicks"]
        impr = row["impressions"]
        ctr = row["ctr"] * 100
        pos = row["position"]
        print(f"  {int(clicks):>8}  {int(impr):>8}  {ctr:>5.1f}%  {pos:>5.1f}  {p}")

    print("\nGSC connection OK.")


if __name__ == "__main__":
    main()
