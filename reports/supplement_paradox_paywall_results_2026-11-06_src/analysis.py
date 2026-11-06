"""Results of the first members-only paywall in a newsletter ("The Supplement Paradox", Oct 2026).

Pure functions (tested in tests/test_supplement_paradox_paywall.py) plus `main()`, which reads the
raw pulls in data/ (written by fetch_data.py, gitignored) and writes datapoints.json, the single
source of every number in the report.

    .venv/bin/python reports/supplement_paradox_paywall_results_2026-11-06_src/fetch_data.py
    .venv/bin/python reports/supplement_paradox_paywall_results_2026-11-06_src/analysis.py
    .venv/bin/python reports/supplement_paradox_paywall_results_2026-11-06_src/build_report.py

How the funnel is measured (three independent systems):
  beehiiv   per-link clicks: the paywall link carries each reader's email hash, so one click row is
            one subscriber. "Verified" clicks are beehiiv's bot-filtered count.
  GuidedTrack  program 38912 (the pitch page) creates a run only when a browser executes the page,
            so scanners that merely fetch the link leave no run. `h` is the same email hash.
  Stripe    every open of the Payment Link creates a Checkout Session; a completed one is a sale.
            The customer's email, hashed the same way, ties the sale back to the run.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DATAPOINTS = HERE / "datapoints.json"

# First real send (post 89bcdaf5); everything before it on the pitch page is team testing.
SEND_START = datetime(2026, 10, 16, 12, 57, tzinfo=timezone.utc)
SP_POSTS = {  # the four sends of the edition, in order
    "post_89bcdaf5-bbcc-4e61-ba15-1024e66142c2": "Oct 16, slice of the whole list (subject-line test)",
    "post_49066aa7-3fc8-413b-88d7-3aae0e96eb53": "Oct 16, engaged subscribers",
    "post_e18bfc70-d0cc-4f8b-8b7a-0f2a7ba45fe9": "Oct 19, resend to frequent openers who had not opened",
    "post_3aacc4ea-e275-428b-a66e-1de88b891a5b": "Oct 30, rest of the list (no opens in 6 months)",
}
ENGAGED_SEND = "post_49066aa7-3fc8-413b-88d7-3aae0e96eb53"
# Earlier article editions sent to the same "CT Audience - Engaged Subs" segment (ead5b83a), the
# like-for-like baseline for the Oct 16 engaged send. Oct 8 went out as two rating-order variants.
BASELINE_EDITIONS = {
    "Sep 18, happiness findings": ["post_cf5686b9-161a-480f-9ae3-1229ecc4007d"],
    "Sep 24, career advice": ["post_04eb21c8-be00-411c-970a-93bf47fd738e"],
    "Sep 29, unanswerable questions": ["post_2b220041-3980-4ed7-8362-0529f8bab1d8"],
    "Oct 8, cognitive biases": ["post_54bc1fbd-457f-48a8-ac19-1b5a502338f4", "post_526daa18-c8a1-4532-9d4e-cebbe5c4beba"],
}
PAYWALL_LINK = re.compile(r"members-only-content/[^ ]*[?&]h=([0-9a-f]{32})")
SUPPORTER_PRICE_USD = 9
BASELINE_START = datetime(2026, 7, 1, tzinfo=timezone.utc)   # Stripe pull starts here
BASELINE_END = datetime(2026, 10, 12, tzinfo=timezone.utc)   # first paywall test payments on Oct 12
RATING_ORDER = ["Excellent", "Good", "Okay", "Subpar", "Bad"]
LOW_RATINGS = {"Subpar", "Bad"}


# ---------------------------------------------------------------------------------------------
# small statistics
# ---------------------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion k/n, as fractions. (0, 0) when n is 0."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def binom_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def rate_ratio_test(k_test: int, days_test: float, k_base: int, days_base: float) -> dict:
    """Did events happen faster in the test window than in the baseline window?

    Exact conditional test for two Poisson rates: given k_test + k_base events in total, under
    equal rates each lands in the test window with probability days_test / (days_test + days_base).
    Returns both weekly rates, their ratio and the one-sided p-value for "test rate is higher".
    """
    share = days_test / (days_test + days_base)
    rate_test = k_test / days_test * 7
    rate_base = k_base / days_base * 7
    return {
        "per_week_test": rate_test,
        "per_week_base": rate_base,
        "ratio": (rate_test / rate_base) if rate_base else None,
        "p_one_sided": binom_tail(k_test, k_test + k_base, share),
    }


def compare_to_baseline(value: float, baseline: list[float]) -> dict:
    """Place one edition's rate among earlier editions' rates.

    Edition-to-edition variation (topic, timing, deliverability) is far larger than binomial
    sampling noise at these list sizes, so the yardstick is the spread BETWEEN baseline editions:
    z = (value - mean) / sd, and the verdict is "above" or "below" only outside the baseline's own
    min-max range AND beyond 2 sd; otherwise "within".
    """
    m = mean(baseline)
    sd = stdev(baseline) if len(baseline) > 1 else 0.0
    z = (value - m) / sd if sd else 0.0
    verdict = "within"
    if value > max(baseline) and z > 2:
        verdict = "above"
    elif value < min(baseline) and z < -2:
        verdict = "below"
    return {"value": value, "mean": m, "sd": sd, "min": min(baseline), "max": max(baseline), "z": z, "verdict": verdict}


# ---------------------------------------------------------------------------------------------
# beehiiv
# ---------------------------------------------------------------------------------------------

def paywall_clickers(posts: list[dict]) -> dict:
    """Subscribers who clicked the paywall link in any of `posts` (single-post API payloads).

    Returns {"all": set of email hashes, "verified": subset with a bot-filtered click}.
    """
    everyone, verified = set(), set()
    for p in posts:
        for c in (p.get("stats") or {}).get("clicks") or []:
            m = PAYWALL_LINK.search(c.get("url") or "")
            if not m:
                continue
            everyone.add(m.group(1))
            if (c.get("email") or {}).get("unique_verified_clicks"):
                verified.add(m.group(1))
    return {"all": everyone, "verified": verified}


def send_stats(posts: list[dict]) -> dict:
    """Totals and rates for one edition (one or more beehiiv posts). Rates are fractions."""
    keys = ("recipients", "delivered", "unique_opens", "unsubscribes", "spam_reports")
    tot = {k: 0 for k in keys}
    for p in posts:
        e = (p.get("stats") or {}).get("email") or {}
        for k in keys:
            tot[k] += int(e.get(k) or 0)
    d, o = tot["delivered"], tot["unique_opens"]
    tot.update({
        "open_rate": o / tot["recipients"] if tot["recipients"] else 0.0,
        "unsub_per_delivered": tot["unsubscribes"] / d if d else 0.0,
        "unsub_per_open": tot["unsubscribes"] / o if o else 0.0,
        "spam_per_delivered": tot["spam_reports"] / d if d else 0.0,
        "spam_per_open": tot["spam_reports"] / o if o else 0.0,
    })
    return tot


def link_clicks(post: dict, needle: str) -> int:
    """Unique verified email clicks on every link of `post` whose URL contains `needle`."""
    return sum((c.get("email") or {}).get("unique_verified_clicks") or 0
               for c in (post.get("stats") or {}).get("clicks") or [] if needle in (c.get("url") or ""))


# ---------------------------------------------------------------------------------------------
# GuidedTrack pitch page (program 38912)
# ---------------------------------------------------------------------------------------------

def _flag(v) -> int | None:
    """GT exports numbers as '1.0' / '0.0' / '' : return 1, 0 or None."""
    if v is None or v == "" or (isinstance(v, float) and math.isnan(v)):
        return None
    return int(float(v))


def classify_runs(runs: list[dict], send_start: datetime, team_hashes: set[str]) -> dict:
    """Funnel counts for the pitch page from its run export.

    Each run needs: t (aware datetime), src, h (email hash or ""), isMember, emailMember.
    Runs before `send_start` and runs whose hash is in `team_hashes` are dropped (and counted).
    Channel: a run with a hash came from the email; one without came from the web post's box.
    A "visitor" is a distinct hash for email runs (the same reader reloading is one visitor) and
    a run for web runs (no identifier exists there, so web visitors are an upper bound).
    """
    out = {"pre_send_runs": 0, "team_runs": 0,
           "email": {"runs": 0, "hashes": set(), "member_hashes": set(), "typed_member": 0, "typed_non_member": 0},
           "web": {"runs": 0, "typed_member": 0, "typed_non_member": 0}}
    for r in runs:
        if r["t"] < send_start:
            out["pre_send_runs"] += 1
            continue
        h = (r.get("h") or "").strip().lower()
        if h and h in team_hashes:
            out["team_runs"] += 1
            continue
        ch = out["email"] if h else out["web"]
        ch["runs"] += 1
        if h:
            ch["hashes"].add(h)
            if _flag(r.get("isMember")) == 1:
                ch["member_hashes"].add(h)
        typed = _flag(r.get("emailMember"))
        if typed == 1:
            ch["typed_member"] += 1
        elif typed == 0:
            ch["typed_non_member"] += 1
    e, w = out["email"], out["web"]
    e["visitors"] = len(e["hashes"])
    e["members_by_hash"] = len(e["member_hashes"])
    e["non_member_visitors"] = e["visitors"] - e["members_by_hash"]
    w["visitors"] = w["runs"]
    w["non_member_visitors"] = w["runs"] - w["typed_member"]
    return out


def match_sales(sessions: list[dict], runs: list[dict], send_start: datetime,
                window: timedelta = timedelta(minutes=10)) -> list[dict]:
    """Attach each post-send Checkout Session to the pitch-page run it came from.

    A session matches an EMAIL run when the customer's email hash equals a run's `h`. Otherwise
    it matches the latest hash-less (web) run started within `window` before the session. Sessions
    need: created (aware datetime), status, email_md5 (None for abandoned checkouts).
    Returns one dict per session: created, paid (bool), channel ("email" | "web" | "unknown").
    """
    post = [r for r in runs if r["t"] >= send_start]
    by_hash = {(r.get("h") or "").lower() for r in post if r.get("h")}
    web_runs = sorted((r["t"] for r in post if not r.get("h")))
    hash_runs = sorted((r["t"] for r in post if r.get("h")))

    def near(times: list[datetime], when: datetime) -> bool:
        return any(timedelta(0) <= when - t <= window for t in times)

    out = []
    for s in sorted(sessions, key=lambda s: s["created"]):
        if s["created"] < send_start:
            continue
        if s.get("email_md5") and s["email_md5"] in by_hash:
            channel = "email"
        elif near(web_runs, s["created"]):
            channel = "web"
        elif near(hash_runs, s["created"]):
            channel = "email"
        else:
            channel = "unknown"
        out.append({"created": s["created"], "paid": s["status"] == "complete", "channel": channel,
                    "email_md5": s.get("email_md5"), "subscription": s.get("sub")})
    return out


# ---------------------------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------------------------

def is_test_subscription(sub: dict) -> bool:
    """Team test: cancelled the same day it was created, or never completed payment."""
    if sub.get("status") == "incomplete_expired":
        return True
    return bool(sub.get("canceled_at")) and sub["canceled_at"][:10] == sub["created"][:10]


def supporter_signups(subs: list[dict], start: datetime, end: datetime) -> list[dict]:
    """Real (non-test) Supporter subscriptions created in [start, end)."""
    fmt = "%Y-%m-%d %H:%M"
    out = []
    for s in subs:
        created = datetime.strptime(s["created"], fmt).replace(tzinfo=timezone.utc)
        if s.get("lookup") == "supporter" and not is_test_subscription(s) and start <= created < end:
            out.append(s)
    return out


# ---------------------------------------------------------------------------------------------
# article ratings (program 38551)
# ---------------------------------------------------------------------------------------------

def article_slug(url: str) -> str:
    """'https://www.clearerthinking.org/post/the-supplement-paradox?utm=..' -> 'the-supplement-paradox'."""
    return re.sub(r"[?#].*$", "", str(url or "")).rstrip("/").rsplit("/", 1)[-1]


def ratings_by_article(rows: list[dict]) -> dict:
    """{slug: {rating: count, "n": total, "low": Subpar + Bad}} from rating runs (article, final_rating)."""
    out: dict = defaultdict(lambda: Counter())
    for r in rows:
        rating = r.get("final_rating")
        slug = article_slug(r.get("article"))
        if rating in RATING_ORDER and slug and slug not in ("nan", "ARTICLE_URL"):
            out[slug][rating] += 1
    res = {}
    for slug, c in out.items():
        n = sum(c.values())
        res[slug] = {**{k: c.get(k, 0) for k in RATING_ORDER}, "n": n, "low": sum(c.get(k, 0) for k in LOW_RATINGS)}
    return res


# ---------------------------------------------------------------------------------------------
# main: raw pulls -> datapoints.json
# ---------------------------------------------------------------------------------------------

def _load(name: str):
    return json.loads((DATA / name).read_text())


def _dt(s: str) -> datetime:
    return datetime.strptime(s[:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def build_datapoints(now: datetime) -> dict:
    posts = _load("beehiiv_posts.json")                 # {post_id: single-post payload}
    runs_raw = _load("gt_pitch_runs.json")
    full_runs = _load("gt_full_version_runs.json")
    sessions_raw = _load("stripe_sessions.json")
    subs = _load("stripe_subscriptions.json")
    ratings = _load("gt_ratings.json")
    ga4 = _load("ga4.json")

    runs = [{**r, "t": _dt(r["t"])} for r in runs_raw]
    sessions = [{**s, "created": _dt(s["created"])} for s in sessions_raw]

    # Team: every hash seen on the pitch page before the send, plus the pre-send test payers.
    team = {r["h"].lower() for r in runs if r["t"] < SEND_START and r.get("h")}
    team |= {s["email_md5"] for s in sessions if s["created"] < SEND_START and s.get("email_md5")}

    sp_posts = [posts[p] for p in SP_POSTS]
    clickers = paywall_clickers(sp_posts)
    funnel = classify_runs(runs, SEND_START, team)
    sales = match_sales(sessions, runs, SEND_START)
    paid = [s for s in sales if s["paid"]]
    sub_by_id = {s["id"]: s for s in subs}
    paid_status = [sub_by_id[s["subscription"]]["status"] for s in paid if s["subscription"] in sub_by_id]

    gt_hashes = funnel["email"]["hashes"]
    email, web = funnel["email"], funnel["web"]
    paid_email = sum(1 for s in paid if s["channel"] == "email")
    paid_web = sum(1 for s in paid if s["channel"] == "web")

    edition = send_stats(sp_posts)
    per_send = []
    for pid, label in SP_POSTS.items():
        st = send_stats([posts[pid]])
        c = paywall_clickers([posts[pid]])
        per_send.append({"label": label, **st, "paywall_clickers": len(c["all"]), "paywall_clickers_verified": len(c["verified"]),
                         "web_version_clicks_verified": link_clicks(posts[pid], "clearerthinking.org/post/the-supplement-paradox")})
    engaged = send_stats([posts[ENGAGED_SEND]])
    baseline = {name: send_stats([posts[p] for p in ids]) for name, ids in BASELINE_EDITIONS.items()}

    def cmp(metric: str) -> dict:
        return compare_to_baseline(engaged[metric], [b[metric] for b in baseline.values()])

    # Supporter sign-ups: the weeks since the send against the pre-paywall baseline.
    base_sups = supporter_signups(subs, BASELINE_START, BASELINE_END)
    test_sups = supporter_signups(subs, SEND_START, now)
    days_test = (now - SEND_START).total_seconds() / 86400
    days_base = (BASELINE_END - BASELINE_START).total_seconds() / 86400
    rr = rate_ratio_test(len(test_sups), days_test, len(base_sups), days_base)
    paid_hashes = {s["email_md5"] for s in paid}
    other_tier = [s for s in subs if _dt(s["created"]) >= SEND_START and not is_test_subscription(s)
                  and s.get("lookup") != "supporter" and s.get("email_md5") in (gt_hashes | clickers["all"])]
    presend_real = [s for s in supporter_signups(subs, BASELINE_END, SEND_START)]

    rt = ratings_by_article(ratings)
    sp_r = rt.get("the-supplement-paradox", {"n": 0, "low": 0})
    others = {k: v for k, v in rt.items() if k != "the-supplement-paradox" and v["n"] >= 20}
    oth_n, oth_low = sum(v["n"] for v in others.values()), sum(v["low"] for v in others.values())
    feedback = [r for r in ratings if article_slug(r.get("article")) == "the-supplement-paradox" and r.get("feedback")]
    paywall_words = re.compile(r"paywall|pay ?wall|member|paid|paying|subscri", re.I)
    all_paywall_fb = [{"date": r["t"][:10], "article": article_slug(r.get("article")), "rating": r.get("final_rating"),
                       "text": r["feedback"]} for r in ratings
                      if r.get("feedback") and paywall_words.search(r["feedback"]) and r["t"] >= "2026-10-16"]

    fv = [r for r in full_runs if _dt(r["t"]) >= SEND_START]

    return {
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"start": SEND_START.strftime("%Y-%m-%d %H:%M UTC"), "end": now.strftime("%Y-%m-%d %H:%M UTC"),
                   "days": round(days_test, 1)},
        "edition": {k: edition[k] for k in ("recipients", "delivered", "unique_opens", "unsubscribes", "spam_reports",
                                             "open_rate", "unsub_per_delivered", "unsub_per_open", "spam_per_delivered")},
        "sends": per_send,
        "funnel": {
            "unique_opens": edition["unique_opens"],
            "paywall_clickers_all": len(clickers["all"]),
            "paywall_clickers_verified": len(clickers["verified"]),
            "email_runs": email["runs"], "email_visitors": email["visitors"],
            "email_members_by_hash": email["members_by_hash"], "email_non_member_visitors": email["non_member_visitors"],
            "email_typed_member": email["typed_member"], "email_typed_non_member": email["typed_non_member"],
            "web_runs": web["runs"], "web_typed_member": web["typed_member"], "web_typed_non_member": web["typed_non_member"],
            "web_non_member_visitors": web["non_member_visitors"],
            "checkouts_opened": len(sales), "checkouts_paid": len(paid), "checkouts_abandoned": len(sales) - len(paid),
            "paid_email": paid_email, "paid_web": paid_web,
            "paid_dates": [s["created"].strftime("%Y-%m-%d") for s in paid],
            "paid_still_active": sum(1 for x in paid_status if x == "active"),
            "pre_send_runs_excluded": funnel["pre_send_runs"], "team_runs_excluded": funnel["team_runs"],
            "full_version_views": len(fv),
            "web_post_views": ga4.get("web_post_views"), "web_post_users": ga4.get("web_post_users"),
            "ga4_pitch_page_users": ga4.get("pitch_page_users"),
        },
        "cross_checks": {
            "gt_visitors_also_beehiiv_clickers": len(gt_hashes & clickers["all"]),
            "gt_visitors": len(gt_hashes),
            "verified_clickers_with_gt_run": len(clickers["verified"] & gt_hashes),
            "verified_clickers": len(clickers["verified"]),
            "paid_hashes_among_gt_visitors": len(paid_hashes & gt_hashes),
            "supporter_subs_since_send_from_stripe_list": len(test_sups),
            "other_tier_subs_by_paywall_visitors": len(other_tier),
        },
        "rates": {
            "paid_per_opener": len(paid) / edition["unique_opens"],
            "email_click_per_opener": email["visitors"] / edition["unique_opens"],
            "email_paid_per_non_member_visitor": paid_email / email["non_member_visitors"] if email["non_member_visitors"] else 0,
            "email_paid_per_non_member_visitor_ci": wilson(paid_email, email["non_member_visitors"]),
            "paid_per_checkout": len(paid) / len(sales) if sales else 0,
        },
        "revenue": {"price_usd": SUPPORTER_PRICE_USD, "new_mrr_usd": SUPPORTER_PRICE_USD * len(paid),
                    "annualised_if_all_stay_usd": SUPPORTER_PRICE_USD * len(paid) * 12},
        "supporter_baseline": {
            "baseline_window": f"{BASELINE_START:%Y-%m-%d} to {BASELINE_END:%Y-%m-%d}", "baseline_signups": len(base_sups),
            "baseline_days": round(days_base, 1), "test_signups": len(test_sups), "test_days": round(days_test, 1),
            "per_week_base": rr["per_week_base"], "per_week_test": rr["per_week_test"], "ratio": rr["ratio"],
            "p_one_sided": rr["p_one_sided"],
            "pre_send_untested_signups": [{"created": s["created"], "status": s["status"]} for s in presend_real],
        },
        "engaged_send_vs_baseline": {
            "engaged_send": {k: engaged[k] for k in ("recipients", "delivered", "unique_opens", "unsubscribes", "spam_reports",
                                                     "open_rate", "unsub_per_delivered", "unsub_per_open", "spam_per_delivered", "spam_per_open")},
            "baseline_editions": {n: {k: b[k] for k in ("recipients", "delivered", "unique_opens", "unsubscribes", "spam_reports",
                                                         "open_rate", "unsub_per_delivered", "unsub_per_open", "spam_per_delivered", "spam_per_open")}
                                  for n, b in baseline.items()},
            "unsub_per_open": cmp("unsub_per_open"), "unsub_per_delivered": cmp("unsub_per_delivered"),
            "spam_per_open": cmp("spam_per_open"), "open_rate": cmp("open_rate"),
        },
        "ratings": {
            "supplement_paradox": sp_r,
            "low_share": sp_r["low"] / sp_r["n"] if sp_r["n"] else 0, "low_share_ci": wilson(sp_r["low"], sp_r["n"]),
            "others": {k: v for k, v in sorted(others.items())},
            "others_low_share": oth_low / oth_n if oth_n else 0, "others_n": oth_n, "others_low": oth_low,
            "others_low_range": [min(v["low"] / v["n"] for v in others.values()), max(v["low"] / v["n"] for v in others.values())] if others else [0, 0],
            "written_feedback_count": len(feedback),
            "written_feedback_mentioning_paywall": sum(1 for r in feedback if paywall_words.search(r["feedback"])),
            "paywall_feedback_any_article_since_send": all_paywall_fb,
        },
        "benchmarks": {
            "note": "From reports/paywall_conversion_benchmark_2026-09-23_src/datapoints.json (news-site paywalls).",
            "paid_per_paywall_stop_median_low": 0.0022, "paid_per_paywall_stop_median_high": 0.0054,
            "paid_per_paywall_stop_top_decile": 0.0131, "checkout_completion_desktop": 0.099, "checkout_completion_mobile": 0.053,
        },
    }


def main() -> None:
    dp = build_datapoints(datetime.now(timezone.utc).replace(second=0, microsecond=0))
    DATAPOINTS.write_text(json.dumps(dp, indent=1, ensure_ascii=False, default=list) + "\n")
    f = dp["funnel"]
    print(f"openers {f['unique_opens']:,} -> pitch-page visitors {f['email_visitors']} email + {f['web_runs']} web "
          f"-> checkouts {f['checkouts_opened']} -> paid {f['checkouts_paid']} (still active {f['paid_still_active']})")


if __name__ == "__main__":
    main()
