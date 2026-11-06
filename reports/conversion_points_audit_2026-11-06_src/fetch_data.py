"""Fetch the raw inputs of the conversion points audit (GA4, GuidedTrack, Stripe).

    .venv/bin/python reports/conversion_points_audit_2026-11-06_src/fetch_data.py --raw-dir <dir outside the repo>

The raw files hold email addresses and per-visit browser fingerprints, and this repo is PUBLIC,
so --raw-dir is required and must NOT be inside the repo. `analysis.py` turns the raw files into
`datapoints.json` (aggregates only), which is what gets committed.
"""
import argparse
import csv
import html
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis import (WINDOW_START, WINDOW_END, LOOKBACK_START, STRIPE_START, LANDING_PAGES,  # noqa: E402
                      CAMPAIGN_LANDINGS, FAB_PERIODS)

GT_BASE = "https://www.guidedtrack.com"
GT_EXPORTS = {"subscribe": 34235, "cognitive_intro": 31137}
FUNNEL_EVENTS = ["Viewed Privacy Policy", "Accepted Privacy Policy", "Reached Email Ask", "Submitted Email", "Finished Exercise"]


# ---------------------------------------------------------------- GA4
def _ga():
    from ga4_client import get_client, property_path
    from google.analytics.data_v1beta import types as T

    client = get_client()

    def flt(dim, value, match="EXACT"):
        return T.FilterExpression(filter=T.Filter(field_name=dim, string_filter=T.Filter.StringFilter(
            match_type=getattr(T.Filter.StringFilter.MatchType, match), value=value)))

    def in_list(dim, values):
        return T.FilterExpression(filter=T.Filter(field_name=dim, in_list_filter=T.Filter.InListFilter(values=list(values))))

    def all_of(*fs):
        return T.FilterExpression(and_group=T.FilterExpressionList(expressions=list(fs)))

    def any_of(*fs):
        return T.FilterExpression(or_group=T.FilterExpressionList(expressions=list(fs)))

    def neg(f):
        return T.FilterExpression(not_expression=f)

    def run(dims, mets, start, end, filt=None):
        rows, offset = [], 0
        while True:
            req = T.RunReportRequest(property=property_path(), dimensions=[T.Dimension(name=d) for d in dims],
                                     metrics=[T.Metric(name=m) for m in mets],
                                     date_ranges=[T.DateRange(start_date=start, end_date=end)], limit=250000, offset=offset)
            if filt is not None:
                req.dimension_filter = filt
            resp = client.run_report(req)
            for r in resp.rows:
                row = {d: v.value for d, v in zip(dims, r.dimension_values)}
                for m, v in zip(mets, r.metric_values):
                    row[m] = float(v.value) if "." in v.value else int(v.value)
                rows.append(row)
            offset += len(resp.rows)
            if not resp.rows or offset >= resp.row_count:
                return rows

    return run, flt, in_list, all_of, any_of, neg


