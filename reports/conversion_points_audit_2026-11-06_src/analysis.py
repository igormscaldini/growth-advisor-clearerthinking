"""Pure functions + the datapoint builder for the conversion points audit.

Everything here works on plain dicts/lists so it can be unit-tested with synthetic data
(tests/test_conversion_points_audit.py). `build_datapoints(raw_dir)` reads the raw files written
by fetch_data.py and returns aggregates only (no emails, no fingerprints).
"""
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

WINDOW_START, WINDOW_END = "2026-08-14", "2026-11-05"   # 12 full weeks
LOOKBACK_START = "2026-07-15"                             # 30 days of page views before the window
STRIPE_START = "2026-07-01"
GA4_TZ = ZoneInfo("America/New_York")                     # the GA4 property clock
PDF_PATHS = ["/personality-test-pdf-generator/", "/personality-test-pdf-generator"]
LANDING_PAGES = ["/coaching", "/plus", "/cognitive-test-intro.html", "/getmyreport.html"] + PDF_PATHS
TOOLS_FAB_LIVE, WAVE_END = "2026-10-21", "2026-10-23"    # tools button went live mid viral wave
FAB_PERIODS = {"fab_all": (TOOLS_FAB_LIVE, WINDOW_END), "fab_wave": (TOOLS_FAB_LIVE, WAVE_END), "fab_steady": ("2026-10-24", WINDOW_END)}
# (key, utm_campaign, landing page) of every tagged on-site promotion
CAMPAIGN_LANDINGS = [
    ("www_fab", "coaching_floating_button", "/coaching"), ("tools_fab", "tools_floating_button", "/coaching"),
    ("grid_pdf", "ct_product_grid_upt_pdf", "/getmyreport.html"), ("grid_cognitive", "ct_product_grid_cognitive", "/cognitive-test-intro.html"),
    ("grid_plus", "ct_product_grid_plus", "/plus"), ("grid_coaching", "ct_product_grid_coaching", "/coaching"),
    ("end_banner_plus", "end_of_tools_banner", "/plus"), ("utt_cta", "coaching_cta_unique_traits", "/coaching"),
]
UNLINKED_ADS_CAMPAIGN = "20999008925"                     # Google Ads campaign seen on the cognitive page, not in CT's readable Ads account
TEST_EMAIL_RE = re.compile(r"igormscaldini|joshrcastle|b\.cobeta|@clearerthinking\.org|sparkwave|\+test|healthcheck", re.I)
TIER_BY_AMOUNT = {900: "supporter", 2900: "explorer", 9900: "navigator", 17900: "navigator"}
TOUCH_LOOKBACK_DAYS = 3
ARTICLE_PAYWALL_FIRST_SEND = "2026-10-16 12:57:00"       # checkouts on the members-only article before this are team tests


# ------------------------------------------------------------------ small helpers
def pct(k, n, digits=2):
    """k/n as a percentage, None when n is 0."""
    return round(100.0 * k / n, digits) if n else None


def wilson(k, n, z=1.96):
    """Wilson 95% interval for a proportion, as percentages (lo, hi). (None, None) when n is 0."""
    if not n:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * max(0.0, mid - half), 2), round(100 * min(1.0, mid + half), 2))


def rate(k, n):
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": pct(k, n), "lo": lo, "hi": hi}


def url_param(url, name):
    """First value of a query parameter in a URL, or None."""
    try:
        vals = parse_qs(urlsplit(url or "").query).get(name)
    except ValueError:
        return None
    return vals[0] if vals else None


def campaign_is(value, target):
    """True when a utm_campaign value is `target`, allowing for GA4's 100-character cut of linkUrl
    (a truncated value is a prefix of the target, at least 7 characters long)."""
    value = (value or "").lower()
    return value == target or (len(value) >= 7 and target.startswith(value))


def week_of(day):
    """Monday (ISO date) of the week containing `day` ('YYYY-MM-DD' or 'YYYYMMDD')."""
    d = datetime.strptime(day.replace("-", "")[:8], "%Y%m%d").date()
    return (d - timedelta(days=d.weekday())).isoformat()


def is_test_email(email):
    return bool(email and TEST_EMAIL_RE.search(email))


