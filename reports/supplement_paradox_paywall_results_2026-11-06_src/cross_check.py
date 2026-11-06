"""Independent recount of the headline numbers ("simplest valid analysis"), written separately from
analysis.py: pandas one-liners on the raw pulls, different sources where one exists. Prints both
figures side by side and exits 1 when any pair disagrees beyond its stated tolerance.

    .venv/bin/python reports/supplement_paradox_paywall_results_2026-11-06_src/cross_check.py

Each headline is recounted from a source the main analysis did NOT use for it:
  sales          main: Stripe Checkout Sessions of the Payment Link.   here: Stripe subscription list.
  email visitors main: GuidedTrack runs (distinct hashes).             here: beehiiv verified link clicks.
  all visitors   main: GuidedTrack runs.                               here: GA4 users of the pitch page.
  unsubscribes   main: beehiiv v2 API today.                           here: figures read off the beehiiv
                                                                       connector earlier the same day.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SEND = "2026-10-16 12:57"
# Read off the beehiiv MCP connector (get_post_stats_batch) on 2026-11-06, before the API pull.
CONNECTOR_ENGAGED_SEND = {"unsubscribes": 575, "unique_opens": 53275}


def main() -> int:
    dp = json.loads((HERE / "datapoints.json").read_text())
    f = dp["funnel"]

    subs = pd.DataFrame(json.loads((DATA / "stripe_subscriptions.json").read_text()))
    since = subs[(subs.created >= SEND) & (subs.lookup == "supporter")]
    real = since[(since.status != "incomplete_expired") & ~(since.canceled_at.fillna("").str[:10] == since.created.str[:10])]
    sales_alt = len(real)

    posts = json.loads((DATA / "beehiiv_posts.json").read_text())
    verified = set()
    for pid in ("post_89bcdaf5-bbcc-4e61-ba15-1024e66142c2", "post_49066aa7-3fc8-413b-88d7-3aae0e96eb53",
                "post_e18bfc70-d0cc-4f8b-8b7a-0f2a7ba45fe9", "post_3aacc4ea-e275-428b-a66e-1de88b891a5b"):
        clicks = pd.DataFrame(posts[pid]["stats"]["clicks"])
        pw = clicks[clicks.url.str.contains("members-only-content/", regex=False) & clicks.url.str.contains("h=", regex=False)]
        ok = pw[pw.email.map(lambda e: e["unique_verified_clicks"] > 0)]
        verified |= set(ok.url.str.extract(r"[?&]h=([0-9a-f]{32})")[0])
    email_alt = len(verified)

    ga4_users = json.loads((DATA / "ga4.json").read_text())["pitch_page_users"]
    unsub_alt = CONNECTOR_ENGAGED_SEND["unsubscribes"] / CONNECTOR_ENGAGED_SEND["unique_opens"]
    unsub_main = dp["engaged_send_vs_baseline"]["engaged_send"]["unsub_per_open"]

    checks = [
        # label, main figure, independent figure, tolerance (absolute), why they may differ
        ("paid sign-ups", f["checkouts_paid"], sales_alt, 0, "must match exactly"),
        ("email visitors to the pitch page", f["email_visitors"], email_alt, 6,
         "beehiiv's bot filter and GuidedTrack's 'a browser ran the page' are different tests of 'human'"),
        ("all visitors to the pitch page", f["email_visitors"] + f["web_runs"], ga4_users, 15,
         "GA4 counts browsers, needs consent/JS and runs on US Eastern days"),
        ("unsubscribes per opener, engaged send", round(unsub_main, 5), round(unsub_alt, 5), 0.0002,
         "opens keep trickling in between the two pulls"),
    ]
    bad = 0
    for label, main_v, alt_v, tol, why in checks:
        ok = abs(main_v - alt_v) <= tol
        bad += not ok
        print(f"{'OK ' if ok else 'DIFF'} {label}: main {main_v} vs independent {alt_v} (tolerance {tol}; {why})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
