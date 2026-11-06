"""Pull the raw data for analysis.py into data/ (gitignored: it holds email hashes and reader feedback).

    .venv/bin/python reports/supplement_paradox_paywall_results_2026-11-06_src/fetch_data.py

Sources: beehiiv v2 API (one request per post: the LIST endpoint truncates `stats.clicks` to a few
dozen rows, the single-post endpoint returns them all), GuidedTrack run exports (38912 pitch page,
38913 full version, 38551 article ratings), Stripe (Checkout Sessions of the paywall Payment Link,
subscriptions since July) and GA4. Emails never reach disk: only their MD5, the same hash beehiiv
puts in the paywall link. The pitch-page export also carries the members-only access key, so only
the columns the analysis needs are kept.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.chdir(ROOT)  # stripe_client and ga4_client read .env and secrets/ relative to the repo root

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
logging.disable(logging.WARNING)

import analysis  # noqa: E402
import data_layer as dl  # noqa: E402

DATA = HERE / "data"
PAYMENT_LINK = "plink_1UPnyKAoBs2tgN9pGuYyXDzo"
GT_PITCH, GT_FULL, GT_RATINGS = 38912, 38913, 38551
FEEDBACK_Q = "(Optional) What feedback would you like to give about this article? (7f2fv5r)"


def md5(email: str | None) -> str | None:
    return hashlib.md5(email.strip().lower().encode()).hexdigest() if email else None


def ts(epoch: int | None) -> str | None:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if epoch else None


def beehiiv_posts() -> dict:
    h = {"Authorization": f"Bearer {os.environ['BEEHIIV_API_KEY'].strip()}"}
    pub = os.environ["BEEHIIV_PUB_CLEARER_THINKING"].strip()
    ids = list(analysis.SP_POSTS) + [p for ps in analysis.BASELINE_EDITIONS.values() for p in ps]
    out = {}
    for pid in ids:
        r = dl._beehiiv_get(f"{dl.BEEHIIV_BASE}/publications/{pub}/posts/{pid}", headers=h,
                            params={"expand[]": ["stats"]}, timeout=(10, 120))
        r.raise_for_status()
        d = r.json()["data"]
        out[pid] = {k: d.get(k) for k in ("id", "subject_line", "publish_date", "send_targets", "stats")}
    return out


def gt_export(program_id: int) -> list[dict]:
    auth = (os.environ["GUIDED_TRACK_USERNAME"], os.environ["GUIDED_TRACK_PASSWORD"])
    r = requests.get(f"https://www.guidedtrack.com/programs/{program_id}/exports?export_format=csv",
                     auth=auth, timeout=(10, 300))
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def stripe_pull() -> tuple[list, list]:
    from stripe_client import get_client
    stripe = get_client()
    sessions = []
    for s in stripe.checkout.Session.list(payment_link=PAYMENT_LINK, limit=100).auto_paging_iter():
        d = s.to_dict()
        sessions.append({"id": d["id"], "created": ts(d["created"]), "status": d["status"],
                         "ref": d.get("client_reference_id"), "sub": d.get("subscription"),
                         "email_md5": md5((d.get("customer_details") or {}).get("email"))})
    start = int(analysis.BASELINE_START.timestamp())
    subs = []
    for s in stripe.Subscription.list(status="all", created={"gte": start}, limit=100,
                                      expand=["data.customer"]).auto_paging_iter():
        d = s.to_dict()
        price = d["items"]["data"][0]["price"]
        cust = d.get("customer") if isinstance(d.get("customer"), dict) else {}
        subs.append({"id": d["id"], "created": ts(d["created"]), "status": d["status"],
                     "canceled_at": ts(d.get("canceled_at")), "lookup": price.get("lookup_key"),
                     "amount": price.get("unit_amount"), "email_md5": md5(cust.get("email"))})
    return sessions, subs


def ga4_pull() -> dict:
    from ga4_client import get_client, property_path
    from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest
    client = get_client()

    def totals(path_contains: str) -> tuple[int, int]:
        req = RunReportRequest(
            property=property_path(), dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"), Metric(name="totalUsers")],
            date_ranges=[DateRange(start_date=analysis.SEND_START.strftime("%Y-%m-%d"), end_date="today")],
            dimension_filter=FilterExpression(filter=Filter(field_name="pagePath", string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.CONTAINS, value=path_contains))))
        rows = client.run_report(req).rows
        return (sum(int(r.metric_values[0].value) for r in rows), sum(int(r.metric_values[1].value) for r in rows))

    views, users = totals("/post/the-supplement-paradox")
    _, pitch_users = totals("/members-only-content/")
    return {"web_post_views": views, "web_post_users": users, "pitch_page_users": pitch_users}


def main() -> None:
    DATA.mkdir(exist_ok=True)

    def save(name: str, obj) -> None:
        (DATA / name).write_text(json.dumps(obj, ensure_ascii=False))
        print(f"{name}: {len(obj)} rows")

    save("beehiiv_posts.json", beehiiv_posts())
    save("gt_pitch_runs.json", [{"t": r["Time Started (UTC)"], "src": r.get("src") or "", "h": r.get("h") or "",
                                 "isMember": r.get("isMember") or "", "emailMember": r.get("emailMember") or ""}
                                for r in gt_export(GT_PITCH)])
    save("gt_full_version_runs.json", [{"t": r["Time Started (UTC)"], "src": r.get("src") or "", "has_key": bool(r.get("k"))}
                                       for r in gt_export(GT_FULL)])
    save("gt_ratings.json", [{"t": r["Time Started (UTC)"], "article": r.get("article") or "",
                              "final_rating": r.get("final_rating") or "",
                              "feedback": (r.get(FEEDBACK_Q) or r.get("feedback") or "").strip()}
                             for r in gt_export(GT_RATINGS)])
    sessions, subs = stripe_pull()
    save("stripe_sessions.json", sessions)
    save("stripe_subscriptions.json", subs)
    save("ga4.json", ga4_pull())
    # Where the goals stand today (GOALS.md: 100 active subscribers, $5,000 MRR), dashboard definitions.
    save("context.json", {"active_subscribers": dl.stripe_active_subscriber_count(), "mrr_usd": round(dl.stripe_current_mrr(), 2)})


if __name__ == "__main__":
    main()