def ga_minute_to_utc(dhm):
    """GA4 dateHourMinute ('YYYYMMDDHHMM', property clock) -> aware UTC datetime."""
    return datetime.strptime(dhm, "%Y%m%d%H%M").replace(tzinfo=GA4_TZ).astimezone(timezone.utc)


def parse_utc(ts):
    return datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def source_group(source, medium, campaign):
    """Bucket a GA4 session source / medium / campaign into a readable channel."""
    s, m, c = (source or "").lower(), (medium or "").lower(), (campaign or "").lower()
    if "floating_button" in c:
        return "Floating buttons"
    if c.startswith("ct_product_grid"):
        return "Product grid"
    if s in ("tools", "programs", "unique_traits", "dashboard", "site", "website", "homepage") or m in ("tool_report", "menu", "my_plan"):
        return "Other on-site links"
    if "email" in m or "newsletter" in m or any(x in s for x in ("beehiiv", "behiiv", "mailgun", "join1440", "mail.")):
        return "Email"
    if m == "cpc":
        return "Paid ads"
    if m == "organic":
        return "Organic search"
    if s == "(direct)":
        return "Direct"
    if s in ("(not set)", "(data not available)"):
        return "Unattributed"
    if m == "referral" or "ai-assistant" in m:
        return "Referral"
    return "Other"


# ------------------------------------------------------------------ GuidedTrack: CT+ subscribe program
def subscribe_run(row):
    """Normalise one run of GT program 34235. Returns None for health-check and team test runs."""
    email = row.get("email") or row.get("raw_email") or ""
    if row.get("src") == "healthcheck" or is_test_email(email):
        return None
    return {
        "time": row["Time Started (UTC)"],
        "plan": (row.get("p") or row.get("selectedPlan") or row.get("selected_plan") or "unknown").lower(),
        "gave_email": bool(email),
        "reached_checkout": (row.get("wasRedirected") or row.get("was_redirected")) == "1",
        "already_member": row.get("status") == "active",
    }


# ------------------------------------------------------------------ Stripe
def classify_session(s):
    """(product, is_real) for a Stripe Checkout Session dict."""
    url = s.get("success_url") or ""
    email = s.get("email") or (s.get("metadata") or {}).get("user_email")
    real = not is_test_email(email)
    amount = s.get("amount_total")
    if s.get("mode") == "subscription":
        if "members-only-content" in url:
            return "supporter_article", real
        tier = (s.get("metadata") or {}).get("product_key") or TIER_BY_AMOUNT.get(amount)
        return (tier if tier in ("supporter", "explorer", "navigator") else "other"), real
    if "to8e8we" in url and amount in (3500, 1750):
        return "cognitive", real
    if "craftmypdf" in url and amount == 900:
        return "pdf", real
    return "other", real


def ended_within_a_day(sub):
    """The repo's rule for team test subscriptions: cancelled within a day of being created
    (it has caught every test so far with no false positive; real quick cancellations take days)."""
    return bool(sub.get("ended")) and (parse_utc(sub["ended"]) - parse_utc(sub["created"])) <= timedelta(days=1)


def sub_tier(sub):
    """Tier of a real CT+ subscription, or None (not CT+, never paid, or a team test)."""
    name = sub.get("product_name") or ""
    if (not name.startswith("Clearer Thinking Plus") or sub.get("status") == "incomplete_expired"
            or is_test_email(sub.get("email")) or ended_within_a_day(sub)):
        return None
    for tier in ("navigator", "explorer", "supporter"):
        if tier in name.lower():
            return tier
    return None


def charge_kind(ch):
    """'pdf' / 'cognitive' / 'subscription' / 'other' for a succeeded charge dict, None if it must not count.
    Mirrors data_layer._charge_bucket (the dashboard's rule) on the fields kept in the raw file."""
    if ch.get("status") != "succeeded" or (ch["amount"] - (ch.get("refunded") or 0)) <= 0:
        return None
    if (ch.get("desc") or "").lower().strip().startswith("subscription"):
        return "subscription"
    return {900: "pdf", 3500: "cognitive", 1750: "cognitive"}.get(ch["amount"], "other")