def fetch_ga4():
    run, flt, in_list, all_of, any_of, neg = _ga()
    W = (WINDOW_START, WINDOW_END)
    www = flt("hostName", "www.clearerthinking.org")
    programs = flt("hostName", "programs.clearerthinking.org")
    lp = in_list("pagePath", LANDING_PAGES)
    pv = flt("eventName", "page_view")
    out = {}
    lp_mets = ["totalUsers", "sessions", "engagedSessions", "screenPageViews", "userEngagementDuration"]
    out["lp_daily"] = run(["date", "pagePath"], lp_mets, *W, lp)
    out["lp_totals"] = run(["pagePath"], lp_mets, *W, lp)
    out["lp_sources"] = run(["pagePath", "sessionSource", "sessionMedium", "sessionManualCampaignName"], lp_mets, *W, lp)
    # Event-level landings: GA4 keeps a session's FIRST campaign, so a utm link clicked mid-session
    # (floating button, product grid) is invisible in session dimensions. The page URL is not.
    out["utm_landings"] = run(["date", "pagePath", "pageLocation", "sessionSource"], ["screenPageViews"], *W,
                              all_of(pv, flt("pageLocation", "utm_campaign=", "CONTAINS")))
    # Distinct people per tagged link. Hits whose session source is "(not set)" never opened a real
    # session (link scanners, bots: 3 engaged sessions out of ~1,200 on /coaching), so they are split out.
    bot = flt("sessionSource", "(not set)")
    out["campaign_landings"] = []
    for key, campaign, path in CAMPAIGN_LANDINGS:
        for period, (a, b) in {"window": W, **(FAB_PERIODS if key == "tools_fab" else {})}.items():
            base = all_of(pv, flt("pagePath", path), flt("pageLocation", f"utm_campaign={campaign}", "CONTAINS"))
            clean = run([], ["totalUsers", "screenPageViews", "sessions"], a, b, all_of(base, neg(bot)))
            bots = run([], ["screenPageViews"], a, b, all_of(base, bot))
            row = clean[0] if clean else {"totalUsers": 0, "screenPageViews": 0, "sessions": 0}
            out["campaign_landings"].append({"key": key, "period": period, "users": row["totalUsers"], "views": row["screenPageViews"],
                                             "sessions": row["sessions"], "bot_views": bots[0]["screenPageViews"] if bots else 0})
    # GA4 cuts linkUrl at 100 characters, so the campaign value arrives truncated ("tools_float").
    out["fab_tools_clicks"] = {}
    for period, (a, b) in FAB_PERIODS.items():
        r = run([], ["eventCount", "totalUsers"], a, b, all_of(flt("eventName", "click"), programs,
                                                                flt("linkUrl", "utm_campaign=tools_float", "CONTAINS")))
        out["fab_tools_clicks"][period] = r[0] if r else {"eventCount": 0, "totalUsers": 0}
    out["www_users_ex_coaching"] = run([], ["totalUsers"], *W, all_of(www, neg(flt("pagePath", "/coaching"))))
    out["www_daily_ex_coaching"] = run(["date"], ["totalUsers"], *W, all_of(www, neg(flt("pagePath", "/coaching"))))
    not_hidden = neg(flt("pagePath", "/unanswered-questions-in-psychology", "BEGINS_WITH"))
    out["programs_daily"] = run(["date", "deviceCategory"], ["totalUsers"], *W, all_of(programs, not_hidden))
    for name, (a, b) in FAB_PERIODS.items():
        out[f"programs_users_{name}"] = run([], ["totalUsers"], a, b, all_of(programs, not_hidden))
        out[f"programs_pages_{name}"] = run(["pagePath"], ["totalUsers"], a, b, all_of(programs, not_hidden))
    out["clicks_to_www"] = run(["date", "pagePath", "linkUrl"], ["eventCount", "totalUsers"], *W, all_of(
        flt("eventName", "click"), programs,
        any_of(flt("linkUrl", "clearerthinking.org/coaching", "CONTAINS"), flt("linkUrl", "clearerthinking.org/plus", "CONTAINS"))))
    out["tool_events"] = run(["pagePath", "eventName"], ["eventCount", "totalUsers"], *W,
                             all_of(programs, in_list("eventName", FUNNEL_EVENTS)))
    out["tool_events_monthly"] = run(["yearMonth", "pagePath", "eventName"], ["eventCount", "totalUsers"], "2026-01-01", WINDOW_END,
                                     all_of(flt("pagePath", "/personality-test.html"), in_list("eventName", FUNNEL_EVENTS)))
    # Where PDF-page visitors come from (previous page), and what the report-finder page leads to.
    out["pdf_page_referrers"] = run(["pagePath", "pageReferrer"], ["screenPageViews", "totalUsers"], *W,
                                    all_of(pv, flt("pagePath", "/personality-test-pdf-generator", "BEGINS_WITH")))
    out["pdf_events"] = run(["eventName", "pagePath"], ["eventCount", "totalUsers"], *W,
                            all_of(programs, any_of(flt("pagePath", "/personality-test-pdf-generator", "BEGINS_WITH"),
                                                    flt("pagePath", "/getmyreport.html"))))
    fp = ["city", "deviceCategory", "browser", "operatingSystem", "screenResolution"]
    out["purchase_events"] = run(["dateHourMinute"] + fp + ["sessionSourceMedium", "sessionManualCampaignName"], ["eventCount"],
                                 LOOKBACK_START, WINDOW_END, flt("eventName", "plus_sign_up"))
    out["lp_views_fp"] = run(["dateHourMinute", "pagePath", "pageLocation"] + fp, ["screenPageViews"], LOOKBACK_START, WINDOW_END,
                             all_of(pv, in_list("pagePath", ["/coaching", "/plus"])))
    return out


