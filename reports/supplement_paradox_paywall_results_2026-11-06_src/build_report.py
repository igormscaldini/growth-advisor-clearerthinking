"""Render the Supplement Paradox paywall assessment as HTML.

    .venv/bin/python reports/supplement_paradox_paywall_results_2026-11-06_src/build_report.py [out.html]

Every number comes from datapoints.json beside this file (written by analysis.py); the wording
lives here. Rerun fetch_data.py and analysis.py first to refresh the figures.
"""
import datetime as dt
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
D = json.loads((HERE / "datapoints.json").read_text())
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "supplement_paradox_paywall_results_2026-11-06.html"
STAMP = dt.datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")

# Read by hand in Gmail on 2026-11-06 (search: to:info@clearerthinking.org, subject "supplement(s)", Oct 16 to Nov 6):
# six messages reached Igor's mailbox, two auto-replies, one copy of the newsletter itself and three written
# by two readers (one disputes the vitamin D section, one calls the Oct 30 send spam). None mentions the paywall.
REPLIES_BY_PEOPLE, REPLY_AUTHORS, REPLIES_ABOUT_PAYWALL = 3, 2, 0

F, R, E, S = D["funnel"], D["rates"], D["edition"], D["supporter_baseline"]
V, RT, C, B = D["engaged_send_vs_baseline"], D["ratings"], D["context"], D["benchmarks"]


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def esc(s) -> str:
    return html.escape(str(s))


# ----------------------------------------------------------------------------- charts (inline SVG)
def hbars(rows, highlight, width=640, bar_h=22, gap=10, label_w=250, fmt=lambda v: f"{v}"):
    """Ranked horizontal bars with one row emphasised (accent) and the rest in the context gray.
    rows = [(label, value)], highlight = the label to emphasise. Every bar is labelled directly."""
    vmax = max(v for _, v in rows) or 1
    h = len(rows) * (bar_h + gap) + 8
    plot_w = width - label_w - 64
    out = [f'<svg class="chart" viewBox="0 0 {width} {h}" role="img" aria-label="bar chart">']
    for i, (label, v) in enumerate(rows):
        y = 4 + i * (bar_h + gap)
        w = max(2, plot_w * v / vmax)
        hot = label == highlight
        out.append(f'<text x="{label_w - 10}" y="{y + bar_h * 0.7:.0f}" text-anchor="end" class="lbl{" hot" if hot else ""}">{esc(label)}</text>')
        out.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" class="{"bar" if hot else "ctx"}"><title>{esc(label)}: {fmt(v)}</title></rect>')
        out.append(f'<text x="{label_w + w + 8:.1f}" y="{y + bar_h * 0.7:.0f}" class="val{" hot" if hot else ""}">{fmt(v)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def weekly_columns(bins, width=640, h=190):
    """Sign-ups per 7-day bin: bins before the send in the context gray, bins since in the accent."""
    n = len(bins)
    vmax = max(b["count"] for b in bins) or 1
    left, right, bottom, top = 10, 10, 40, 30
    plot_w, plot_h = width - left - right, h - bottom - top
    slot = plot_w / n
    bw = slot * 0.62
    base = top + plot_h
    out = [f'<svg class="chart" viewBox="0 0 {width} {h}" role="img" aria-label="Supporter sign-ups per week">']
    first_after = next(i for i, b in enumerate(bins) if b["after"])
    gx = left + first_after * slot                      # the send sits on the left edge of the first accent bin
    out.append(f'<line x1="{gx:.1f}" x2="{gx:.1f}" y1="{top - 14}" y2="{base}" class="gate"/>')
    out.append(f'<text x="{gx - 6:.1f}" y="{top - 4}" text-anchor="end" class="gate-lbl">paywall sent, Oct 16</text>')
    months_seen = set()
    for i, b in enumerate(bins):
        x = left + i * slot + (slot - bw) / 2
        if b["count"]:
            bh = plot_h * b["count"] / vmax
            out.append(f'<rect x="{x:.1f}" y="{base - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4" class="{"bar" if b["after"] else "ctx"}">'
                       f'<title>Week from {b["start"]}: {b["count"]} sign-up{"s" if b["count"] != 1 else ""}</title></rect>')
            out.append(f'<text x="{x + bw / 2:.1f}" y="{base - bh - 6:.1f}" text-anchor="middle" class="val">{b["count"]}</text>')
        month = dt.date.fromisoformat(b["start"]).strftime("%b")
        if month not in months_seen:                    # one tick label per month, under its first bin
            months_seen.add(month)
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 16}" text-anchor="middle" class="lbl small">{month}</text>')
    out.append(f'<line x1="{left}" x2="{width - right}" y1="{base + 0.5:.1f}" y2="{base + 0.5:.1f}" class="axis"/>')
    out.append("</svg>")
    return "\n".join(out)