# ------------------------------------------------------------------ joining GA4 purchase events to Stripe
def collapse_purchase_events(rows):
    """GA4 plus_sign_up rows -> one purchase per (fingerprint, day): the earliest minute.
    The thank-you page re-fires on reload, so one buyer can produce several events."""
    best = {}
    for r in rows:
        key = (fingerprint(r), r["dateHourMinute"][:8])
        if key not in best or r["dateHourMinute"] < best[key]["dateHourMinute"]:
            best[key] = r
    return sorted(best.values(), key=lambda r: r["dateHourMinute"])


def fingerprint(row):
    return tuple(row.get(k, "") for k in ("city", "deviceCategory", "browser", "operatingSystem", "screenResolution"))


def match_purchases(events, subs, before_min=3, after_min=30):
    """Pair GA4 thank-you-page events with Stripe subscriptions by time.

    events: dicts with 'dateHourMinute' (GA4 clock); subs: dicts with 'created' (UTC).
    An event can match a subscription created from `before_min` minutes after it (clock rounding)
    to `after_min` minutes before it. Greedy by smallest gap; each side is used once.
    Returns [(event_index, sub_index)].
    """
    cands = []
    for i, e in enumerate(events):
        et = ga_minute_to_utc(e["dateHourMinute"])
        for j, s in enumerate(subs):
            gap = (et - parse_utc(s["created"])).total_seconds() / 60.0
            if -before_min <= gap <= after_min:
                cands.append((abs(gap), i, j))
    used_e, used_s, pairs = set(), set(), []
    for _, i, j in sorted(cands):
        if i not in used_e and j not in used_s:
            used_e.add(i), used_s.add(j), pairs.append((i, j))
    return sorted(pairs)


def label_base_rates(events, views, lookback_days=TOUCH_LOOKBACK_DAYS):
    """How often a touch label shows up by coincidence: every purchase time is paired with the browser
    fingerprint of every OTHER purchase (a buyer-like browser that did not buy at that moment).
    Returns {label: % of such pairs carrying the label}; compare with the real share."""
    hits, n = Counter(), 0
    for i, e in enumerate(events):
        for j, other in enumerate(events):
            if i == j or fingerprint(e) == fingerprint(other):
                continue
            pseudo = {**other, "dateHourMinute": e["dateHourMinute"]}
            n += 1
            for lbl in {x["label"] for x in touches_before(pseudo, views, lookback_days)}:
                hits[lbl] += 1
    return {lbl: pct(k, n, 1) for lbl, k in hits.items()}, n


def touch_label(page_location):
    """What kind of link produced this landing-page view."""
    c = (url_param(page_location, "utm_campaign") or "").lower()
    m = (url_param(page_location, "utm_medium") or "").lower()
    if campaign_is(c, "coaching_floating_button"):
        return "www floating button"
    if campaign_is(c, "tools_floating_button") or url_param(page_location, "src") == "tools_fab":
        return "tools floating button"
    if c.startswith("ct_product_grid"):
        return "product grid"
    if c.startswith("coaching_cta"):
        return "in-tool coaching CTA"
    if c == "end_of_tools_banner":
        return "end-of-tool CT+ banner"
    if url_param(page_location, "_bhlid") or "email" in m or "newsletter" in m:
        return "email"
    return "other / untagged"


def touches_before(event, views, lookback_days=TOUCH_LOOKBACK_DAYS):
    """Landing-page views by the same browser fingerprint in the `lookback_days` before a purchase event."""
    t1 = ga_minute_to_utc(event["dateHourMinute"])
    t0 = t1 - timedelta(days=lookback_days)
    fp = fingerprint(event)
    out = []
    for v in views:
        if fingerprint(v) != fp:
            continue
        vt = ga_minute_to_utc(v["dateHourMinute"])
        if t0 <= vt <= t1:
            out.append({"page": v["pagePath"], "label": touch_label(v["pageLocation"])})
    return out


# ------------------------------------------------------------------ the builder
def _iso(date8):
    return f"{date8[:4]}-{date8[4:6]}-{date8[6:]}"


def _in_window(ts, start=WINDOW_START, end=WINDOW_END):
    return start <= ts[:10] <= end