# ---------------------------------------------------------------- GuidedTrack
def fetch_gt_export(program_id, dest):
    import requests
    from dotenv import dotenv_values

    env = dotenv_values(ROOT / ".env")
    r = requests.get(f"{GT_BASE}/programs/{program_id}/exports?export_format=csv", stream=True, timeout=3600,
                     auth=(env["GUIDED_TRACK_USERNAME"], env["GUIDED_TRACK_PASSWORD"]))
    r.raise_for_status()
    r.raw.decode_content = True
    csv.field_size_limit(10 ** 9)
    lines = (line.replace("\x00", "") for line in io.TextIOWrapper(r.raw, encoding="utf-8", errors="replace", newline=""))
    n = 0
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        for row in csv.reader(lines):
            w.writerow(row)
            n += 1
    return n - 1


# ---------------------------------------------------------------- Stripe
def fetch_stripe():
    from stripe_client import get_client

    s = get_client()
    t0 = int(datetime.fromisoformat(STRIPE_START).replace(tzinfo=timezone.utc).timestamp())

    def iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None

    def md(o):
        return (o.to_dict() if hasattr(o, "to_dict") else dict(o)) if o else {}

    subs = []
    for sub in s.Subscription.list(status="all", created={"gte": t0}, limit=100, expand=["data.customer"]).auto_paging_iter():
        price = sub["items"].data[0].price
        cust = sub.customer
        subs.append({"id": sub.id, "created": iso(sub.created), "ended": iso(sub.ended_at), "status": sub.status,
                     "email": getattr(cust, "email", None), "amount": price.unit_amount, "product": price.product,
                     "cancel_reason": md(sub.cancellation_details).get("reason")})
    names = {pid: s.Product.retrieve(pid).name for pid in {x["product"] for x in subs}}
    for x in subs:
        x["product_name"] = names[x["product"]]
    charges = [{"id": ch.id, "created": iso(ch.created), "amount": ch.amount, "refunded": ch.amount_refunded, "status": ch.status,
                "desc": ch.description, "pi": ch.payment_intent,
                "email": (ch.billing_details.email if ch.billing_details else None) or ch.receipt_email}
               for ch in s.Charge.list(created={"gte": t0}, limit=100).auto_paging_iter()]
    sessions = [{"id": cs.id, "created": iso(cs.created), "mode": cs.mode, "status": cs.status, "amount_total": cs.amount_total,
                 "email": (cs.customer_details.email if cs.customer_details else None) or cs.customer_email,
                 "success_url": cs.success_url, "metadata": md(cs.metadata), "pi": cs.payment_intent, "subscription": cs.subscription}
                for cs in s.checkout.Session.list(created={"gte": t0}, limit=100).auto_paging_iter()]
    return {"subs": subs, "charges": charges, "sessions": sessions}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--only", choices=["ga4", "gt", "stripe"], action="append")
    a = ap.parse_args()
    raw = Path(a.raw_dir).resolve()
    if ROOT in raw.parents or raw == ROOT:
        sys.exit("--raw-dir must be outside the (public) repo: the raw files hold personal data")
    raw.mkdir(parents=True, exist_ok=True)
    only = a.only or ["ga4", "gt", "stripe"]
    if "ga4" in only:
        ga = fetch_ga4()
        (raw / "ga4.json").write_text(json.dumps(ga))
        print("ga4:", {k: len(v) for k, v in ga.items()})
    if "gt" in only:
        for name, pid in GT_EXPORTS.items():
            print("gt", name, fetch_gt_export(pid, raw / f"gt_{name}.csv"), "runs")
    if "stripe" in only:
        st = fetch_stripe()
        (raw / "stripe.json").write_text(json.dumps(st))
        print("stripe:", {k: len(v) for k, v in st.items()})


if __name__ == "__main__":
    main()