def kpi(v, l):
    return f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>'


# ----------------------------------------------------------------------------- derived wording inputs
eng = V["engaged_send"]
base_eds = V["baseline_editions"]
SP_LABEL = "Oct 16, Supplement Paradox"
unsub_rows = [(name, 100 * b["unsub_per_open"]) for name, b in base_eds.items()] + [(SP_LABEL, 100 * eng["unsub_per_open"])]
unsub_chart = hbars(unsub_rows, SP_LABEL, label_w=260, fmt=lambda v: f"{v:.2f}%")
u = V["unsub_per_open"]

NAMES = {  # rating-page slugs -> short titles
    "the-supplement-paradox": "The Supplement Paradox",
    "should-you-steelman-people-you-disagree-with": "Steelman people you disagree with",
    "how-and-why-to-reason-more-complexly": "Reason more complexly",
    "is-what-youve-been-taught-about-biases-wrong": "Cognitive biases",
    "in-defense-of-unanswerable-questions-they-are-not-pointless-or-unscientific": "Unanswerable questions",
    "career-advice-from-conversations-with-experts": "Career advice",
    "what-our-scientific-findings-can-teach-you-about-happiness": "Happiness findings",
    "what-capitalists-and-marxists-agree-and-disagree-about": "Capitalists and Marxists",
    "what-stands-between-you-and-reality": "Between you and reality",
    "psychology-words-that-dont-mean-what-you-think": "Psychology words",
}


def short(slug: str) -> str:
    if slug in NAMES:
        return NAMES[slug]
    return "Meditation myths" if slug.startswith("four-things-you-probably-don-t-know-about-med") else slug.replace("-", " ")[:34]


sp_r = RT["supplement_paradox"]
rating_rows = [(short(k), round(100 * v["low"] / v["n"], 1), v["n"]) for k, v in RT["others"].items()]
rating_rows.append((short("the-supplement-paradox"), round(100 * RT["low_share"], 1), sp_r["n"]))
rating_rows.sort(key=lambda r: -r[1])
rating_chart = hbars([(f"{name} (n={n})", v) for name, v, n in rating_rows],
                     f"{short('the-supplement-paradox')} (n={sp_r['n']})", label_w=300, fmt=lambda v: f"{v:.0f}%")
weekly_chart = weekly_columns(S["weekly"])

non_member_email = F["email_non_member_visitors"]
ci_lo, ci_hi = R["email_paid_per_non_member_visitor_ci"]
members_reached = F["existing_members_reached_max"]
first_three_opens = sum(s["unique_opens"] for s in D["sends"][:3])
same_or_worse = sum(1 for v in RT["others"].values() if v["low"] / v["n"] >= RT["low_share"])
clickers_per = round(1 / R["email_click_per_opener"], -2)
weeks_after = [b for b in S["weekly"] if b["after"]]
complaints = RT["paywall_feedback_any_article_since_send"]
last_send = D["sends"][-1]
web_clicks = sum(s["web_version_clicks_verified"] for s in D["sends"])
plus_clicks = sum(s["plus_footer_clicks_verified"] for s in D["sends"])


