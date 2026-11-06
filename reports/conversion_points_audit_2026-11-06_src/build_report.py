"""Render reports/conversion_points_audit_2026-11-06.html from datapoints.json (aggregates only).

    .venv/bin/python reports/conversion_points_audit_2026-11-06_src/build_report.py [--open]

Every number in the page is read from datapoints.json; the device split and the scroll figures that
came from one-off GA4 queries live in EXTRA below, with the query described next to each.
"""
import html
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "conversion_points_audit_2026-11-06.html"
dp = json.loads((HERE / "datapoints.json").read_text())

# One-off GA4 reads (2026-11-06) that are not in the fetch script.
EXTRA = {
    # users who clicked / users exposed, by device. Tools button: steady period Oct 24 to Nov 5, click events.
    # Website button: Aug 14 to Nov 5, tagged /coaching page views, scanner hits excluded.
    "tools_fab_device": {"mobile": (905, 18524), "desktop": (225, 8514)},
    "www_fab_device": {"mobile": (1190, 53352), "desktop": (138, 48208)},
    # /coaching sessions by GA4 session campaign, Aug 14 to Nov 5: (sessions, avg engaged seconds, scroll-to-bottom events)
    "coaching_quality": {"Tools floating button": (4299, 6.1, 230), "Website floating button": (555, 14.3, 43),
                         "Coaching email (Oct 27)": (439, 25.7, 61), "Organic search": (614, 18.7, 68)},
}


def n(x):
    return f"{x:,.0f}" if isinstance(x, (int, float)) else str(x)


def p(k, total, d=1):
    return f"{100 * k / total:.{d}f}%" if total else "n/a"


def esc(s):
    return html.escape(str(s))