def _lp_block(ga, paths):
    paths = [paths] if isinstance(paths, str) else paths
    tot = [r for r in ga["lp_totals"] if r["pagePath"] in paths]
    groups = defaultdict(lambda: {"sessions": 0, "engaged": 0})
    for r in ga["lp_sources"]:
        if r["pagePath"] in paths:
            g = groups[source_group(r["sessionSource"], r["sessionMedium"], r["sessionManualCampaignName"])]
            g["sessions"] += r["sessions"]
            g["engaged"] += r["engagedSessions"]
    return {"users": sum(r["totalUsers"] for r in tot), "sessions": sum(r["sessions"] for r in tot),
            "engaged_sessions": sum(r["engagedSessions"] for r in tot),
            "sources": sorted(({"group": k, **v} for k, v in groups.items()), key=lambda x: -x["sessions"])}


def _landing(ga, key, period="window"):
    return next(r for r in ga["campaign_landings"] if r["key"] == key and r["period"] == period)


def _session_scoped(ga, path, campaign):
    rows = [r for r in ga["lp_sources"] if r["pagePath"] == path and r["sessionManualCampaignName"] == campaign]
    n = sum(r["sessions"] for r in rows)
    return {"sessions": n, "engaged": sum(r["engagedSessions"] for r in rows), "engaged_pct": pct(sum(r["engagedSessions"] for r in rows), n, 1),
            "avg_engagement_sec": round(sum(r["userEngagementDuration"] for r in rows) / n, 1) if n else None}