def sends_table():
    rows = ["<table class='num'><thead><tr><th>Send</th><th>Recipients</th><th>Unique opens</th><th>Open rate</th>"
            "<th>Paywall clicks (human)</th><th>Paid</th><th>Unsubscribes</th><th>Spam reports</th></tr></thead><tbody>"]
    for s in D["sends"]:
        rows.append(f"<tr><td>{esc(s['label'])}</td><td>{s['recipients']:,}</td><td>{s['unique_opens']:,}</td><td>{pct(s['open_rate'])}</td>"
                    f"<td>{s['paywall_clickers_verified']}</td><td>{s['paid']}</td><td>{s['unsubscribes']:,}</td><td>{s['spam_reports']}</td></tr>")
    rows.append(f"<tr><td>Web version of the article (box under the cut)</td><td></td><td></td><td></td><td>{F['web_runs']} visits</td>"
                f"<td>{F['paid_web']}</td><td></td><td></td></tr>")
    rows.append(f"<tr class='tot'><td>Total</td><td>{E['recipients']:,}</td><td>{E['unique_opens']:,}</td><td>{pct(E['open_rate'])}</td>"
                f"<td>{F['paywall_clickers_verified']} + {F['web_runs']}</td><td>{F['checkouts_paid']}</td><td>{E['unsubscribes']:,}</td><td>{E['spam_reports']}</td></tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def funnel_table():
    steps = [
        ("Emails delivered, four sends", f"{E['delivered']:,}", ""),
        ("Opened the email (unique opens)", f"{F['unique_opens']:,}", f"{pct(E['open_rate'])} of recipients"),
        ("Clicked the paywall card, bot-filtered (beehiiv)", f"{F['paywall_clickers_verified']}", f"{pct(F['paywall_clickers_verified'] / F['unique_opens'], 2)} of openers"),
        ("Loaded the offer page from the email (GuidedTrack)", f"{F['email_visitors']}", f"{pct(R['email_click_per_opener'], 2)} of openers"),
        ("of them, already members and let straight in", f"{F['email_members_by_hash']}", ""),
        ("of them, non-members who saw the offer", f"{non_member_email}", ""),
        ("Loaded the offer page from the web article", f"{F['web_runs']}", f"{F['web_post_users']:,} Google Analytics users viewed the web version"),
        ("Opened Stripe checkout", f"{F['checkouts_opened']}", f"{pct(F['checkouts_opened'] / (non_member_email + F['web_non_member_visitors']))} of non-member visitors"),
        ("Paid ($9 a month Supporter)", f"{F['checkouts_paid']}", f"{pct(R['paid_per_checkout'], 0)} of checkouts; {F['paid_email']} from the email, {F['paid_web']} from the web"),
        (f"Still paying on {D['window']['end'][:10]}", f"{F['paid_still_active']}", "none cancelled or refunded"),
    ]
    rows = ["<table class='funnel'><tbody>"]
    for label, value, note in steps:
        sub = label.startswith("of them")
        rows.append(f"<tr class='{'subrow' if sub else ''}'><td>{esc(label)}</td><td class='n'>{value}</td><td class='note'>{esc(note)}</td></tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


CSS = """
:root{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a897f;--line:#e6e5e0;--card:#ffffff;--accent:#0b6fd3;--accent2:#eb6834;--accent-soft:#eaf2fd;--ctx:#a9b0bb}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8d8c84;--line:#33332f;--card:#222221;--accent:#4a95ee;--accent2:#e2703f;--accent-soft:#1f2d3f;--ctx:#6b7079}}
:root[data-theme="dark"]{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8d8c84;--line:#33332f;--card:#222221;--accent:#4a95ee;--accent2:#e2703f;--accent-soft:#1f2d3f;--ctx:#6b7079}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:920px;margin:0 auto;padding:40px 16px 80px}h1{font-size:30px;line-height:1.2;margin:0 0 6px}h2{font-size:22px;margin:48px 0 12px;padding-top:12px;border-top:1px solid var(--line)}h3{font-size:18px;margin:28px 0 8px}
.sub{color:var(--ink2);margin:0 0 24px}.lead{font-size:18px;margin:0}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:14px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.kpi .v{font-size:26px;font-weight:600;line-height:1.1}.kpi .l{color:var(--ink2);font-size:13px;margin-top:4px}
.chart{width:100%;height:auto;display:block;margin:10px 0 4px}.bar{fill:var(--accent)}.ctx{fill:var(--ctx)}.lbl{fill:var(--ink2);font-size:13px}.lbl.hot,.val.hot{fill:var(--ink);font-weight:600}.lbl.small{font-size:11px}.val{fill:var(--ink);font-size:13px}.axis{stroke:var(--line);stroke-width:1}.gate{stroke:var(--accent2);stroke-width:2;stroke-dasharray:6 5}.gate-lbl{fill:var(--ink2);font-size:12px;font-weight:600}
.cap{color:var(--muted);font-size:13px;margin:0 0 6px}table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--ink2);font-weight:600}
table.num td:not(:first-child),table.num th:not(:first-child){text-align:right}tr.tot td{font-weight:600;border-bottom:0}
table.funnel td.n{text-align:right;font-weight:600;font-size:16px;white-space:nowrap;font-variant-numeric:tabular-nums}table.funnel td.note{color:var(--ink2)}table.funnel tr.subrow td:first-child{padding-left:28px;color:var(--ink2)}table.funnel tr.subrow td.n{font-weight:400;font-size:14px}
.scroll{overflow-x:auto}ul,ol{padding-left:22px}li{margin:6px 0}.warn{border-left:4px solid var(--accent2);padding-left:14px}
blockquote{margin:10px 0;padding:8px 14px;border-left:3px solid var(--line);color:var(--ink2)}
"""

H = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Supplement Paradox paywall results</title><style>{CSS}</style></head><body><main>
<h1>The Supplement Paradox paywall: what it earned and what it cost</h1>
<p class="sub">Clearer Thinking's first members-only cut inside a newsletter. Data from the first send ({D['window']['start']}) to {D['window']['end']}, {D['window']['days']:.0f} days. Report built {STAMP}.</p>

<div class="card"><p class="lead"><b>Short answer.</b> The paywall brought in {F['checkouts_paid']} new $9 a month Supporters (${D['revenue']['new_mrr_usd']} of monthly recurring revenue) from {F['unique_opens']:,} opens, and all {F['paid_still_active']} are still paying three weeks later. I can find no measurable damage: unsubscribes per opener were inside the range of the four previous editions, ratings were in the usual range, and one reader complained in writing. It is a small, real, low-risk result. It is not a growth lever at this volume, and the reason is specific: about 1 opener in {clickers_per:,.0f} clicked through to the offer, while 1 in {round(1 / R['email_paid_per_non_member_visitor'])} of the non-members who did click went on to pay.</p></div>

<div class="kpis">
{kpi(F['checkouts_paid'], f"new paying members, all on the $9 Supporter tier ({F['paid_email']} from the email, {F['paid_web']} from the web article)")}
{kpi(f"${D['revenue']['new_mrr_usd']}", f"new monthly recurring revenue, against ${C['mrr_usd']:,.0f} total today")}
{kpi(f"{F['email_visitors']} + {F['web_runs']}", "people who reached the offer page: from the email + from the web article")}
{kpi(pct(R['email_paid_per_non_member_visitor']), f"of non-member email visitors paid ({F['paid_email']} of {non_member_email}; 95% interval {pct(ci_lo, 0)} to {pct(ci_hi, 0)})")}
{kpi(pct(R['paid_per_opener'], 3), f"of openers paid ({F['checkouts_paid']} of {F['unique_opens']:,})")}
</div>

<h2>1. The funnel, step by step</h2>
<p class="cap">Three systems measured it independently: beehiiv (clicks on the paywall card, one link per subscriber), GuidedTrack (the offer page only records a visit when a real browser runs it) and Stripe (checkouts and payments). The steps span four orders of magnitude, so this is a table, not a bar chart.</p>
<div class="scroll">{funnel_table()}</div>
<ul>
<li><b>The leak is between the email and the offer page.</b> Once a non-member reached the offer, the page did its job: {F['checkouts_opened']} of {non_member_email + F['web_non_member_visitors']} opened checkout and {F['checkouts_paid']} of those {F['checkouts_opened']} paid. Ten US metro dailies in the Lenfest data saw {pct(B['checkout_completion_mobile'], 0)} (mobile) to {pct(B['checkout_completion_desktop'], 0)} (desktop) of offer-page visitors complete a purchase, so {pct(R['email_paid_per_non_member_visitor'])} is ordinary, not weak.</li>
<li><b>The paywall card was still one of the most clicked things in the email.</b> It drew {F['paywall_clickers_verified']} human clicks, against {web_clicks} on the "read online" title link and {plus_clicks} on the Clearer Thinking Plus line in the footer. The full article sits in the email, so few readers click anything; the cut came at the last section ("What should you do?"), after most of the text.</li>
<li><b>How many readers actually saw the cut is unknown.</b> Email has no scroll tracking, so "{pct(R['email_click_per_opener'], 2)} of openers clicked" mixes two things I cannot separate: readers who never reached the end, and readers who reached it and declined.</li>
<li><b>Existing members:</b> {F['email_members_by_hash']} were recognised by their email link and let straight in, and {F['web_typed_member']} more got in from the web version by typing their email. That is at most {members_reached} of the {C['members_at_send']} members at the time, so the members-only section was opened by roughly one member in {round(C['members_at_send'] / members_reached)}.</li>
</ul>

<h2>2. Where the sales came from</h2>
<div class="scroll">{sends_table()}</div>
<p>The edition went out in four sends: a first one to part of the whole list, the engaged segment a few hours later (both with a subject-line test), a resend on Oct 19 to frequent openers who had not opened, and on Oct 30 everyone who had not been sent it yet. That last group is {last_send['recipients']:,} subscribers outside the engaged segment, almost all with under 1% opens in six months: it produced {last_send['paywall_clickers_verified']} human paywall clicks, {last_send['paid']} sales and {last_send['spam_reports']} of the edition's {E['spam_reports']} spam reports. That is a list-hygiene matter, not a paywall one, but it means the paywall result really comes from the {first_three_opens:,} opens of the first three sends. It also means the resend to engaged non-openers planned on Oct 22 is not what went out on Oct 30: the send excluded everyone who had already <i>received</i> the edition, not everyone who had opened it, so apart from the {D['sends'][2]['recipients']:,} frequent openers of Oct 19, engaged readers who missed it were not sent it again.</p>

<h2>3. Was it more than the usual trickle of Supporters?</h2>
<p class="cap">New Supporter subscriptions per week, counted in 7-day blocks from the moment of the first send. Team test subscriptions (cancelled the same day) are excluded. The gray bar just before the send is the Oct 14 sign-up made through the offer page during testing (section 7).</p>
{weekly_chart}
<p>Yes. In the {S['baseline_days']:.0f} days before the paywall existed ({S['baseline_window']}) Clearer Thinking gained {S['baseline_signups']} Supporters, one every three weeks. The {S['test_days']:.0f} days since the send brought {S['test_signups']}, every one of them through the paywall page: {S['ratio']:.1f} times the weekly rate, and unlikely to be chance (one-sided p = {S['p_one_sided']:.3f}, exact test on two Poisson rates). {'No one who clicked the paywall link bought a higher tier instead.' if D['cross_checks']['other_tier_subs_by_paywall_visitors'] == 0 else str(D['cross_checks']['other_tier_subs_by_paywall_visitors']) + ' people who clicked the paywall link bought a higher tier instead.'}</p>
<p>The shape matters as much as the total: all {weeks_after[0]['count']} arrived in the first week and the next {len(weeks_after) - 1} weeks brought {sum(b['count'] for b in weeks_after[1:])}. A paywalled article sells when it lands and then stops, so the yield is per article, not per month.</p>

<h2>4. Did it cost anything?</h2>
<h3>Unsubscribes: no sign of it</h3>
<p class="cap">Unsubscribes per unique opener, the Oct 16 send to the "Engaged Subs" segment against the four previous article editions sent to the same segment. Per opener, not per recipient, because the delivery problem that week changed how many people saw the email at all.</p>
{unsub_chart}
<p>The paywalled edition lost {pct(u['value'], 2)} of its openers ({eng['unsubscribes']:,} of {eng['unique_opens']:,}); the four before it lost between {pct(u['min'], 2)} and {pct(u['max'], 2)}. It sits {abs(u['z']):.1f} standard deviations {'below' if u['z'] < 0 else 'above'} their average, well inside normal variation. Spam reports on that send were {eng['spam_reports']}, against {min(b['spam_reports'] for b in base_eds.values())} to {max(b['spam_reports'] for b in base_eds.values())} on the earlier editions. Across all four sends the edition had {E['unsubscribes']:,} unsubscribes ({pct(E['unsub_per_delivered'], 2)} of delivered).</p>

<h3>Ratings: in the usual range, and noisy</h3>
<p class="cap">Share of "Subpar" or "Bad" ratings per article, all rating-box runs since August. Email link scanners click every rating once, so small differences mean nothing.</p>
{rating_chart}
<p>{sp_r['low']} of {sp_r['n']} ratings were low ({pct(RT['low_share'], 0)}; 95% interval {pct(RT['low_share_ci'][0], 0)} to {pct(RT['low_share_ci'][1], 0)}), against {pct(RT['others_low_share'], 0)} across the other articles, which range from {pct(RT['others_low_range'][0], 0)} to {pct(RT['others_low_range'][1], 0)}. {same_or_worse} of the other {len(RT['others'])} articles scored the same or worse without a paywall.</p>

<h3>What readers wrote</h3>
<ul>
<li>{RT['written_feedback_count']} readers left a written comment on this article's rating page. {'None mentions' if RT['written_feedback_mentioning_paywall'] == 0 else str(RT['written_feedback_mentioning_paywall']) + ' mention'} the paywall: the critical ones argue with the content (vitamin D, the choice of trials, the AI image).</li>
<li>{len(complaints)} comment about paywalls has appeared on any article since the send, left on {complaints[0]['date'] if complaints else 'n/a'} under the next edition (the steelman article, which had no paywall of its own):
{''.join(f'<blockquote>"{esc(c["text"])}" (rated {esc(c["rating"])})</blockquote>' for c in complaints)}</li>
<li>Of the replies to the sends that reached Igor's mailbox, {REPLIES_BY_PEOPLE} were written by people ({REPLY_AUTHORS} readers: one disputes the vitamin D section, one calls the Oct 30 send spam). {'None mentions' if REPLIES_ABOUT_PAYWALL == 0 else str(REPLIES_ABOUT_PAYWALL) + ' mention'} the paywall. Replies go to info@clearerthinking.org, so there may be others I cannot see.</li>
</ul>
<p class="warn">The March 2026 audience survey (n = 539) listed "paywalls seen as off-mission" among readers' frictions. One written complaint from about {round(first_three_opens / 1000):,}k opens is a mild reaction to a first paywall, but one edition cannot show what a paywall every week would do to goodwill.</p>

<h2>5. How it compares with paywalls elsewhere</h2>
<p>The benchmark report of Sep 23 found that news sites convert a median of {pct(B['paid_per_paywall_stop_median_low'], 2)} to {pct(B['paid_per_paywall_stop_median_high'], 2)} of the readers their paywall stops in a month, and the top tenth of publishers {pct(B['paid_per_paywall_stop_top_decile'], 1)}. Clearer Thinking's {F['checkouts_paid']} sales are {pct(R['paid_per_opener'], 3)} of openers. The two are not the same measure (an opener is not a reader stopped by a wall, and most openers never reach the end of a long email), so the fair statement is narrow: if even one opener in ten reached the cut, the conversion per reader stopped was about {pct(F['checkouts_paid'] / (F['unique_opens'] / 10), 2)}, below the news median; if it was one in fifty, about {pct(F['checkouts_paid'] / (F['unique_opens'] / 50), 2)}, in line with it. Those two ratios are illustrations, not measurements.</p>

<h2>6. What this test cannot tell you</h2>
<ul>
<li><b>Five sales is a small sample.</b> The true conversion of offer-page visitors could be anywhere from {pct(ci_lo, 0)} to {pct(ci_hi, 0)}. A second paywalled article could plausibly sell 2 or 10.</li>
<li><b>Retention is unknown.</b> The first renewals fall between Nov 16 and Nov 22. Past Supporters churned at about 4 to 5% a month (measured Sep 14), but those were supporters by choice, not readers who paid to finish one article.</li>
<li><b>There was no control group.</b> Unsubscribes, ratings and comments are the only goodwill measures, compared against earlier editions on different topics.</li>
<li><b>The week was unusual.</b> Opens were about a quarter below normal for the engaged segment ({pct(eng['open_rate'])} against {pct(V['open_rate']['min'])} to {pct(V['open_rate']['max'])} before) because of the beehiiv delivery bug, so fewer people than usual had the chance to hit the paywall. Opens happen before a reader can see the cut, so the paywall did not cause that.</li>
</ul>

<h2>7. Loose ends found while measuring</h2>
<ul>
<li><b>"Already a member?" confused some readers.</b> {F['email_typed_non_member']} of the {non_member_email} non-member email visitors typed an address into that box and were told no membership was found. The typed addresses are not stored, so I cannot prove why, but the likeliest reading is that "the email you subscribed with" sounds like the newsletter subscription. Rewording it to "paying member" is a one-line change.</li>
<li><b>One buyer's first view of the article after paying was the locked page</b> (Oct 19, no access key in the address); they got in about 40 seconds later by typing their email. The other four went straight in. Inferred from timestamps in the two page logs, so the cause is unknown; worth a test purchase on a phone.</li>
<li><b>One Supporter subscription from Oct 14, two days before the send, is still active.</b> It came through the offer page during testing and is not counted above. If it was a team test, it should be cancelled and refunded.</li>
<li><b>The Stripe source tag is being overwritten.</b> On {F['checkout_refs_overwritten']} of the {F['checkouts_opened']} checkouts the <code>client_reference_id</code> that should name the source (email or web) held an analytics tracking id instead (it starts with "ga-", most likely written by the Stripe-to-GA4 purchase tracking), so this report attributes sales by matching email hashes and timestamps. Fine for five sales, fragile for fifty.</li>
</ul>

<h2>8. Verdict and next steps</h2>
<div class="card"><p><b>Verdict: worth repeating, on evidence that it is safe, not on evidence that it is lucrative.</b> One paywalled article added {F['checkouts_paid']} members to a base of {C['active_subscribers']} (the goal is 100) at no visible cost in unsubscribes or ratings. At ${D['revenue']['new_mrr_usd']} a month it does not move the revenue goal, and it will not until many more readers reach the offer page.</p></div>
<ol>
<li><b>Run it again and make offer-page visits per opener the number to beat.</b> This edition scored {pct(R['email_click_per_opener'], 2)}. The offer page converts normally, so the next test should change what happens before it: say near the top what members get at the end, and consider cutting earlier than the final section.</li>
<li><b>Check the five on Nov 23.</b> If most renew, a paywalled article is worth roughly {F['checkouts_paid']} long-lived Supporters; if most cancel, it is worth about ${D['revenue']['new_mrr_usd']} once.</li>
<li><b>Fix the four loose ends above before the next one</b>, the member box wording and the source tag first.</li>
</ol>

<h2>How this was checked</h2>
<ul>
<li>The headline counts were recounted from a second source each: sales from Stripe's subscription list ({D['cross_checks']['supporter_subs_since_send_from_stripe_list']}, same as the {F['checkouts_paid']} completed checkouts), email visitors from beehiiv's bot-filtered clicks ({F['paywall_clickers_verified']}, against {F['email_visitors']} in GuidedTrack; {D['cross_checks']['verified_clickers_with_gt_run']} people appear in both), all visitors from Google Analytics ({F['ga4_pitch_page_users']} users, against {F['email_visitors'] + F['web_runs']}).</li>
<li>Every one of the {D['cross_checks']['gt_visitors']} email visitors is also among beehiiv's {F['paywall_clickers_all']} raw clickers; the other {F['paywall_clickers_all'] - F['paywall_clickers_verified']} raw clicks are link scanners that never ran the page.</li>
<li>{F['pre_send_runs_excluded']} visits to the offer page before the first send are team tests and are excluded; no team address appears after it.</li>
<li>The analysis code is unit-tested on hand-worked cases and on two synthetic data sets built to give a known null result and a known positive one (tests/test_supplement_paradox_paywall.py).</li>
</ul>
<p class="cap">Sources: beehiiv API (per-post stats and per-link clicks), GuidedTrack run exports (programs 38912, 38913, 38551), Stripe (Checkout Sessions of the paywall Payment Link, subscriptions since Jul 1), Google Analytics 4, Gmail. Built by reports/supplement_paradox_paywall_results_2026-11-06_src/.</p>
</main></body></html>"""

assert chr(8212) not in H, "no em dashes in reports"
OUT.write_text(H)
print(OUT)
