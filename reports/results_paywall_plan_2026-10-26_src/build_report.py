"""Build the results-paywall plan report (UPT, Unique Traits Test, Rationality Test).

Usage: .venv/bin/python reports/results_paywall_plan_2026-10-26_src/build_report.py [out.html]
Reads datapoints.json beside this file; every number in the HTML comes from there or is derived
in `derive()` below, so a data refresh is: edit datapoints.json, rerun.
"""
import json, sys, datetime as dt, html
from pathlib import Path

HERE = Path(__file__).parent
D = json.loads((HERE / "datapoints.json").read_text())
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "results_paywall_plan_2026-10-26.html"


def pct(a, b):
    return round(100 * a / b, 1) if b else 0


def derive(d):
    g = d["ga4_90d"]; m = d["ga4_monthly_submits_2026"]; u = d["upt_export"]; t = d["utt_export"]
    upt_month = round(sum(m["UPT"][:9]) / 9)                      # Jan to Sep 2026 average
    utt_months = [x for x in m["UTT"][2:9]]                        # Mar to Sep 2026 (live since March)
    utt_median = sorted(utt_months)[len(utt_months) // 2]
    rat_month = round(sum(m["RAT"][:9]) / 9)
    p1_share = u["page1"] / u["finished_questions"]
    depth = d["upt_report_export"]["depth_pct_of_page1"]       # 2026 curve (report revisits), page 8 included
    upt_viewers = round(upt_month * p1_share)
    hits = {
        "A (after page 1)": upt_viewers,
        "B (after page 2)": round(upt_viewers * depth["p2"] / 100),
        "C (after page 5)": round(upt_viewers * depth["p5"] / 100),
        "D (page 8 only)": round(upt_viewers * depth["p7"] / 100),
    }
    pdf_2026 = d["stripe"]["pdf_monthly"]["count"][-10:]
    return {
        "upt_month": upt_month, "utt_median": utt_median, "rat_month": rat_month,
        "upt_finish_rate": pct(g["UPT"]["submits"], g["UPT"]["starts"]),
        "utt_finish_rate": pct(g["UTT"]["submits"], g["UTT"]["starts"]),
        "rat_finish_rate": pct(g["RAT"]["submits"], g["RAT"]["starts"]),
        "upt_email_of_finished": pct(u["gave_email"], u["finished_questions"]),
        "upt_p1_of_finished": pct(u["page1"], u["finished_questions"]),
        "upt_finished_of_runs": pct(u["finished_questions"], u["runs"]),
        "utt_finished_of_runs": pct(t["finished"], t["runs"]),
        "utt_email_of_finished": pct(t["gave_email"], t["finished"]),
        "utt_all86_of_runs": pct(t["selected_all_86_traits"], t["runs"]),
        "upt_viewers": upt_viewers, "hits": hits,
        "pdf_2026_avg": round(sum(pdf_2026) / len(pdf_2026)),
        "pdf_page_users_month": round(g["report_pages"]["personality-test-pdf-generator"]["users"] / 3),
        "pdf_cta_rate": round(100 * g["cta_click_to_pdf_page_from_report_pages"] / g["UPT"]["submits"], 2),
    }


X = derive(D)
STAMP = dt.datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")


# ----------------------------------------------------------------------------- charts (inline SVG)
def hbars(rows, width=640, bar_h=22, gap=10, label_w=190, gate_after=None, gate_label="proposed gate", unit="%"):
    """Horizontal bars, one hue, direct labels, optional dashed gate line after a row index (0-based)."""
    n = len(rows); vmax = max(v for _, v in rows) or 1
    h = n * (bar_h + gap) + 8
    plot_w = width - label_w - 70
    out = [f'<svg class="chart" viewBox="0 0 {width} {h}" role="img" aria-label="bar chart">']
    for i, (label, v) in enumerate(rows):
        y = 4 + i * (bar_h + gap); w = max(2, plot_w * v / vmax)
        out.append(f'<text x="{label_w - 10}" y="{y + bar_h * 0.7:.0f}" text-anchor="end" class="lbl">{html.escape(label)}</text>')
        vs = f"{v:,}" if isinstance(v, int) else f"{v}"
        out.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" class="bar"><title>{html.escape(label)}: {vs}{unit}</title></rect>')
        out.append(f'<text x="{label_w + w + 8:.1f}" y="{y + bar_h * 0.7:.0f}" class="val">{vs}{unit}</text>')
        if gate_after is not None and i == gate_after:
            gy = y + bar_h + gap / 2
            out.append(f'<line x1="{label_w}" x2="{label_w + plot_w}" y1="{gy:.1f}" y2="{gy:.1f}" class="gate"/>')
            out.append(f'<text x="{label_w + plot_w}" y="{gy - 4:.1f}" text-anchor="end" class="gate-lbl">{html.escape(gate_label)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def columns(labels, values, width=640, h=170, label_every=1):
    n = len(values); vmax = max(values) or 1
    left, bottom, top = 10, 34, 18
    plot_w = width - left - 10; plot_h = h - bottom - top
    slot = plot_w / n; bw = slot * 0.62
    out = [f'<svg class="chart" viewBox="0 0 {width} {h}" role="img" aria-label="column chart">']
    imax = values.index(max(values))
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = left + i * slot + (slot - bw) / 2; bh = plot_h * v / vmax; y = top + plot_h - bh
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" class="bar"><title>{html.escape(lab)}: {v}</title></rect>')
        if i in (0, imax, n - 1):
            out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle" class="val">{v}</text>')
        if i % label_every == 0:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 12}" text-anchor="middle" class="lbl small">{html.escape(lab[2:] if lab.startswith("20") else lab)}</text>')
    out.append(f'<line x1="{left}" x2="{width - 10}" y1="{top + plot_h + 0.5:.1f}" y2="{top + plot_h + 0.5:.1f}" class="axis"/>')
    out.append("</svg>")
    return "\n".join(out)


# ----------------------------------------------------------------------------- content
g = D["ga4_90d"]; u = D["upt_export"]; t = D["utt_export"]; s = D["stripe"]; a = D["audience"]; m = D["ga4_monthly_submits_2026"]
rr = D["upt_report_export"]; depth = rr["depth_pct_of_page1"]; depth24 = u["depth_pct_of_page1"]; names = u["page_names"]
names["p8"] = "AI insights"
pt = rr["pdf_price_test_2025_plus"]

depth_rows = [(f"{k[1]}. {names[k]}", depth[k]) for k in ("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8")]
depth_chart = hbars(depth_rows, gate_after=4, gate_label="proposed gate: before page 6")

funnel_chart = hbars([
    ("UPT: started", g["UPT"]["starts"]), ("UPT: submitted email", g["UPT"]["submits"]),
    ("Unique Traits: started", g["UTT"]["starts"]), ("Unique Traits: submitted", g["UTT"]["submits"]),
    ("Rationality: started", g["RAT"]["starts"]), ("Rationality: submitted", g["RAT"]["submits"]),
], unit="", label_w=230)

pdf_chart = columns(s["pdf_monthly"]["months"], s["pdf_monthly"]["count"], label_every=2)
R = D["rat_export"]
rat_chart = hbars([("1. Reasoning type", R["depth_pct_of_page1"]["p1"]), ("2. Skill percentiles", R["depth_pct_of_page1"]["p2"]),
                   ("3. Twelve skills + tips", R["depth_pct_of_page1"]["p3"]), ("4. Share", R["depth_pct_of_page1"]["p4"])])


def scenario_table(hits, prices=(9, 14), rates=(0.03, 0.06, 0.12)):
    rows = ["<table class='num'><thead><tr><th>Placement (hits a month)</th>" + "".join(f"<th>{int(r*100)}% buy, ${p}</th>" for p in prices for r in rates) + "</tr></thead><tbody>"]
    for k, hv in hits.items():
        rows.append(f"<tr><td>{html.escape(k)} ({hv:,})</td>" + "".join(f"<td>${round(hv * r * p):,}</td>" for p in prices for r in rates) + "</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def options_table(opts):
    opts = sorted(opts, key=lambda o: -o["score"])
    out = ["<div class='options'>"]
    for o in opts:
        out.append(f"""<div class="opt"><div class="opt-head"><span class="score">{o['score']}/10</span><h4>{html.escape(o['name'])}</h4></div>
<p>{o['what']}</p><p><b>For:</b> {o['for']}</p><p><b>Against:</b> {o['against']}</p></div>""")
    out.append("</div>")
    return "\n".join(out)


upt_options = [
    dict(score=8, name="C. Free pages 1 to 5, paid pages 6 to 8 plus the PDF",
         what="Everything the page title promises stays free: snapshot, the 16-cluster analysis, Big Five, Enneagram, Jungian type. The paid part is what only Clearer Thinking has: Distinctive Traits, Predictions about your life (from CT's own outcome data), the AI action plan, and the $9 PDF folded in. Locked items show as teasers in the page-1 contents list and as one line at the foot of pages 2 to 5.",
         **{"for": f"It never contradicts the free promise that ranks the page (goal #3), it sits after the email ask (goal #4 untouched), and it hits the {depth['p5']}% most engaged readers, who have already spent about 24 minutes. CT+ members get it free, which gives the membership a tangible perk.",
            "against": f"Smallest paying audience of the hard gates (about {X['hits']['C (after page 5)']:,} hits a month on 2026 traffic). Pages 6 to 8 must feel premium to justify money; the predictions page is currently flagged as not crystal-ball accurate in its own copy."}),
    dict(score=8, name="F. First make the existing $9 PDF visible in the flow (no gate)",
         what=f"Only {g['cta_click_to_pdf_page_from_report_pages']} clicks reached the PDF page from the report pages in 90 days ({X['pdf_cta_rate']}% of finishers); nearly all PDF buyers arrive from the follow-up email. Put the PDF card at the end of page 5 and page 8 with a preview image, and measure clicks before building anything.",
         **{"for": f"About {X['pdf_page_users_month']} people a month reach the PDF page and {X['pdf_2026_avg']} buy (roughly one in seven), so the offer converts once seen; the problem is exposure. One afternoon of GuidedTrack edits, no payments code, no risk to the free experience.",
            "against": "It is an upsell, not a paywall, so the ceiling is lower; it only tells you how the PDF sells, not how a locked report would."}),
    dict(score=7, name="E. No gate: sell an expanded 'Full Report' at the end of pages 5 and 8",
         what="Keep every current page free and sell more: a longer AI action plan, the PDF, a printable traits map, and the right to re-run and compare later. Same checkout mechanics as C, no content taken away.",
         **{"for": "Zero loss of free value, fully consistent with the mission and the survey; tests willingness to pay with no backlash risk.",
            "against": "Upsells convert below gates, and it needs new content before it can be sold."}),
    dict(score=6, name="D. Gate only page 8 (AI insights) plus the PDF",
         what="The AI page is the one with a real marginal cost (a Gemini call per view) and the one that reads as premium. Lock it, bundle the PDF, leave pages 1 to 7 free.",
         **{"for": "Smallest footprint and a clean story (we charge for the part that costs us money).",
            "against": f"About {X['hits']['D (page 8 only)']:,} hits a month and you are taking away something readers have had free since the page launched; lowest revenue of the gates."}),
    dict(score=5, name="B. Free pages 1 to 2, paid pages 3 to 8",
         what="Snapshot plus the cluster deep-dive stay free; the Big Five, Enneagram and Jungian detail pages, traits, predictions and AI become paid.",
         **{"for": f"Hits {depth['p2']}% of report viewers (about {X['hits']['B (after page 2)']:,} a month), so roughly 1.6x the revenue of C at the same conversion.",
            "against": "The title sells 'Myers-Briggs style, Big 5 and Enneagram'; charging for their detail pages reads as bait and switch, invites refunds and bad reviews, and risks the ranking and the email engine."}),
    dict(score=3, name="A. Free page 1 only (snapshot), everything else paid",
         what="The classic hard paywall: you get your four type names in one image, pay for the rest.",
         **{"for": "Every report viewer sees the price, so the highest theoretical revenue.",
            "against": "Breaks the 'free personality test, instant results' promise that ranks #7 for 'personality test', kills the compare-with-a-friend and team flows, and lands squarely on the survey finding that paywalls feel off-mission (NPS already minus 5)."}),
]

utt_options = [
    dict(score=8, name="U4. Measure first: turn the AI profile into a 'Generate my AI profile' button",
         what="The report is one long page, so we have no idea how many readers reach the AI section. Make it on demand (a click, still free) and record the click. Four weeks of data tell you the hit rate a gate would get.",
         **{"for": "Zero risk, trivial GuidedTrack change, and it also cuts Gemini calls for readers who never scroll that far.",
            "against": "Delays revenue by a month."}),
    dict(score=7, name="U3. Gate the AI profile, distribution plots and a PDF, after the trait lists",
         what="All trait alignments (strong, moderate, absent) stay free. The paid 'Deep Dive' is the AI 'Understanding Your Unique Profile' section (five parts), the per-trait score distributions, and a downloadable PDF.",
         **{"for": f"Readers have invested a median {t['minutes']['median']} minutes and {X['utt_email_of_finished']}% gave an email; the trait results they came for are not withheld, only the synthesis is. The AI section has a real per-view cost.",
            "against": "Hit rate unknown until U4 runs; the single-page report needs a page break and a locked-state card, which is more GuidedTrack surgery than the UPT."}),
    dict(score=5, name="U2. Free strong traits, paid moderate and absent traits plus AI",
         what=f"Show the median {t['strong_traits']['median']} strong alignments, lock the median {t['moderate_traits']['median']} moderate ones, the absent list and the AI profile.",
         **{"for": "Everyone who finishes sees the gate, and moderate traits are where the surprises are.",
            "against": "After a 26-minute test, hiding half of the results is the scenario most likely to produce angry feedback; it also hides the content that makes people share."}),
    dict(score=5, name="U5. Upsell instead: paid 'assess someone else' or compare-with-a-partner report",
         what=f"{X['utt_all86_of_runs']}% of runs already answer all 86 traits; sell a second run for a partner or friend with a side-by-side comparison.",
         **{"for": "New value rather than a wall; a natural gift or couples product.",
            "against": "Speculative demand and new content to build; the current for-someone-else mode is used by under 1% of runs."}),
    dict(score=3, name="U1. Hero counts plus top 3 strong traits free, everything else paid",
         what="The hard version.",
         **{"for": "Maximum hits.", "against": "Longest test on the site, lowest trust tolerance; the backlash risk outweighs the revenue."}),
]

rat_options = [
    dict(score=8, name="R3. No paywall; keep it as the free front door and sharpen the cross-sells",
         what="The report is four short pages whose tips link to free CT mini-tools; it is the tool partners (80,000 Hours, Asimov Press, MailList Accelerator deals) embed under their own brand, and the Cognitive Assessment card already sits on page 1 and 2. Keep it free, tighten the Cognitive Assessment and CT+ cards, and revisit once the UPT gate has numbers.",
         **{"for": f"About {X['rat_month']:,} submits a month come through partner and paid pages whose value to CT is the subscriber, not the report. A wall here hurts the deals that pay per subscriber.",
            "against": "Leaves money on the table if the UPT gate converts well."}),
    dict(score=5, name="R4. Later: sell a 'rationality skills training plan' card on page 3",
         what="New content: a personalised 4-week plan built from the 12 skill scores, delivered as a PDF or email course.",
         **{"for": "Page 3 is where readers see their weak skills and want a fix; it adds value instead of removing it.",
            "against": "Content does not exist yet; demand unproven."}),
    dict(score=3, name="R2. Gate page 3 (12-skill breakdown and tips) only",
         what="Type and the four skill percentiles stay free; the skill-by-skill page becomes paid.",
         **{"for": "Page 3 is the most actionable page.",
            "against": "The tips are links to free CT tools, so you would be charging for a table of contents, and the partner-branded runs would need an exemption."}),
    dict(score=2, name="R1. Gate pages 2 to 4",
         what="Type free, everything else paid.",
         **{"for": "Simple.", "against": "A thin, ten-year-old report cannot carry a price, and the partner pages would need an exemption."}),
]

CSS = """
:root{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a897f;--line:#e6e5e0;--card:#ffffff;--accent:#2a78d6;--accent2:#eb6834;--accent-soft:#eaf2fd;--ok:#0ca30c;--warn:#d03b3b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8d8c84;--line:#33332f;--card:#222221;--accent:#3987e5;--accent2:#d95926;--accent-soft:#1f2d3f}}
:root[data-theme="dark"]{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8d8c84;--line:#33332f;--card:#222221;--accent:#3987e5;--accent2:#d95926;--accent-soft:#1f2d3f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:920px;margin:0 auto;padding:40px 16px 80px}h1{font-size:30px;line-height:1.2;margin:0 0 6px}h2{font-size:22px;margin:48px 0 12px;padding-top:12px;border-top:1px solid var(--line)}h3{font-size:18px;margin:28px 0 8px}h4{margin:0;font-size:16px}
.sub{color:var(--ink2);margin:0 0 24px}.lead{font-size:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:14px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.kpi .v{font-size:26px;font-weight:600;line-height:1.1}.kpi .l{color:var(--ink2);font-size:13px;margin-top:4px}
.chart{width:100%;height:auto;display:block;margin:10px 0 4px}.bar{fill:var(--accent)}.lbl{fill:var(--ink2);font-size:13px}.lbl.small{font-size:11px}.val{fill:var(--ink);font-size:13px}.axis{stroke:var(--line);stroke-width:1}.gate{stroke:var(--accent2);stroke-width:2;stroke-dasharray:6 5}.gate-lbl{fill:var(--accent2);font-size:12px;font-weight:600}
.cap{color:var(--muted);font-size:13px;margin:0 0 6px}table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--ink2);font-weight:600}table.num td:not(:first-child),table.num th:not(:first-child){text-align:right}
.options{display:grid;gap:12px}.opt{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 18px}.opt p{margin:6px 0;font-size:15px}.opt-head{display:flex;align-items:center;gap:12px}.score{background:var(--accent-soft);color:var(--accent);font-weight:700;border-radius:999px;padding:2px 10px;font-size:14px;white-space:nowrap}
ul,ol{padding-left:22px}li{margin:4px 0}.warn{border-left:4px solid var(--accent2);padding-left:14px}.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media (max-width:700px){.two{grid-template-columns:1fr}}
code{font-size:13px;background:var(--accent-soft);padding:1px 5px;border-radius:4px}
"""

def kpi(v, l):
    return f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>'

H = []
H.append(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Results paywall plan</title><style>{CSS}</style></head><body><main>
<h1>Where to put a results paywall: UPT, Unique Traits Test, Rationality Test</h1>
<p class="sub">Plan for Igor's approval, nothing has been changed on any tool. {STAMP}</p>

<div class="card"><p class="lead"><b>Short answer.</b> Gate the Ultimate Personality Test between report page 5 and page 6: everything the page promises (snapshot, cluster, Big Five, Enneagram, Jungian type) stays free, and the paid part is what only CT has (Distinctive Traits, Predictions, the AI action plan) plus the existing $9 PDF folded in, free for CT+ members. For the Unique Traits Test, measure first (make the AI profile an on-demand button for four weeks), then gate the AI synthesis, not the trait results. Do not paywall the Rationality Test: it is the partner front door and its report is too thin to carry a price. On 2026 traffic the whole programme is worth roughly $5k to $20k a year, so treat it as a lever that pays off when paid traffic scales, not as the path to the $120k goal.</p>
<p><b>Why the gate sits after the email ask in every tool:</b> the report already comes after the email step, so goal #4 (opens per campaign) and the MailList Accelerator deals (paid per subscriber) are untouched. Nothing in this plan moves the paywall ahead of the email.</p></div>

<h2>1. What the three tools look like today</h2>
<p class="cap">GA4, {g['window']}. Starts = Accepted Privacy Policy, submitted = Submitted Email (the functional "finished" event).</p>
{funnel_chart}
<div class="kpis">
{kpi(f"{X['upt_month']:,}", "UPT finishers a month, Jan to Sep 2026 average (28k to 49k a month in Oct to Dec 2025 on paid traffic)")}
{kpi(f"{X['utt_median']:,}", "Unique Traits finishers in a typical 2026 month (11,511 in the August viral wave)")}
{kpi(f"{X['rat_month']:,}", "Rationality Test finishers a month, 2026 average (partner pages drive the spikes)")}
{kpi(f"{X['upt_finish_rate']}% / {X['utt_finish_rate']}% / {X['rat_finish_rate']}%", "start to email-submit rate: UPT / Unique Traits / Rationality (90 days)")}
</div>

<h3>Ultimate Personality Test: an eight-page report that loses four in ten readers on page 1</h3>
<p class="cap">GuidedTrack export of the report program (22897), {rr['window']}, {rr['runs_2026']:,} runs: readers opening their report again from the emailed or copied link. Share of page-1 viewers who opened each page. The 2024 in-run curve for first-time readers (May to Aug 2024, {u['page1']:,} readers) is almost identical: pages 2 to 7 at {depth24['p2']}, {depth24['p3']}, {depth24['p4']}, {depth24['p5']}, {depth24['p6']} and {depth24['p7']}%.</p>
{depth_chart}
<div class="kpis">
{kpi(f"{X['upt_finished_of_runs']}%", "of runs answer every question")}
{kpi(f"{X['upt_email_of_finished']}%", "of finishers give an email")}
{kpi(f"{X['upt_p1_of_finished']}%", "of finishers open report page 1")}
{kpi(f"{u['median_minutes_by_deepest_page']['1']} to {u['median_minutes_by_deepest_page']['7']} min", "median time spent, readers who stop at page 1 vs. reach page 7")}
</div>
<ul>
<li>The curve has one cliff and then a slope: {100 - depth['p2']:.0f}% leave after the snapshot page, and from page 2 on each page keeps roughly 90% of the previous one, down to {depth['p8']}% on the AI page. Readers who get past the snapshot tend to read on; the gate position decides how many of them see a price, not whether the report "works".</li>
<li>Paid-ads visitors go shallower (2024 in-run data): {u['organic_vs_cpc']['cpc_p5_of_p1']}% of them reach page 5 against {u['organic_vs_cpc']['organic_p5_of_p1']}% of organic visitors. A gate after page 5 is therefore mostly seen by organic readers, the ones who also become the engaged subscribers (UPT subscribers open at {a['upt_subscriber_open_rate']}).</li>
<li>The PDF card on page 1 is clicked by {rr['pdf_click_pct_of_page1_2026']}% of 2026 report viewers and the Cognitive Assessment card by {rr['iq_click_pct_of_page1_2026']}%: soft, one-line offers already draw a few percent at the top of the report.</li>
<li>Report revisits are large: /personality_report.html had {g['report_pages']['personality_report.html']['views']:,} views from {g['report_pages']['personality_report.html']['users']:,} users in 90 days, mostly from the emailed link. The unlock must travel with the link, or buyers will hit the wall again.</li>
</ul>

<h3>Unique Traits Test: one long page, 26 minutes of effort, no depth signal</h3>
<div class="kpis">
{kpi(f"{X['utt_finished_of_runs']}%", "of runs finish (longest test on the site)")}
{kpi(f"{t['minutes']['median']} min", f"median time to the report (p25 {t['minutes']['p25']}, p75 {t['minutes']['p75']})")}
{kpi(f"{X['utt_email_of_finished']}%", "of finishers give an email (90 days; 73% since launch)")}
{kpi(f"{t['strong_traits']['median']} / {t['moderate_traits']['median']}", "median strong / moderate trait alignments per report")}
</div>
<p>{t['note']} {X['utt_all86_of_runs']}% of runs answer all 86 traits. The report shows the counts, the strongest traits, the moderate ones, an AI-written five-part profile (a Gemini call per view), the absent traits, and a retake offer. There is no way to know today how many readers scroll to the AI section, which is why the plan measures before it charges.</p>

<h3>Rationality Test: short quiz, four-page report, the partner front door</h3>
<p class="cap">GuidedTrack run export, {R['window']}, {R['runs']:,} runs, {R['report_p1']:,} report viewers.</p>
{rat_chart}
<div class="kpis">
{kpi(f"{R['depth_pct_of_page1']['p4']}%", "of report viewers reach page 4 (the flattest curve of the three tools)")}
{kpi(f"{R['minutes_median_report_viewers']} min", "median time to the report")}
{kpi(f"{R['iq_click_pct_of_page1']}%", "of report viewers click the Cognitive Assessment card")}
{kpi(f"{R['by_source']['partner']['runs']:,}", "partner-branded runs in 2026 (Asimov Press, 80,000 Hours)")}
</div>
<p>Four short pages (type, four skill percentiles, twelve skills with tips linking to free CT tools, share) keep {R['depth_pct_of_page1']['p3']}% of readers to page 3 and {R['depth_pct_of_page1']['p4']}% to page 4, so a gate here would be seen by most finishers; the question is what it would sell. The page already carries the Cognitive Assessment card with a randomised price: the $35 card is clicked by {R['iq_price_test'].get('35', {}).get('click_pct', '?')}% of readers and the $17.50 card by {R['iq_price_test'].get('17.50', {}).get('click_pct', '?')}%, the same lesson as the PDF test (a lower price buys no extra clicks). The product grid between pages 1 and 2 is seen by {R['product_grid_pct_of_page1_since_jul_2026']}% of readers since July 2026. {g['RAT']['landings']:,} landings became {g['RAT']['submits']:,} finishers in 90 days; paid and partner traffic come in bursts (26,544 runs in April 2026, 23,406 of them from ads).</p>

<h2>2. What readers already pay for, and what they said about paywalls</h2>
<p class="cap">Stripe, one-off $9 Personality PDF purchases by month ({s['pdf_sales_since_2025_01']} since January 2025, ${s['pdf_net_usd_since_2025_01']:,} net). October 2026 runs to the 26th.</p>
{pdf_chart}
<ul>
<li><b>The PDF converts when seen.</b> About {X['pdf_page_users_month']} people a month reach the PDF page and {X['pdf_2026_avg']} buy, roughly one in seven. But only {g['cta_click_to_pdf_page_from_report_pages']} clicks in 90 days came from the report pages themselves ({X['pdf_cta_rate']}% of finishers); {g['pdf_page_sessions_by_source']['(direct) / (none)']} of {sum(g['pdf_page_sessions_by_source'].values()):,} PDF-page sessions were direct, i.e. the follow-up email. Demand exists; exposure inside the report does not.</li>
<li><b>The price test already ran, and it says $9 is not too high.</b> The UPT randomises the PDF price shown on the report. Since 2025, the $9 card was clicked by {pt['$9']['click_pct']}% of readers who saw it ({pt['$9']['clicked']:,} of {pt['$9']['shown']:,}), the $4.50 card by {pt['$4.50']['click_pct']}% ({pt['$4.50']['clicked']} of {pt['$4.50']['shown']:,}) and the $19 card by {pt['$19']['click_pct']}% ({pt['$19']['clicked']} of {pt['$19']['shown']:,}). Halving the price bought no extra clicks; doubling it cut clicks four-fold. Revenue per view is therefore highest at $9 of the points tested, and the untested band between $9 and $19 is where a gate price test should sit (the plan proposes $9 against $14). The same GuidedTrack <code>*experiment</code> machinery runs the gate test.</li>
<li><b>Competitors charge far more for less.</b> Truity's full report is {D['competitors']['Truity full report']}, 16Personalities' suites {D['competitors']['16Personalities premium suites']}, the official MBTI {D['competitors']['Official MBTI (mbtionline)']} (third-party 2026 figures, unverified on the vendors' sites). CT's $9 anchor is low, and most of these sites gate the detail, not the type.</li>
<li><b>The audience warned us.</b> In the March 2026 survey (n={a['survey_n']}) paywalls were named as off-mission, NPS is {a['nps']}, and only {a['ct_plus_awareness']} knew CT+ existed. Buyers are {a['buyers_us_share']} US; India is {a['india_signups']}. A gate that keeps the promised results free and makes CT+ worth more is defensible to this audience; a wall in front of the type is not.</li>
<li><b>Benchmarks.</b> News paywalls convert {D['benchmarks']['news_paywall_stop_conversion_monthly_median']} of paywall hits a month for anonymous visitors and about {D['benchmarks']['known_user_conversion_piano']} for known users (see the September benchmark report). Every reader who hits a CT gate is a known user: we have their email and 20 minutes of their attention. The scenarios below assume 3% to 12% of gate hits buy; the PDF page's one-in-seven is the optimistic bound for a pre-qualified audience.</li>
</ul>

<h2>3. Placement options, scored</h2>
<h3>Ultimate Personality Test</h3>
{options_table(upt_options)}
<h3>Unique Traits Test</h3>
{options_table(utt_options)}
<h3>Rationality Test</h3>
{options_table(rat_options)}

<h2>4. What it is worth on today's traffic</h2>
<p class="cap">UPT, monthly. {X['upt_month']:,} finishers x {X['upt_p1_of_finished']}% who open the report = about {X['upt_viewers']:,} report viewers a month; hits = viewers who reach the gate under the 2026 depth curve (page 8 gate: readers who finish page 7). Gross, before Stripe fees and refunds, before any cannibalisation of today's {X['pdf_2026_avg']} PDF sales a month (about ${X['pdf_2026_avg'] * 9:,}).</p>
{scenario_table(X['hits'])}
<ul>
<li>Option C at $9 and a 6% conversion is about ${round(X['hits']['C (after page 5)'] * 0.06 * 9):,} a month, roughly what the PDF makes today; the bundle replaces it rather than adding to it unless conversion or price is higher. The honest framing: on 2026 organic traffic this is a $5k to $20k a year lever. In Oct to Dec 2025 the UPT ran at 8 to 14 times today's volume on paid traffic; a gate that converts even 3% at $9 then adds about $2.5 to $4 per 100 finishers, which partly funds the ads.</li>
<li>Unique Traits: {X['utt_median']:,} finishers in a typical month, all of whom see the report; if half reach the AI section, about {round(X['utt_median'] * 0.5):,} hits, so ${round(X['utt_median'] * 0.5 * 0.03 * 9):,} to ${round(X['utt_median'] * 0.5 * 0.12 * 9):,} a month at $9. The August wave would have multiplied that by eight for one month.</li>
<li>Rationality: not modelled, no gate recommended.</li>
</ul>

<h2>5. Recommended plan</h2>
<div class="card">
<h3 style="margin-top:0">Phase 0 (week 1): measure and expose, no payments code</h3>
<ol>
<li>UPT: add a PDF card with a preview image at the foot of page 5 and page 8 (option F) and record the click in the run data; today the card only shows on page 1.</li>
<li>Unique Traits: turn the AI profile into a free "Generate my AI profile" button and record clicks (option U4). This is the hit-rate measurement for a later gate.</li>
<li>Both: add <code>paywall_seen</code>, <code>checkout_clicked</code> and <code>unlocked</code> variables now so the baseline exists before anything is charged.</li>
<li>Confirm the 2026 first-time-reader depth curve from the refreshed main export (streaming as this is written; the revisit curve above and the 2024 in-run curve already agree).</li>
</ol>
<h3>Phase 1 (weeks 2 to 3): build the gate behind a flag</h3>
<ol>
<li><b>Stripe:</b> one product "Ultimate Personality Test: Full Report" with a $9 price and a $14 test price; metadata <code>tool=upt</code>. Tell <code>data_layer._charge_bucket</code> apart from the PDF by metadata, or the dashboard will file these as PDF sales.</li>
<li><b>Two Vercel routes in this repo</b> (same pattern and basic auth as the members-only check): <code>POST /api/report-checkout</code> creates a Checkout Session whose success URL is the reader's own report link plus <code>&amp;unlock={{CHECKOUT_SESSION_ID}}</code>, with the email pre-filled; <code>GET /api/report-unlock</code> answers 1 for a paid session id, for an email with a prior purchase, or for an active CT+ member (reusing the member-check lookup). The GuidedTrack checkout program the team runs on Firebase is the alternative; it needs Belen or Josh and cannot carry a per-reader success URL today.</li>
<li><b>GuidedTrack</b> (report program 22897, in Igor's account): at the start of page 6, if not unlocked, show the gate card (what is inside, price, CT+ members free, "Already bought it? Enter your email"), call the checkout service, and return. On report start, verify an <code>unlock</code> parameter through the service and append it to the emailed and copied report links so revisits stay open. Send a receipt email with the unlocked link.</li>
<li><b>Teasers:</b> lock icons on items 6 to 8 of the page-1 contents list and a one-line note at the foot of pages 2 to 5, so nobody discovers the wall by surprise.</li>
<li>Test end to end with <code>?paywall=1</code> only (Igor and the team), including a real $9 purchase and refund, a CT+ member, and a revisit from the emailed link.</li>
</ol>
<h3>Phase 2 (weeks 4 to 8): launch at 50%, read weekly</h3>
<ol>
<li>GuidedTrack <code>*experiment</code> with three arms: control (no gate), gate at $9, gate at $14. Four weeks or 1,500 gate hits per arm, whichever comes first.</li>
<li>Primary metrics: gate hits, checkout clicks, paid, revenue per report viewer. Guardrails that pause the test if they move more than 10% against control: email-submit rate, page 1 to page 2 continuation, the end-of-tool feedback rating, and the GSC click-through rate for "personality test" (weekly, mobile and desktop separately, as in the ranking plan).</li>
<li>Decide: keep the winning arm at 100%, add the PDF email campaign's link to the unlocked report, and retire the standalone PDF card if the bundle outsells it.</li>
</ol>
<h3>Phase 3: Unique Traits, only with the Phase 0 numbers</h3>
<p>If at least 40% of finishers click "Generate my AI profile", gate it (option U3) with the same routes, a page break before the AI section, and the trait lists untouched. Below that, keep it free and sell the PDF instead.</p>
<h3>Rationality Test</h3>
<p>No gate. Tighten the Cognitive Assessment card copy on pages 1 and 2 and keep the product grid. Revisit after the UPT numbers exist. Note that the in-run report program (id 2263) is not in Igor's GuidedTrack account, so any change there needs its owner.</p>
</div>

<h2>6. Risks and how the plan handles them</h2>
<table><thead><tr><th>Risk</th><th>Why it matters here</th><th>Mitigation in the plan</th></tr></thead><tbody>
<tr><td>Ranking for "personality test" (goal #3)</td><td>The title promises a free test with instant results; a wall in front of the type would invite pogo-sticking and bad reviews.</td><td>Gate only after every promised framework; GSC CTR is a pause guardrail; teasers make the paid part explicit.</td></tr>
<tr><td>Audience trust (paywalls "off-mission", NPS minus 5)</td><td>The Rigorous Rationalist persona is the loudest critic and the CT+ prospect.</td><td>CT+ members free (the gate becomes a membership perk); the free part is larger than any competitor's; copy says where the money goes.</td></tr>
<tr><td>Email engine and MLA deals (goal #4)</td><td>Partners pay per subscriber; the newsletter's best cohort comes from the UPT.</td><td>The gate sits after the email step everywhere; partner pages can be exempted by the <code>brand_data</code> variable if ever needed.</td></tr>
<tr><td>Support load: lost links, "I already paid"</td><td>Report revisits are 36k views a quarter.</td><td>Unlock travels in the link and in a receipt email; email lookup recognises prior buyers.</td></tr>
<tr><td>Revenue mis-filed in the dashboard</td><td>$9 charges are classified as PDF sales by amount.</td><td>Classify by Stripe metadata before launch.</td></tr>
<tr><td>Team conventions (Firebase payments)</td><td>CT's other paid flows create sessions via Firebase.</td><td>Either path works; the Vercel path is proposed because it carries the per-reader success URL and is under Igor's control. Flag to Spencer before build.</td></tr>
<tr><td>Cannibalising the PDF</td><td>The PDF is the entry product (50% of buyers).</td><td>Bundle it; measure bundle sales against the PDF baseline of about {X['pdf_2026_avg']} a month.</td></tr>
</tbody></table>

<h2>7. What I need from you to start</h2>
<ol>
<li>Scope: UPT first (option C), Unique Traits measured then gated (U4 then U3), Rationality untouched. Yes or changes.</li>
<li>Price arms: $9 and $14, PDF included in both. Or your own numbers.</li>
<li>CT+ members get the full report free. Yes or no.</li>
<li>Payments path: new Vercel routes in this repo (my proposal) or the team's Firebase checkout (needs Belen or Josh).</li>
<li>Permission to edit the two UPT report programs and the Unique Traits programs in your GuidedTrack account, behind a flag, after the usual pull-and-diff.</li>
</ol>

<h2>Appendix: data notes</h2>
<ul>
<li>{D['generated_note']}</li>
<li>UPT depth: the chart uses the report program's own 2026 export (report revisits, {rr['runs_2026']:,} runs, complete). The main test's export (about 3.4 GB, 5,199 columns) stalled server-side after 188k rows (August 2024) on the first pass, so first-time-reader depth is from May to August 2024; a second pass with a longer timeout is running. {rr['note']}</li>
<li>Rationality: {R['note']} The first two passes stopped in June 2015 on that NUL byte (a parser bug on my side).</li>
<li>Unique Traits numbers are complete ({t['since_launch']['runs']:,} live runs since launch). The export does not record device.</li>
<li>GA4 <code>cta_click</code> counts use the standard <code>linkUrl</code> dimension; the tag's <code>link_url</code> parameter is not registered as a custom dimension.</li>
<li>Monthly GA4 submits by tool are in the datapoints file; October 2026 is partial.</li>
</ul>
</main></body></html>""")

OUT.write_text("\n".join(H), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