def build_datapoints(raw_dir):
    raw = Path(raw_dir)
    ga = json.loads((raw / "ga4.json").read_text())
    st = json.loads((raw / "stripe.json").read_text())
    csv.field_size_limit(10 ** 9)
    with open(raw / "gt_subscribe.csv", newline="") as f:
        sub_rows = list(csv.DictReader(f))
    with open(raw / "gt_cognitive_intro.csv", newline="") as f:
        cog_all = list(csv.DictReader(f))

    dp = {"meta": {"window_start": WINDOW_START, "window_end": WINDOW_END, "weeks": 12,
                   "tools_fab_live": TOOLS_FAB_LIVE, "wave_end": WAVE_END, "touch_lookback_days": TOUCH_LOOKBACK_DAYS}}

    # ---------- floating button, www
    L = _landing(ga, "www_fab")
    exposed = ga["www_users_ex_coaching"][0]["totalUsers"]
    dp["fab_www"] = {"exposed_users": exposed, "landing_users": L["users"], "landing_views": L["views"], "bot_views_excluded": L["bot_views"],
                     "ctr": rate(L["users"], exposed), **{f"session_{k}": v for k, v in _session_scoped(ga, "/coaching", "coaching_floating_button").items()}}

    # ---------- floating button, tools
    fab_tools = {"periods": {}}
    for period, (a, b) in FAB_PERIODS.items():
        pages = Counter()
        for r in ga["clicks_to_www"]:
            if a <= _iso(r["date"]) <= b and campaign_is(url_param(r["linkUrl"], "utm_campaign"), "tools_floating_button"):
                pages[r["pagePath"]] += r["eventCount"]
        Lp = _landing(ga, "tools_fab", period)
        exp = ga[f"programs_users_{period}"][0]["totalUsers"]
        ck = ga["fab_tools_clicks"][period]
        page_users = {r["pagePath"]: r["totalUsers"] for r in ga[f"programs_pages_{period}"]}
        fab_tools["periods"][period] = {
            "start": a, "end": b, "days": (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days + 1, "exposed_users": exp,
            "clicks": ck["eventCount"], "click_users": ck["totalUsers"], "landing_users": Lp["users"], "landing_views": Lp["views"],
            "ctr": rate(ck["totalUsers"], exp),
            "by_page": [{"page": p, "clicks": n, "page_users": page_users.get(p), "clicks_per_100_users": pct(n, page_users.get(p))}
                        for p, n in pages.most_common(8)]}
    fab_tools.update({f"session_{k}": v for k, v in _session_scoped(ga, "/coaching", "tools_floating_button").items()})
    dp["fab_tools"] = fab_tools
    other = [r for r in ga["lp_sources"] if r["pagePath"] == "/coaching" and "floating_button" not in r["sessionManualCampaignName"]
             and r["sessionSource"] != "(not set)"]
    n_other = sum(r["sessions"] for r in other)
    dp["coaching_other_sources"] = {"sessions": n_other, "engaged_pct": pct(sum(r["engagedSessions"] for r in other), n_other, 1),
                                    "avg_engagement_sec": round(sum(r["userEngagementDuration"] for r in other) / max(1, n_other), 1)}

    # ---------- landing pages
    dp["lp"] = {"coaching": _lp_block(ga, "/coaching"), "plus": _lp_block(ga, "/plus"), "cognitive": _lp_block(ga, "/cognitive-test-intro.html"),
                "getmyreport": _lp_block(ga, "/getmyreport.html"), "pdf": _lp_block(ga, PDF_PATHS)}

    # ---------- CT+ funnel: sign-up clicks (GT runs) -> checkout (Stripe sessions) -> paid (Stripe subs)
    runs = [r for r in (subscribe_run(x) for x in sub_rows if _in_window(x["Time Started (UTC)"])) if r]
    test_sub_ids = {s["id"] for s in st["subs"] if ended_within_a_day(s)}
    sessions = []
    for s in st["sessions"]:
        if _in_window(s["created"]):
            prod, real = classify_session(s)
            real = real and s.get("subscription") not in test_sub_ids and not (prod == "supporter_article" and s["created"] < ARTICLE_PAYWALL_FIRST_SEND)
            sessions.append((s, prod, real))
    article_sub_ids = {s["subscription"] for s, prod, real in sessions if prod == "supporter_article" and s["subscription"] and real}
    subs = []
    for s in st["subs"]:
        tier = sub_tier(s)
        if tier and _in_window(s["created"]) and not (s["id"] in {x["subscription"] for x, prod, real in sessions if prod == "supporter_article" and not real}):
            life_days = (parse_utc(s["ended"]) - parse_utc(s["created"])).days if s.get("ended") else None
            subs.append({**s, "tier": tier, "via_article": s["id"] in article_sub_ids, "life_days": life_days})
    funnel = {}
    for tier in ("navigator", "explorer", "supporter"):
        tr = [r for r in runs if r["plan"] == tier]
        ts = [s for s, prod, real in sessions if prod == tier and real]
        tsub = [s for s in subs if s["tier"] == tier and not s["via_article"]]
        funnel[tier] = {
            "signup_clicks": len(tr), "already_member": sum(r["already_member"] for r in tr),
            "gave_email": sum(r["gave_email"] for r in tr), "reached_checkout": sum(r["reached_checkout"] for r in tr),
            "stripe_checkouts": len(ts), "stripe_completed": sum(s["status"] == "complete" for s in ts),
            "paid_subs": len(tsub), "cancelled_within_14d": sum(1 for s in tsub if s["life_days"] is not None and s["life_days"] <= 14),
            "still_active": sum(s["status"] in ("active", "past_due", "trialing") for s in tsub),
            "first_month_revenue": sum(s["amount"] for s in tsub) / 100}
    art = [s for s, prod, real in sessions if prod == "supporter_article" and real]
    dp["ctplus_funnel"] = {"by_tier": funnel,
                           "article_paywall": {"stripe_checkouts": len(art), "stripe_completed": sum(s["status"] == "complete" for s in art),
                                               "paid_subs": sum(s["via_article"] for s in subs)},
                           "test_sessions_excluded": sum(1 for s, prod, real in sessions if not real)}

    # ---------- weekly series (first week is partial: the window starts on a Friday)
    weeks = defaultdict(lambda: {"coaching_users": 0, "plus_users": 0, "nav_clicks": 0, "other_clicks": 0, "nav_subs": 0, "other_subs": 0,
                                 "www_fab_landings": 0, "tools_fab_landings": 0})
    for r in ga["lp_daily"]:
        key = {"/coaching": "coaching_users", "/plus": "plus_users"}.get(r["pagePath"])
        if key:
            weeks[week_of(r["date"])][key] += r["totalUsers"]      # sum of daily users (upper bound on weekly uniques)
    for r in runs:
        weeks[week_of(r["time"][:10])]["nav_clicks" if r["plan"] == "navigator" else "other_clicks"] += 1
    for s in subs:
        if not s["via_article"]:
            weeks[week_of(s["created"][:10])]["nav_subs" if s["tier"] == "navigator" else "other_subs"] += 1
    for r in ga["utm_landings"]:
        c = url_param(r["pageLocation"], "utm_campaign")
        if r["pagePath"] == "/coaching" and r["sessionSource"] != "(not set)":
            if campaign_is(c, "coaching_floating_button"):
                weeks[week_of(r["date"])]["www_fab_landings"] += r["screenPageViews"]
            elif campaign_is(c, "tools_floating_button"):
                weeks[week_of(r["date"])]["tools_fab_landings"] += r["screenPageViews"]
    dp["weekly"] = [{"week": w, **weeks[w]} for w in sorted(weeks)]

    # ---------- purchase attribution (GA4 thank-you event <-> Stripe subscription <-> prior landing-page views)
    events = [e for e in collapse_purchase_events(ga["purchase_events"]) if _in_window(ga_minute_to_utc(e["dateHourMinute"]).strftime("%Y-%m-%d"))]
    typ_subs = [s for s in subs if not s["via_article"]]
    pairs = match_purchases(events, typ_subs)
    purchases = []
    for i, j in pairs:
        e, s = events[i], typ_subs[j]
        t = touches_before(e, ga["lp_views_fp"])
        purchases.append({"week": week_of(s["created"][:10]), "tier": s["tier"], "session_source": e["sessionSourceMedium"],
                          "session_campaign": e["sessionManualCampaignName"],
                          "pages": sorted({x["page"] for x in t}), "touches": sorted({x["label"] for x in t}),
                          "cancelled_within_14d": s["life_days"] is not None and s["life_days"] <= 14})
    matched_events = [events[i] for i, _ in pairs]
    base, n_pairs = label_base_rates(matched_events, ga["lp_views_fp"])
    dp["purchases"] = {"paid_subs_via_signup_flow": len(typ_subs), "ga4_purchase_events": len(events), "matched": len(purchases),
                       "by_touch": dict(Counter(lbl for p in purchases for lbl in p["touches"])),
                       "by_page": dict(Counter("both" if len(p["pages"]) == 2 else (p["pages"][0] if p["pages"] else "none found") for p in purchases)),
                       "by_tier_matched": dict(Counter(p["tier"] for p in purchases)),
                       "coincidence_rate_pct": base, "coincidence_pairs": n_pairs, "rows": purchases,
                       # simplest independent read: the GA4 session channel of EVERY thank-you-page event (no fingerprint join)
                       "all_events_by_session_channel": dict(Counter(
                           source_group(*(e["sessionSourceMedium"].split(" / ") + [""])[:2], e["sessionManualCampaignName"]) for e in events)),
                       "all_events_by_session_campaign": dict(Counter(e["sessionManualCampaignName"] for e in events))}

    # ---------- Cognitive Assessment
    def cog_group(r):
        c = (r.get("utm_campaign") or "").lower()
        m = (r.get("utm_medium") or "").lower()
        if c.startswith("ct_product_grid"):
            return "Product grid"
        if r.get("gclid") or r.get("gbraid") or r.get("wbraid") or m == "cpc":
            return "Google Ads"
        if r.get("cameFromEndCard"):
            return "End-of-tool card"
        if r.get("referringProgram"):
            return "UPT / Rationality report card"
        if m in ("email", "newsletter"):
            return "Email"
        if m in ("menu", "website"):
            return "Website menu / homepage"
        return "Untagged (direct, organic, video, other)"
    real_cog = [r for r in cog_all if not is_test_email(r.get("email")) and r.get("TEST_MODE") in ("", "0", None)]
    cog = [r for r in real_cog if _in_window(r["Time Started (UTC)"])]
    paid_emails = {(c.get("email") or "").lower() for c in st["charges"] if charge_kind(c) == "cognitive" and _in_window(c["created"]) and c.get("email")}
    by_src = defaultdict(lambda: {"runs": 0, "to_payment": 0, "paid": 0})
    for r in cog:
        g = by_src[cog_group(r)]
        g["runs"] += 1
        g["to_payment"] += r.get("wasRedirectedToPayment") == "1"
        g["paid"] += bool(r.get("email")) and r["email"].lower() in paid_emails
    cs = [s for s, prod, real in sessions if prod == "cognitive" and real]
    cch = [c for c in st["charges"] if charge_kind(c) == "cognitive" and _in_window(c["created"])]
    ads = [r for r in real_cog if r.get("gad_campaignid") == UNLINKED_ADS_CAMPAIGN and r["Time Started (UTC)"] >= "2026-01-01"]
    all_paid = {(c.get("email") or "").lower() for c in st["charges"] if charge_kind(c) == "cognitive" and c.get("email")}
    dp["cognitive"] = {"runs": len(cog), "to_payment": sum(g["to_payment"] for g in by_src.values()),
                       "stripe_checkouts": len(cs), "stripe_completed": sum(s["status"] == "complete" for s in cs),
                       "paid_charges": len(cch), "revenue": sum(c["amount"] - c["refunded"] for c in cch) / 100,
                       "paid_matched_to_runs": sum(g["paid"] for g in by_src.values()),
                       "by_source": sorted(({"group": k, **v} for k, v in by_src.items()), key=lambda x: -x["runs"]),
                       "unlinked_ads_campaign": {"id": UNLINKED_ADS_CAMPAIGN, "first": min(r["Time Started (UTC)"][:10] for r in ads) if ads else None,
                                                 "last": max(r["Time Started (UTC)"][:10] for r in ads) if ads else None, "runs": len(ads),
                                                 "to_payment": sum(r.get("wasRedirectedToPayment") == "1" for r in ads),
                                                 "paid": sum(bool(r.get("email")) and r["email"].lower() in all_paid for r in ads)}}

    # ---------- Personality Test PDF
    ev = {(r["pagePath"], r["eventName"]): r for r in ga["tool_events"]}
    upt_finish = ev.get(("/personality-test.html", "Submitted Email"), {}).get("totalUsers", 0)
    pdf_sessions = defaultdict(list)
    for s, prod, real in sessions:
        if prod == "pdf" and real:
            pdf_sessions[s["success_url"]].append(s["status"])      # the flow opens 2 sessions per PDF
    pch = [c for c in st["charges"] if charge_kind(c) == "pdf" and _in_window(c["created"])]
    refs = Counter()
    for r in ga["pdf_page_referrers"]:
        ref = urlsplit(r["pageReferrer"]) if r["pageReferrer"] else None
        refs[(ref.netloc + ref.path) if ref and ref.netloc else "(none: email link or direct)"] += r["screenPageViews"]
    month_fin = {r["yearMonth"]: r["totalUsers"] for r in ga["tool_events_monthly"] if r["eventName"] == "Submitted Email"}
    month_sales = Counter(c["created"][:7] for c in st["charges"] if charge_kind(c) == "pdf")
    dp["pdf"] = {"upt_starts_ga4": ev.get(("/personality-test.html", "Accepted Privacy Policy"), {}).get("totalUsers", 0),
                 "upt_finishers_ga4": upt_finish, "pdf_page_users": dp["lp"]["pdf"]["users"],
                 "pdfs_generated_with_checkout": len(pdf_sessions), "checkouts_completed": sum("complete" in v for v in pdf_sessions.values()),
                 "paid_charges": len(pch), "revenue": sum(c["amount"] - c["refunded"] for c in pch) / 100,
                 "per_finisher": rate(len(pch), upt_finish), "per_pdf_page_user": rate(len(pch), dp["lp"]["pdf"]["users"]),
                 "monthly": [{"month": m, "finishers_ga4": month_fin.get(m.replace("-", "")), "pdf_sales": month_sales[m]}
                             for m in ("2026-07", "2026-08", "2026-09", "2026-10")],
                 "page_referrers": [{"referrer": k, "views": n} for k, n in refs.most_common(8)]}

    # ---------- Product grid
    cards = {}
    for key, lk in (("pdf", "grid_pdf"), ("cognitive", "grid_cognitive"), ("plus", "grid_plus"), ("coaching", "grid_coaching")):
        Lc = _landing(ga, lk)
        cards[key] = {"landing_users": Lc["users"], "landing_views": Lc["views"], "bot_views_excluded": Lc["bot_views"]}
    grid_clicks = defaultdict(Counter)
    for r in ga["clicks_to_www"]:
        if campaign_is(url_param(r["linkUrl"], "utm_campaign"), "ct_product_grid_"):
            grid_clicks[r["pagePath"]]["plus" if "/plus" in r["linkUrl"] else "coaching"] += r["eventCount"]
    grid_src = next((g for g in dp["cognitive"]["by_source"] if g["group"] == "Product grid"), {"runs": 0, "to_payment": 0, "paid": 0})
    grid_tools = ("/personality-test.html", "/how_rational_are_you_really_take_the_test.html")
    finishers = {p: ev.get((p, "Submitted Email"), {}).get("totalUsers", 0) for p in grid_tools}
    n_fin = sum(finishers.values())
    for c in cards.values():
        c["per_100_finishers"] = pct(c["landing_users"], n_fin, 2)
    dp["grid"] = {"cards": cards, "finishers_ga4": finishers, "finishers_total": n_fin,
                  "any_card_per_100_finishers": pct(sum(c["landing_users"] for c in cards.values()), n_fin, 1),
                  "www_card_clicks_by_tool": [{"page": p, **dict(c)} for p, c in sorted(grid_clicks.items(), key=lambda kv: -sum(kv[1].values()))[:8]],
                  "cognitive_from_grid": grid_src}

    # ---------- in-tool coaching CTAs and the end-of-tool CT+ banner
    def clicks_from(prefix, to):
        n = 0
        for r in ga["clicks_to_www"]:
            c = url_param(r["linkUrl"], "utm_campaign")
            promo = campaign_is(c, "tools_floating_button") or campaign_is(c, "ct_product_grid_") or url_param(r["linkUrl"], "src") == "tools_fab"
            if r["pagePath"].startswith(prefix) and f"clearerthinking.org/{to}" in r["linkUrl"] and not promo:
                n += r["eventCount"]
        return n
    utt_fin = sum(v["totalUsers"] for (p, e), v in ev.items() if p.startswith("/unique-traits-test") and e == "Finished Exercise")
    utt_clicks = clicks_from("/unique-traits-test", "coaching")
    dp["tool_ctas"] = {"unique_traits": {"finishers_ga4": utt_fin, "clicks": utt_clicks, "ctr": rate(utt_clicks, utt_fin),
                                         "tagged_landing_users": _landing(ga, "utt_cta")["users"]},
                       "dashboard": {"clicks_to_coaching": clicks_from("/dashboard", "coaching"), "clicks_to_plus": clicks_from("/dashboard", "plus")},
                       "end_banner_plus": {"landing_users": _landing(ga, "end_banner_plus")["users"], "landing_views": _landing(ga, "end_banner_plus")["views"]}}

    # ---------- cross-checks between independent sources
    dp["cross_checks"] = {
        "ctplus_completed_checkouts_vs_paid_subs": [sum(f["stripe_completed"] for f in funnel.values()), sum(f["paid_subs"] for f in funnel.values())],
        "pdf_completed_checkouts_vs_charges": [dp["pdf"]["checkouts_completed"], dp["pdf"]["paid_charges"]],
        "cognitive_completed_checkouts_vs_charges": [dp["cognitive"]["stripe_completed"], dp["cognitive"]["paid_charges"]],
        "tools_fab_click_events_vs_landing_views": [fab_tools["periods"]["fab_all"]["clicks"], fab_tools["periods"]["fab_all"]["landing_views"]],
        "grid_cognitive_ga4_users_vs_gt_runs": [cards["cognitive"]["landing_users"], grid_src["runs"]]}
    return dp


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    a = ap.parse_args()
    out = Path(__file__).with_name("datapoints.json")
    out.write_text(json.dumps(build_datapoints(a.raw_dir), indent=1))
    print("wrote", out)