# ------------------------------------------------------------------ charts (inline SVG, no gridlines, no frame)
def weekly_chart():
    weeks = [w for w in dp["weekly"] if w["week"] >= "2026-08-17"]
    W, H, L, R, T, B = 860, 300, 44, 16, 46, 46
    top = max(max(w["nav_clicks"], w["nav_subs"]) for w in weeks)
    ymax = (top // 10 + 1) * 10
    slot = (W - L - R) / len(weeks)
    bw = 13
    y = lambda v: T + (H - T - B) * (1 - v / ymax)  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Navigator sign-up clicks and new paid Navigators per week">']
    for tick in range(0, ymax + 1, 10):
        out.append(f'<text x="{L - 8}" y="{y(tick) + 4}" class="tick" text-anchor="end">{tick}</text>')
    out.append(f'<line x1="{L}" y1="{y(0)}" x2="{W - R}" y2="{y(0)}" class="axis"/>')
    notes = {"2026-10-19": "Tools button live (Oct 21)", "2026-10-26": "Coaching email (Oct 27)"}
    for i, w in enumerate(weeks):
        cx = L + slot * (i + 0.5)
        d = datetime.strptime(w["week"], "%Y-%m-%d")
        label = d.strftime("%b %-d") + ("*" if w["week"] == "2026-11-02" else "")
        for j, (key, cls, name) in enumerate((("nav_clicks", "s1", "Sign-up clicks"), ("nav_subs", "s2", "New paid Navigators"))):
            v = w[key]
            x = cx - bw - 1 + j * (bw + 2)
            h = y(0) - y(v)
            if v:
                r = min(4, h)
                out.append(f'<path class="{cls} bar" data-tip="Week of {label.rstrip("*")}: {v} {name.lower()}" '
                           f'd="M{x},{y(0)} v{-(h - r)} q0,{-r} {r},{-r} h{bw - 2 * r} q{r},0 {r},{r} v{h - r} z"/>')
        out.append(f'<text x="{cx}" y="{H - B + 18}" class="tick" text-anchor="middle">{label}</text>')
        if w["week"] in notes:      # selective direct labels: only the two annotated weeks
            out.append(f'<text x="{cx - bw / 2 - 1}" y="{y(w["nav_clicks"]) - 6}" class="val" text-anchor="middle">{w["nav_clicks"]}</text>')
            out.append(f'<text x="{cx + bw / 2 + 1}" y="{y(w["nav_subs"]) - 6}" class="val" text-anchor="middle">{w["nav_subs"]}</text>')
            # the note sits right above the value label of its own week, right-aligned, so it crosses nothing
            out.append(f'<text x="{cx + bw + 1}" y="{y(w["nav_clicks"]) - 24}" class="note" text-anchor="end">{notes[w["week"]]}</text>')
    out.append("</svg>")
    return "".join(out)


def rate_chart():
    g, t = dp["grid"]["cards"], dp["tool_ctas"]["unique_traits"]
    dev = lambda k: 100 * k[0] / k[1]  # noqa: E731
    rows = [
        ("Tools floating button, phones", dev(EXTRA["tools_fab_device"]["mobile"]), "of tool visitors"),
        ("Product grid: PDF card", g["pdf"]["per_100_finishers"], "of test finishers"),
        ("Tools floating button, desktop", dev(EXTRA["tools_fab_device"]["desktop"]), "of tool visitors"),
        ("Website floating button, phones", dev(EXTRA["www_fab_device"]["mobile"]), "of site visitors"),
        ("Product grid: Cognitive Assessment card", g["cognitive"]["per_100_finishers"], "of test finishers"),
        ("Unique Traits coaching CTA", t["ctr"]["pct"], "of test finishers"),
        ("Product grid: CT+ button", g["plus"]["per_100_finishers"], "of test finishers"),
        ("Product grid: coaching card", g["coaching"]["per_100_finishers"], "of test finishers"),
        ("Website floating button, desktop", dev(EXTRA["www_fab_device"]["desktop"]), "of site visitors"),
    ]
    rows.sort(key=lambda r: -r[1])
    W, rowh, L, R, T = 860, 30, 290, 150, 6
    H = T + rowh * len(rows) + 8
    vmax = max(r[1] for r in rows)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Share of exposed people who clicked each prompt">']
    out.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{H - 8}" class="axis"/>')
    for i, (name, v, den) in enumerate(rows):
        yy = T + rowh * i + 6
        w = max(2, (W - L - R) * v / vmax)
        r = min(4, w)
        out.append(f'<text x="{L - 10}" y="{yy + 13}" class="lab" text-anchor="end">{esc(name)}</text>')
        out.append(f'<path class="s1 bar" data-tip="{esc(name)}: {v:.1f}% {den}" d="M{L},{yy} h{w - r} q{r},0 {r},{r} v{18 - 2 * r} q0,{r} {-r},{r} h{-(w - r)} z"/>')
        out.append(f'<text x="{L + w + 8}" y="{yy + 13}" class="val">{v:.1f}% <tspan class="den">{den}</tspan></text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ small HTML helpers
def funnel(steps, note=""):
    """steps: [(label, count)]. Shows each step, its share of the first step and of the previous one."""
    first = steps[0][1] or 1
    rows, prev = [], None
    for label, c in steps:
        share = 100 * c / first
        rows.append(f'<tr><td>{label}</td><td class="num">{n(c)}</td><td class="num">{p(c, prev) if prev else ""}</td>'
                    f'<td class="barcell"><span class="fbar" style="width:{max(share, 0.6):.1f}%"></span></td></tr>')
        prev = c
    foot = f'<p class="small">{note}</p>' if note else ""
    return ('<table class="funnel"><thead><tr><th>Step</th><th class="num">People</th><th class="num">Of previous step</th><th></th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>{foot}')


def table(head, rows, num_from=1):
    th = "".join(f'<th class="{"num" if i >= num_from else ""}">{h}</th>' for i, h in enumerate(head))
    trs = "".join("<tr>" + "".join(f'<td class="{"num" if i >= num_from else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def idea(score, name, what, lay, pro, con):
    lay_html = f'<p><b>In plain words:</b> {lay}</p>' if lay else ""
    return (f'<div class="idea"><div class="idea-head"><span class="score">{score}/10</span><h3>{name}</h3></div>'
            f'<p>{what}</p>{lay_html}<p><b>Strongest case for:</b> {pro}</p><p><b>Strongest case against:</b> {con}</p></div>')


# ------------------------------------------------------------------ numbers used in the prose
m = dp["meta"]
fw, ft, lp = dp["fab_www"], dp["fab_tools"], dp["lp"]
fa, fwv, fs = ft["periods"]["fab_all"], ft["periods"]["fab_wave"], ft["periods"]["fab_steady"]
F = dp["ctplus_funnel"]["by_tier"]
nav, exp_, sup = F["navigator"], F["explorer"], F["supporter"]
art = dp["ctplus_funnel"]["article_paywall"]
pur, cog, pdf, grid, tc = dp["purchases"], dp["cognitive"], dp["pdf"], dp["grid"], dp["tool_ctas"]
ads = cog["unlinked_ads_campaign"]
day = lambda iso: datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d")  # noqa: E731
ads_window = next(g for g in cog["by_source"] if g["group"] == "Google Ads")
cog_ex_ads_runs = cog["runs"] - ads_window["runs"]
cog_ex_ads_pay = cog["to_payment"] - ads_window["to_payment"]
touch = pur["by_touch"]
fab_touch = sum(1 for r in pur["rows"] if {"www floating button", "tools floating button"} & set(r["touches"]))
plus_seen = pur["by_page"].get("/plus", 0) + pur["by_page"].get("both", 0)
coaching_seen = pur["by_page"].get("/coaching", 0) + pur["by_page"].get("both", 0)
with_page = pur["matched"] - pur["by_page"].get("none found", 0)
coaching_bots = next((s["sessions"] for s in lp["coaching"]["sources"] if s["group"] == "Unattributed"), 0)
email_drop = nav["signup_clicks"] - nav["gave_email"]
total_first_month = sum(f["first_month_revenue"] for f in F.values())
generated = datetime.now().strftime("%Y-%m-%d %I:%M%p").lower()

scorecard = table(
    ["Conversion point", "Who saw it (12 weeks)", "What they did", "Money it can be tied to", "Verdict"],
    [
        ["Coaching floating button, website", f"{n(fw['exposed_users'])} site visitors",
         f"{n(fw['landing_users'])} opened /coaching ({fw['ctr']['pct']}%). Phones 2.2%, desktop 0.3%",
         f"In the path of {touch.get('www floating button', 0)} of {pur['matched']} traceable CT+ purchases",
         "<b>Keep.</b> Cheap and it feeds real buyers, but most phone clicks look accidental"],
        ["Coaching floating button, tools", f"{n(fa['exposed_users'])} tool visitors in {fa['days']} days (live since Oct 21)",
         f"{n(fa['click_users'])} clicked ({fa['ctr']['pct']}%), then stayed {ft['session_avg_engagement_sec']:.0f} seconds on /coaching",
         f"In the path of {touch.get('tools floating button', 0)} of {pur['matched']} traceable purchases, all in its first two weeks",
         "<b>Keep and tune.</b> Largest click source on CT, lowest-quality visits"],
        ["Coaching page (/coaching)", f"{n(lp['coaching']['users'])} visitors, about half of them one viral wave",
         f"{nav['signup_clicks']} Navigator sign-up clicks, {nav['stripe_checkouts']} Stripe checkouts",
         f"{nav['paid_subs']} paid Navigators (${n(nav['first_month_revenue'])} first-month revenue), {nav['still_active']} still active",
         "<b>Converts, with two big leaks:</b> the email step and Stripe abandonment"],
        ["CT+ page (/plus)", f"{n(lp['plus']['users'])} visitors (about 65 a week)",
         f"{exp_['signup_clicks']} Explorer and {sup['signup_clicks']} Supporter sign-up clicks",
         f"{exp_['paid_subs']} Explorers, {sup['paid_subs']} Supporter; seen before {plus_seen} of {with_page} traceable purchases",
         "<b>Best page per visitor, starved of traffic.</b> Supporter tier barely sells here"],
        ["Cognitive Assessment page", f"{n(cog['runs'])} visitors, {n(ads_window['runs'])} of them from one ad campaign",
         f"{cog['to_payment']} went to payment ({p(cog['to_payment'], cog['runs'])}), {cog['stripe_checkouts']} Stripe checkouts",
         f"{cog['paid_charges']} sales, ${n(cog['revenue'])}. The ad visitors bought nothing",
         "<b>Weak.</b> Only 1 in 9 checkouts is paid; ads to this page do not work"],
        ["Personality Test PDF", f"{n(pdf['upt_finishers_ga4'])} test finishers, {n(pdf['pdf_page_users'])} reached the PDF page",
         f"About 1 in 10 PDF-page visitors buys ({pdf['per_pdf_page_user']['pct']}%)",
         f"{pdf['paid_charges']} sales, ${n(pdf['revenue'])} ({pdf['per_finisher']['pct']}% of finishers)",
         "<b>The page sells; too few people reach it</b>"],
        ["Product grid (after the email ask)", f"{n(grid['finishers_total'])} finishers of the two main tools that show it",
         f"{grid['any_card_per_100_finishers']} in 100 clicked a card: PDF {grid['cards']['pdf']['per_100_finishers']}, Cognitive {grid['cards']['cognitive']['per_100_finishers']}, CT+ {grid['cards']['plus']['per_100_finishers']}, coaching {grid['cards']['coaching']['per_100_finishers']}",
         f"{grid['cognitive_from_grid']['paid']} Cognitive sales ($70) and {touch.get('product grid', 0)} Navigator",
         "<b>Gets attention, earns little.</b> Its most-clicked card lands on the wrong page"],
        ["Coaching CTA inside tools (Unique Traits)", f"{n(tc['unique_traits']['finishers_ga4'])} finishers",
         f"{tc['unique_traits']['clicks']} clicks ({tc['unique_traits']['ctr']['pct']}%)",
         "No purchase can be tied to it",
         "<b>Not working</b> as built; its tracking tags are also gone"],
    ], num_from=99)

quality = table(["Arrived from", "Sessions", "Avg. engaged time", "Reached page bottom"],
                [[k, n(v[0]), f"{v[1]:.0f} s", p(v[2], v[0])] for k, v in EXTRA["coaching_quality"].items()])

page_rows = [[esc(x["page"].strip("/").replace(".html", "").replace("_", " ")[:30]), n(x["clicks"]), n(x["page_users"] or 0), f"{x['clicks_per_100_users']}"] for x in fs["by_page"][:6]]
cog_rows = [[g["group"], n(g["runs"]), n(g["to_payment"]), p(g["to_payment"], g["runs"]), n(g["paid"]), p(g["paid"], g["runs"], 2)] for g in cog["by_source"]]
src_rows = lambda key: [[s["group"], n(s["sessions"]), p(s["engaged"], s["sessions"], 0)] for s in lp[key]["sources"][:7]]  # noqa: E731
tier_rows = [[t.title(), f["signup_clicks"], f["gave_email"], f["stripe_checkouts"], f["paid_subs"], p(f["paid_subs"], f["stripe_checkouts"], 0),
              f["cancelled_within_14d"], f"${n(f['first_month_revenue'])}"] for t, f in F.items()]
pur_rows = [[k, v, f"{dp['purchases']['coincidence_rate_pct'].get(k, 0)}%"] for k, v in sorted(touch.items(), key=lambda kv: -kv[1])]
grid_rows = [[name, n(c["landing_users"]), c["per_100_finishers"], dest, result] for name, c, dest, result in (
    ("Ultimate Personality PDF Report", grid["cards"]["pdf"], "the report finder page (/getmyreport.html), not the PDF page", "cannot be traced"),
    ("Advanced Cognitive Assessment", grid["cards"]["cognitive"], "the Cognitive Assessment page",
     f"{grid['cognitive_from_grid']['to_payment']} checkouts, {grid['cognitive_from_grid']['paid']} sales"),
    ("Learn more (CT+)", grid["cards"]["plus"], "/plus", "no traceable purchase"),
    ("One-on-one coaching", grid["cards"]["coaching"], "/coaching", f"{touch.get('product grid', 0)} Navigator"))]
month_rows = [[datetime.strptime(x["month"], "%Y-%m").strftime("%B"), n(x["finishers_ga4"] or 0), x["pdf_sales"],
               f"{1000 * x['pdf_sales'] / x['finishers_ga4']:.0f}" if x["finishers_ga4"] and x["month"] != "2026-07" else "n/a"] for x in pdf["monthly"]]

ideas = "".join([
    idea(9, "Label every sign-up button",
         "Add <code>&amp;src=coaching</code> or <code>&amp;src=plus</code> (plus the tier) to the Sign Up links in Wix. The sign-up program already stores a <code>src</code> value on each run (the daily health check uses it), so nothing else has to change.",
         "Each button gets a name tag, so every click and every sale says which page it came from.",
         "Ten minutes of work, and it ends the main blind spot of this audit: today Navigator clicks from /coaching and /plus cannot be told apart, so neither page can be A/B tested.",
         "None of substance. It measures, it does not lift anything by itself."),
    idea(9, "Send the Sign Up click straight to payment",
         f"After clicking Sign Up, visitors land on a GuidedTrack page that asks for their email before Stripe opens. {email_drop} of {nav['signup_clicks']} Navigator clickers ({p(email_drop, nav['signup_clicks'], 0)}) never typed it. Let Stripe collect the email (it asks for it anyway) and keep the email step only for people who say they are already members.",
         "Remove the extra page between the Sign Up button and the payment form.",
         "It is the largest single drop in the Navigator funnel, and two readers wrote in the last two weeks that signing up was confusing. Even recovering a quarter of those clickers at the current checkout completion rate is about 5 more Navigators per 12 weeks.",
         f"The email step is how the program recognises existing members ({nav['already_member']} of the {nav['signup_clicks']} clickers already had a plan) and sends them to their account instead of charging them twice. The checkout function is the team's code, so it needs a developer."),
    idea(8, "Follow up on abandoned checkouts",
         f"{nav['stripe_checkouts'] - nav['stripe_completed']} Navigator checkouts and {cog['stripe_checkouts'] - cog['stripe_completed']} Cognitive Assessment checkouts were opened and left unpaid in 12 weeks, and each one has an email address attached. Turn on Stripe's abandoned-checkout recovery, or send one plain follow-up email a day later.",
         "When someone gets to the payment form and leaves, send them one reminder with a link back.",
         "These are the warmest leads CT has: they chose a product and typed their email. Recovery emails usually win back a few percent, and at $99 a month each recovered Navigator matters.",
         "It needs a small change in the checkout code and clear wording so it does not feel like chasing. Some of the Cognitive checkouts came from low-intent ad clicks and will not return."),
    idea(8, "Point the grid's PDF card at the PDF page",
         f"The PDF card is the most-clicked card in the product grid ({n(grid['cards']['pdf']['landing_users'])} people in 12 weeks), but it opens the report finder, where the visitor has to enter an email and find their report again. For Ultimate Personality Test finishers, link it to the PDF page with their results; hide the card in tools that have no PDF.",
         "People who click 'PDF report' should land on the page that sells the PDF.",
         f"The PDF page turns about 1 visitor in 10 into a buyer and only {n(pdf['pdf_page_users'])} people reached it in 12 weeks. If the card's clickers landed there and bought at even half that rate, that is roughly {round(grid['cards']['pdf']['landing_users'] * pdf['per_pdf_page_user']['pct'] / 200)} extra sales per 12 weeks.",
         "The grid is one shared program used by several tools, so it needs a way to receive the test results. People who click from the Rationality Test may not have taken the personality test at all."),
    idea(7, "Stop the floating button from catching thumbs",
         "On phones, show the button only after the visitor has scrolled or finished a tool, make it a little smaller, and send a GA4 event on every click. Run it for two weeks against the current version before deciding.",
         "",
         "On the website, phones click it 8 times as often as desktops and stay 14 seconds; from the tools they stay 6 seconds. Fewer accidental taps means cleaner /coaching numbers and less annoyance during a test.",
         f"It is in the path of {fab_touch} of the {pur['matched']} purchases that could be traced, more than any other prompt. Anything that hides it risks losing real buyers along with the stray taps, which is why it should be tested, not just changed."),
    idea(7, "Publish more members-only articles",
         f"The first members-only article produced {art['paid_subs']} paying Supporters from {art['stripe_checkouts']} checkouts in its first week (October 16 to 22). The /plus page produced {sup['paid_subs']} Supporter in 12 weeks.",
         "",
         "It is the only thing that has sold the $9 tier in any volume, and it sells it at the moment the reader wants something specific.",
         "One article is a small sample, and part of the result may be novelty. It also depends on the team writing gated pieces regularly."),
    idea(6, "Give /plus more visitors",
         f"/plus gets about 65 visitors a week against several hundred on /coaching, yet it was viewed before {plus_seen} of the {with_page} traceable purchases. Link to it from the tools floating button on alternate weeks, the end-of-tool banner and the newsletter footer, then compare.",
         "",
         "Per visitor it is the stronger page, and it offers the cheaper tiers that coaching-curious visitors may accept.",
         "The purchase sample is small, and visitors who seek out /plus are warmer than visitors pushed to it, so the rate will fall as traffic grows."),
    idea(5, "Rebuild or retire the Unique Traits coaching CTA",
         f"{tc['unique_traits']['clicks']} clicks from {n(tc['unique_traits']['finishers_ga4'])} finishers ({tc['unique_traits']['ctr']['pct']}%) and no traceable sale, despite personalised copy shown before the report. Restore its tracking tags first; then test it after the report instead of before it.",
         "",
         "People who just read about their own difficulties are the natural coaching audience, so a better-placed version could work.",
         "It has had 12 weeks at the top of the page. The floating button on the same pages already does the job with five times the click rate."),
    idea(5, "Find the owner of the Cognitive Assessment ad campaign",
         f"Google Ads campaign {ads['id']} sent {n(ads['runs'])} paid clicks to the Cognitive Assessment page from {day(ads['first'])} to {day(ads['last'])}: {ads['to_payment']} checkouts, {ads['paid']} sales. It is not in the Ads account this project can read, and GA4 is not linked to it.",
         "",
         "Somebody paid for about 2,500 clicks that sold nothing. Knowing who and how much prevents a repeat, and the campaign should not be restarted against this page.",
         "It stopped on its own in early September, so there is no money to save today."),
])

CSS = """
:root{--bg:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--axis:#c3c2b7;--s1:#2a78d6;--s2:#eb6834;--tint:#eef4fc}
@media (prefers-color-scheme:dark){:root{--bg:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;--axis:#383835;--s1:#3987e5;--s2:#d95926;--tint:#16202e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:40px 20px 80px}h1{font-size:30px;line-height:1.2;margin:0 0 6px}h2{font-size:22px;margin:44px 0 10px}h3{font-size:17px;margin:0}
.sub{color:var(--ink2);margin:0 0 26px}.small{font-size:13.5px;color:var(--ink2)}p{margin:10px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}.kpi b{display:block;font-size:26px;line-height:1.15}.kpi span{font-size:13.5px;color:var(--ink2)}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14.5px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--ink2);font-size:13px}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.funnel td.barcell{width:38%;padding-left:14px}.fbar{display:block;height:12px;border-radius:0 4px 4px 0;background:var(--s1)}
svg{width:100%;height:auto;display:block}.tick,.lab{font-size:12.5px;fill:var(--muted)}.lab{fill:var(--ink2)}.val{font-size:12.5px;fill:var(--ink);font-weight:600}
.den{font-weight:400;fill:var(--muted)}.note{font-size:12.5px;fill:var(--ink2)}.axis{stroke:var(--axis);stroke-width:1}.leader{stroke:var(--axis);stroke-width:1;fill:none}
.s1{fill:var(--s1)}.s2{fill:var(--s2)}.bar:hover{opacity:.8}.legend{display:flex;gap:18px;font-size:13.5px;color:var(--ink2);margin:0 0 6px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.idea{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:12px 0}.idea p{font-size:15px;margin:7px 0}
.idea-head{display:flex;align-items:center;gap:12px}.score{background:var(--tint);color:var(--ink);border-radius:8px;padding:3px 9px;font-weight:700;font-size:14px;white-space:nowrap}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.two>*{min-width:0}.card{overflow-x:auto}@media (max-width:760px){.two{grid-template-columns:1fr}}
code{font-size:13.5px;background:var(--tint);padding:1px 5px;border-radius:4px}ul{padding-left:22px;margin:8px 0}li{margin:5px 0}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);font-size:13px;padding:5px 9px;border-radius:6px;opacity:0;transition:opacity .08s;z-index:9}
"""
JS = """
const tip=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(el=>{
  el.addEventListener('mousemove',e=>{tip.textContent=el.dataset.tip;tip.style.opacity=1;tip.style.left=Math.min(e.clientX+12,innerWidth-260)+'px';tip.style.top=(e.clientY-34)+'px'});
  el.addEventListener('mouseleave',()=>{tip.style.opacity=0});
});
"""

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conversion points audit</title><style>{CSS}</style></head><body><main>
<h1>Conversion points audit: what each prompt and page on Clearer Thinking earns</h1>
<p class="sub">Generated {generated} · data from GA4, GuidedTrack and Stripe for the 12 weeks from August 14 to November 5, 2026 (the tools floating button: October 21 to November 5)</p>

<div class="card"><p><b>The short version.</b> In 12 weeks the paid flows produced {nav['paid_subs']} Navigators, {exp_['paid_subs']} Explorers and {sup['paid_subs'] + art['paid_subs']} Supporters (${n(total_first_month + 9 * art['paid_subs'])} of first-month subscription revenue), {pdf['paid_charges']} PDF sales (${n(pdf['revenue'])}) and {cog['paid_charges']} Cognitive Assessment sales (${n(cog['revenue'])}). The two floating buttons are the best prompts CT has: one of them was clicked before {fab_touch} of the {pur['matched']} purchases that could be traced. They also send a lot of accidental phone taps. The pages themselves convert; the money is lost in three places: an email step before payment that {p(email_drop, nav['signup_clicks'], 0)} of Navigator clickers never complete, unpaid Stripe checkouts ({nav['stripe_checkouts'] - nav['stripe_completed']} Navigator, {cog['stripe_checkouts'] - cog['stripe_completed']} Cognitive Assessment), and a product-grid PDF card that sends its clickers to the wrong page.</p></div>

<div class="kpis">
<div class="kpi"><b>{nav['paid_subs']}</b><span>new paid Navigators, {nav['still_active']} still active</span></div>
<div class="kpi"><b>{p(nav['stripe_completed'], nav['stripe_checkouts'], 0)}</b><span>of Navigator checkouts get paid ({nav['stripe_completed']} of {nav['stripe_checkouts']})</span></div>
<div class="kpi"><b>{p(cog['stripe_completed'], cog['stripe_checkouts'], 0)}</b><span>of Cognitive Assessment checkouts get paid ({cog['stripe_completed']} of {cog['stripe_checkouts']})</span></div>
<div class="kpi"><b>{pdf['per_pdf_page_user']['pct']:.0f}%</b><span>of PDF-page visitors buy; only {p(pdf['pdf_page_users'], pdf['upt_finishers_ga4'], 0)} of finishers get there</span></div>
</div>

<h2>Scorecard</h2>
<div class="card scroll">{scorecard}</div>
<p class="small">"Traceable purchases": {pur['matched']} of the {pur['paid_subs_via_signup_flow']} CT+ subscriptions bought through the sign-up flow could be linked to the buyer's earlier page views (method at the end). Treat those counts as a sample of about a third, not a total.</p>

<h2>How often each prompt gets clicked</h2>
<div class="card"><p class="small">Share of the people who could see each prompt and clicked it. The denominators differ (site visitors, tool visitors, test finishers), so compare neighbours, not extremes.</p>{rate_chart()}</div>

<h2>1 and 2. The coaching floating buttons</h2>
<p><b>Website button.</b> {n(fw['exposed_users'])} people visited the website outside /coaching and {n(fw['landing_users'])} of them opened /coaching through the button: {fw['ctr']['pct']}% (95% interval {fw['ctr']['lo']} to {fw['ctr']['hi']}). The split by device is the story: 2.2% of phone visitors clicked against 0.3% of desktop visitors.</p>
<p><b>Tools button.</b> It went live on October 21, in the middle of a viral wave on the Who Attracts You study ({n(fwv['exposed_users'])} tool visitors in three days). Since the wave ended, {n(fs['click_users'])} of {n(fs['exposed_users'])} tool visitors clicked it: {fs['ctr']['pct']}%, about {round(fs['click_users'] / fs['days'])} people a day. Phones 4.9%, desktop 2.6%.</p>
<div class="two">
<div class="card"><h3>What button visitors do on /coaching</h3>{quality}<p class="small">Button visitors leave fast. A real reader of the page needs more than 6 to 14 seconds, so a large share of these clicks are stray taps or quick looks.</p></div>
<div class="card"><h3>Tools button by page, after the wave</h3>{table(["Tool page", "Clicks", "Visitors", "Per 100"], page_rows)}<p class="small">October 24 to November 5.</p></div>
</div>
<p>And still, they sell. Among the {pur['matched']} traceable purchases, the website button was clicked before {touch.get('www floating button', 0)} and the tools button before {touch.get('tools floating button', 0)} (chance alone would explain about half a purchase each). The week after the tools button launched was the best Navigator week of the period, although the coaching email of October 27 landed in the same week, so the two cannot be separated cleanly.</p>

<h2>3 and 4. The coaching page and the CT+ page</h2>
<div class="card"><div class="legend"><span><i style="background:var(--s1)"></i>Navigator sign-up clicks</span><span><i style="background:var(--s2)"></i>New paid Navigators</span></div>{weekly_chart()}<p class="small">Weeks start on Monday. * The last week covers November 2 to 5 only.</p></div>
<div>
<div class="card"><h3>Navigator, from click to payment</h3>{funnel([("Clicked a Navigator Sign Up button", nav['signup_clicks']), ("Typed their email on the next page", nav['gave_email']), ("Were sent to Stripe", nav['reached_checkout']), ("Paid", nav['paid_subs'])], f"Stripe shows {nav['stripe_checkouts']} Navigator checkouts in total, more than the {nav['reached_checkout']} this path sent: the rest start elsewhere (for example a member upgrading from their account). {nav['already_member']} of the clickers were already members. {nav['cancelled_within_14d']} of the {nav['paid_subs']} buyers cancelled within two weeks.")}</div>
<div class="card"><h3>All tiers</h3><div class="scroll">{table(["Tier", "Clicks", "Typed email", "Checkouts", "Paid", "% paid", "Left in 14 days", "1st-month revenue"], tier_rows)}</div><p class="small">Separately, the members-only article paywall sold {art['paid_subs']} Supporter subscriptions from {art['stripe_checkouts']} checkouts in its first week (October 16 to 22).</p></div>
</div>
<div class="two">
<div class="card"><h3>/coaching: {n(lp['coaching']['users'])} visitors</h3>{table(["Came from", "Sessions", "Engaged"], src_rows("coaching"))}<p class="small">GA4 session source. "Unattributed" is {n(coaching_bots)} sessions with almost no engagement (link scanners and a bot burst on September 1). Against engaged sessions only ({n(lp['coaching']['engaged_sessions'])}), the page gets one Navigator sign-up click per {round(lp['coaching']['engaged_sessions'] / nav['signup_clicks'])} visits and one paid Navigator per {round(lp['coaching']['engaged_sessions'] / nav['paid_subs'])}.</p></div>
<div class="card"><h3>/plus: {n(lp['plus']['users'])} visitors</h3>{table(["Came from", "Sessions", "Engaged"], src_rows("plus"))}<p class="small">A tenth of the coaching page's traffic. Of the {with_page} traceable buyers who viewed a landing page before paying, {coaching_seen} had seen /coaching and {plus_seen} had seen /plus.</p></div>
</div>
<p>Which page a Navigator click came from is still unknown: both pages use the same link, with no label. That is the first fix below.</p>

<h2>5. The Cognitive Assessment page</h2>
<div>
<div class="card"><h3>From visit to sale</h3>{funnel([("Opened the page", cog['runs']), ("Clicked through to payment", cog['to_payment']), ("Paid $35", cog['paid_charges'])], f"Stripe counted {cog['stripe_checkouts']} checkouts (some visitors open more than one) and {cog['stripe_completed']} payments. Without the ad campaign: {n(cog_ex_ads_runs)} visitors, {cog_ex_ads_pay} to payment, {cog['paid_charges']} sales, which is {p(cog['paid_charges'], cog_ex_ads_runs)} of visitors.")}</div>
<div class="card"><h3>By where the visitor came from</h3><div class="scroll">{table(["Source", "Visitors", "To payment", "", "Paid", ""], cog_rows)}</div><p class="small">Paid = the visitor's email matches a Stripe payment ({cog['paid_matched_to_runs']} of {cog['paid_charges']} sales matched).</p></div>
</div>
<p><b>An ad campaign nobody seems to own.</b> Google Ads campaign {ads['id']} sent {n(ads['runs'])} clicks to this page between {day(ads['first'])} and {day(ads['last'])}. {ads['to_payment']} of those visitors opened a checkout and none paid. The campaign does not exist in the Google Ads account this project reads, and GA4 shows its clicks with no campaign name, which is what an unlinked account looks like. Worth finding out whose it is and what it cost.</p>

<h2>6. Personality Test PDF</h2>
<div>
<div class="card"><h3>From test to PDF sale</h3>{funnel([("Started the Ultimate Personality Test", pdf['upt_starts_ga4']), ("Finished and gave an email", pdf['upt_finishers_ga4']), ("Opened the PDF page", pdf['pdf_page_users']), ("Bought the $9 PDF", pdf['paid_charges'])], "The first three steps are GA4 counts, which miss visitors with ad blockers; the sales are exact (Stripe).")}</div>
<div class="card"><h3>By month</h3>{table(["Month", "Finishers (GA4)", "PDF sales", "Per 1,000 finishers"], month_rows)}<p class="small">GA4 recorded nothing on the test pages from July 22 to August 10, so July's finisher count is unusable and August's is too low (its true rate is below 8).</p></div>
</div>
<p>The PDF page does its job: about one visitor in ten pays. The limit is how few finishers ever see it ({p(pdf['pdf_page_users'], pdf['upt_finishers_ga4'], 0)}). The October analysis of the report found the same thing from the other side: the PDF card sits only on page 1 of the report and 2.4% of first-time readers click it.</p>

<h2>7. The product grid</h2>
<p>The grid (three shuffled cards plus a CT+ button, shown between the email ask and the rest of the results) lives in the Ultimate Personality Test report and in the Rationality Test report. {grid['any_card_per_100_finishers']} of every 100 finishers click something in it.</p>
<div class="card scroll">{table(["Card", "People who clicked", "Per 100 finishers", "Where it sends them", "Result in 12 weeks"], grid_rows)}</div>
<p>The grid is good at getting a click and poor at what happens next. Its most popular card, the PDF, opens a page that asks the visitor to look up their report by email, although most of them are in the middle of reading that very report. The Cognitive Assessment card sent {grid['cognitive_from_grid']['runs']} visits and made {grid['cognitive_from_grid']['paid']} sales.</p>

<h2>8. Coaching CTAs inside tools</h2>
<ul>
<li><b>Unique Traits Test, before the report</b> (AI-personalised pitch, live since August 19): {tc['unique_traits']['clicks']} clicks from {n(tc['unique_traits']['finishers_ga4'])} finishers, {tc['unique_traits']['ctr']['pct']}% (95% interval {tc['unique_traits']['ctr']['lo']} to {tc['unique_traits']['ctr']['hi']}). No purchase can be tied to it. Its link also lost its tracking tags around September 17, so GA4 now files these visits under "direct".</li>
<li><b>Member dashboard, My Plan:</b> {tc['dashboard']['clicks_to_coaching']} clicks to /coaching.</li>
<li><b>End-of-tool CT+ banner</b> (the perks image at the end of the personality report): {tc['end_banner_plus']['landing_users']} people reached /plus through it, and {touch.get('end-of-tool CT+ banner', 0)} traceable Explorer purchase followed.</li>
</ul>

<h2>Things that looked wrong, and what they turned out to be</h2>
<ul>
<li><b>GA4's standard reports hide on-site promotions.</b> A session keeps the first campaign it arrived with, so a button clicked mid-visit is credited to Google or to an email. Session reports show {fw['session_sessions']} visits from the website button; the page URLs show {n(fw['landing_users'])} people. Every count here uses the URL, not the session.</li>
<li><b>Scanners click the button link too.</b> {n(fw['bot_views_excluded'])} hits on the website button's link came from sessions that never really opened (email link scanners, the September 1 bot burst). They are excluded.</li>
<li><b>GA4 cuts link addresses at 100 characters</b>, which chops the campaign name off the tools button's link. Counts allow for it.</li>
<li><b>Stripe held {dp['ctplus_funnel']['test_sessions_excluded']} test checkouts</b> in the period, nearly all from the daily site health check. Excluded.</li>
<li><b>Tools button clicks ({n(fa['clicks'])}) exceed arrivals on /coaching ({n(fa['landing_views'])} views).</b> About one click in five never loads the page, which fits stray taps closed at once.</li>
</ul>

<h2>What I would do, in order</h2>
{ideas}

<h2>How this was measured, and how far to trust it</h2>
<ul>
<li><b>Sales are exact.</b> Subscriptions, PDF and Cognitive Assessment payments come from Stripe, with team tests and health checks removed. Three independent counts agree: completed checkouts and paid subscriptions ({dp['cross_checks']['ctplus_completed_checkouts_vs_paid_subs'][0]} and {dp['cross_checks']['ctplus_completed_checkouts_vs_paid_subs'][1]}), PDF checkouts and PDF charges ({dp['cross_checks']['pdf_completed_checkouts_vs_charges'][0]} and {dp['cross_checks']['pdf_completed_checkouts_vs_charges'][1]}), Cognitive checkouts and charges ({dp['cross_checks']['cognitive_completed_checkouts_vs_charges'][0]} and {dp['cross_checks']['cognitive_completed_checkouts_vs_charges'][1]}).</li>
<li><b>Sign-up clicks are a floor.</b> They are runs of the GuidedTrack sign-up program; a returning visitor continues an old run, so some clicks are not counted.</li>
<li><b>Visitor counts come from GA4</b> and miss people who block analytics. Rates built from two GA4 numbers are less affected than the raw counts.</li>
<li><b>Tying a purchase to a prompt.</b> GA4 fires an event on the CT+ thank-you page. {pur['ga4_purchase_events']} such events were recorded for {pur['paid_subs_via_signup_flow']} purchases; {pur['matched']} matched a Stripe subscription by time. For each, I looked for views of /coaching and /plus in the previous {m['touch_lookback_days']} days from the same city, device, browser, system and screen size, and read the tag on the link that opened the page. Swapping buyers at random gives a false match about {max(dp['purchases']['coincidence_rate_pct'].values())}% of the time at most, so the pattern is real, but {pur['matched']} purchases is a small sample and "clicked before buying" is not "bought because of".</li>
<li><b>Not measured:</b> which page each sign-up click came from, what happens after the grid's PDF card, and the grid's exact number of views (finishers are used instead).</li>
</ul>
<div class="card"><h3>Traceable purchases by prompt</h3>{table(["Seen in the 3 days before buying", "Purchases (of " + str(pur['matched']) + ")", "Expected by chance"], pur_rows)}<p class="small">One purchase can carry several prompts. "Expected by chance" is the share of random buyer and time pairs that carry the same tag.</p></div>
</main><div id="tip"></div><script>{JS}</script></body></html>"""

OUT.write_text(page)
print("wrote", OUT)
if "--open" in sys.argv:
    subprocess.run(["open", "-a", "Google Chrome", str(OUT)], check=False)
