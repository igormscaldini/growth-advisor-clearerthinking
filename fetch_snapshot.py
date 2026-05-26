"""Generate frontend/public/snapshot.json with current dashboard data.

Run locally:  python fetch_snapshot.py
On CI:        .github/workflows/fetch-snapshot.yml runs this every 30 minutes.

The snapshot pre-computes the 7d / 30d / 90d ranges plus prior periods for variance.
All fetches are wrapped so a single API failure doesn't kill the snapshot.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent


def _materialize_ci_secrets() -> None:
    """On CI, OAuth JSON blobs come in as env vars. Write them to ./secrets/ so the existing clients find them."""
    blobs = {
        "OAUTH_CLIENT_JSON": ROOT / "secrets" / "oauth-client.json",
        "GOOGLE_TOKEN_JSON": ROOT / "secrets" / "ga4-token.json",
    }
    for env_var, target in blobs.items():
        blob = os.environ.get(env_var, "").strip()
        if not blob:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blob)


_materialize_ci_secrets()

# Imports happen after secret materialization so client modules see the files at import time.
from data_layer import (  # noqa: E402
    beehiiv_daily_new_subscribers,
    beehiiv_daily_rates,
    beehiiv_engaged_readers,
    beehiiv_metrics,
    ga4_audience_metrics,
    ga4_daily_users_and_events,
    ga4_modules_finished_by_campaign,
    ga4_modules_finished_by_channel,
    google_ads_metrics,
    gsc_keyword_position,
    gsc_keyword_position_daily,
    stripe_active_subscriber_count,
    stripe_charges_daily_by_amounts,
    stripe_current_mrr,
    stripe_metrics,
    stripe_mrr_history,
    stripe_new_subscribers_monthly,
    stripe_revenue_by_category,
)

OUT = ROOT / "frontend" / "public" / "snapshot.json"

PRESETS = {"7d": 7, "30d": 30, "90d": 90}
COG_AMOUNTS = (3500, 1750)
PERSONALITY_AMOUNTS = (900,)

MANUAL_REVENUE_LAST_UPDATED = "2026-05-15"
MANUAL_REVENUE: dict[str, list[tuple[str, float]]] = {
    "MLA": [("ACE", 2_500.00), ("FarmKind", 2_500.00)],
    "Affiliates": [("Kitted Decks", 2_529.53)],
    "Newsletter Sponsorships": [("80,000 Hours", 4_200.00)],
    "Beehiiv Ad Network": [("Beehiiv", 431.85)],
}


def _safe(fn, *args, **kwargs):
    """Run fn; on failure log + return {"error": str}. Keeps one broken API from killing the snapshot."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"[warn] {fn.__name__} failed: {e}", file=sys.stderr)
        return {"error": str(e)}


def fetch_range(start: date, end: date) -> dict:
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        f = {
            "ga4": ex.submit(_safe, ga4_audience_metrics, start, end),
            "ga4_daily": ex.submit(_safe, ga4_daily_users_and_events, start, end),
            "stripe_m": ex.submit(_safe, stripe_metrics, start, end),
            "mrr_history": ex.submit(_safe, stripe_mrr_history, start, end),
            "bh": ex.submit(_safe, beehiiv_metrics, start, end),
            "bh_daily_rates": ex.submit(_safe, beehiiv_daily_rates, start, end),
            "new_subs_daily": ex.submit(_safe, beehiiv_daily_new_subscribers, start, end),
            "cog_sales": ex.submit(_safe, stripe_charges_daily_by_amounts, start, end, COG_AMOUNTS, False),
            "pdf_sales": ex.submit(_safe, stripe_charges_daily_by_amounts, start, end, PERSONALITY_AMOUNTS, True),
            "ads": ex.submit(_safe, google_ads_metrics, start, end),
            "modules_by_channel": ex.submit(_safe, ga4_modules_finished_by_channel, start, end),
            "modules_by_campaign": ex.submit(_safe, ga4_modules_finished_by_campaign, start, end),
            "kw_pos": ex.submit(_safe, gsc_keyword_position_daily, "personality test", start, end),
            "revenue_cat": ex.submit(_safe, stripe_revenue_by_category, start, end),
        }
        return {k: fut.result() for k, fut in f.items()}


def _scalar_or_default(v, default):
    """Unwrap _safe results: real values pass through, {"error": ...} becomes default."""
    if isinstance(v, dict) and "error" in v and len(v) == 1:
        return default
    return v


def main() -> None:
    today = date.today()
    print(f"[snapshot] {today.isoformat()} → starting...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        f_current_mrr = ex.submit(_safe, stripe_current_mrr)
        f_active_subs = ex.submit(_safe, stripe_active_subscriber_count)
        f_new_subs_monthly = ex.submit(_safe, stripe_new_subscribers_monthly)
        f_engaged = ex.submit(_safe, beehiiv_engaged_readers)
        f_keyword_overall = ex.submit(_safe, gsc_keyword_position, "personality test")
        current_mrr = _scalar_or_default(f_current_mrr.result(), 0.0)
        active_subs = _scalar_or_default(f_active_subs.result(), 0)
        new_subs_monthly = _scalar_or_default(f_new_subs_monthly.result(), [])
        engaged = f_engaged.result()
        keyword_overall = f_keyword_overall.result()

    periods = {}
    for label, days in PRESETS.items():
        start = today - timedelta(days=days - 1)
        end = today
        prior_end = start - timedelta(days=1)
        prior_start = prior_end - timedelta(days=days - 1)
        print(f"[snapshot] {label}: {start} → {end} (vs {prior_start} → {prior_end})")
        periods[label] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "prior_start": prior_start.isoformat(),
            "prior_end": prior_end.isoformat(),
            "days": days,
            "current": fetch_range(start, end),
            "prior": fetch_range(prior_start, prior_end),
        }

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": today.isoformat(),
        "snapshots": {
            "current_mrr": current_mrr,
            "active_subscribers": active_subs,
            "engaged_readers": engaged,
            "keyword_overall": keyword_overall,
            "new_subscribers_monthly_alltime": new_subs_monthly if isinstance(new_subs_monthly, list) else [],
        },
        "periods": periods,
        "manual_revenue": {
            "last_updated": MANUAL_REVENUE_LAST_UPDATED,
            "lines": {
                label: [{"source": src, "amount": amt} for src, amt in items]
                for label, items in MANUAL_REVENUE.items()
            },
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, default=str, indent=2))
    print(f"[snapshot] wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
