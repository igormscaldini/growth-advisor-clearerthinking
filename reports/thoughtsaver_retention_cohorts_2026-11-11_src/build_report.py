"""datapoints.json -> reports/thoughtsaver_retention_cohorts_2026-11-11.html (single source: datapoints.json)."""
import datetime as dt
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "thoughtsaver_retention_cohorts_2026-11-11.html"
EV = [f"user_return_{n}d" for n in range(1, 11)]


def fmt_date(iso):
    return dt.date.fromisoformat(iso).strftime("%b %-d")


def day_label(iso):
    return dt.date.fromisoformat(iso).strftime("%a %b %-d")


def timestamp():
    now = dt.datetime.now()
    return now.strftime("%Y-%m-%d %I:%M") + now.strftime("%p").lower()


def curve_svg(pooled):
    """Bars = % of sign-ups reaching N return days, whiskers = 95% Wilson interval."""
    w, h, left, right, top, bottom = 720, 300, 48, 16, 20, 44
    pw, ph = w - left - right, h - top - bottom
    ymax = 20.0
    y = lambda v: top + ph - v / ymax * ph  # noqa: E731
    slot = pw / 10
    bw = slot * 0.56
    parts = [f'<text x="{left - 8}" y="{y(t) + 4:.1f}" class="ax" text-anchor="end">{t}%</text>' for t in (0, 5, 10, 15, 20)]
    parts.append(f'<line x1="{left}" x2="{w - right}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="base"/>')
    for i, ev in enumerate(EV, start=1):
        r = pooled[ev]
        cx = left + slot * (i - 0.5)
        x0 = cx - bw / 2
        top_y = y(r["pct"])
        bar_h = max(y(0) - top_y, 0)
        rad = min(4, bar_h / 2)
        tip = f"{i}+ return days: {r['k']} of {r['n']} sign-ups = {r['pct']}% (95% CI {r['lo']} to {r['hi']}%)"
        bar = (f'<path d="M{x0:.1f},{y(0):.1f} V{top_y + rad:.1f} Q{x0:.1f},{top_y:.1f} {x0 + rad:.1f},{top_y:.1f} '
               f'H{x0 + bw - rad:.1f} Q{x0 + bw:.1f},{top_y:.1f} {x0 + bw:.1f},{top_y + rad:.1f} V{y(0):.1f} Z" class="bar"/>'
               if bar_h > 0 else "")
        parts.append(f'<g class="m"><title>{html.escape(tip)}</title>'
                     f'<rect x="{x0 - 6:.1f}" y="{top}" width="{bw + 12:.1f}" height="{ph}" fill="transparent"/>{bar}'
                     f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(r["lo"]):.1f}" y2="{y(r["hi"]):.1f}" class="ci"/>'
                     f'<line x1="{cx - 5:.1f}" x2="{cx + 5:.1f}" y1="{y(r["hi"]):.1f}" y2="{y(r["hi"]):.1f}" class="ci"/></g>')
        if i in (1, 2):
            parts.append(f'<text x="{cx + bw / 2 + 4:.1f}" y="{top_y + 12:.1f}" class="lbl">{r["pct"]}%</text>')
        parts.append(f'<text x="{cx:.1f}" y="{h - bottom + 18}" class="ax" text-anchor="middle">{i}</text>')
    parts.append(f'<text x="{left + pw / 2:.1f}" y="{h - 6}" class="ax" text-anchor="middle">'
                 'came back on at least this many separate days after signing up</text>')
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Share of sign-ups reaching each number of return days">'
            + "".join(parts) + "</svg>")


def cell(r, scale):
    if r is None:
        return '<td class="na">·</td>'
    if r["n"] == 0:
        return '<td class="na">–</td>'
    alpha = min(r["pct"] / scale, 1) * 0.55
    return (f'<td style="background: rgba(37,99,235,{alpha:.2f})" title="{r["k"]} of {r["n"]}">'
            f'{r["k"]}<span class="p">{r["pct"]:.0f}%</span></td>')


def cohort_table(rows):
    head = "".join(f"<th>{i}+</th>" for i in range(1, 11))
    body = []
    for r in rows:
        flag = "" if r["monotonic"] else ' <span class="flag" title="More people at a higher N than a lower one: a milestone event went missing in GA4">*</span>'
        body.append(f'<tr><th class="wk">{day_label(r["day"])}{flag}</th>'
                    f'<td class="n">{r["entered"]}</td><td class="n">{r["entered_created"]}</td>'
                    f'<td class="n sep">{r["signups"]}</td>'
                    + cell(r["cells"]["onboarding_completed"], 100)
                    + "".join(cell(r["cells"][ev], 50) for ev in EV) + "</tr>")
    return (f'<table class="ct"><thead><tr><th rowspan="2">Day</th><th colspan="2">Onboarding that day</th>'
            f'<th rowspan="2" class="sep">Sign-ups<br>that day</th><th rowspan="2">Completed<br>onboarding</th>'
            f'<th colspan="10">Came back on at least N later days</th></tr>'
            f'<tr><th>entered</th><th>signed up</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>')


def naive_table(naive, pooled, total):
    rows = [f"<tr><td>account_created</td><td class='n'>{naive.get('account_created', 0)}</td><td class='n'>{total}</td></tr>"]
    for ev in ["onboarding_completed"] + EV:
        rows.append(f"<tr><td>{ev}</td><td class='n'>{naive.get(ev, 0)}</td><td class='n'>{pooled[ev]['k']}</td></tr>")
    return ("<table class='nv'><thead><tr><th>Event</th><th>All users firing it in the period</th>"
            "<th>Of the people who signed up in the period</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


COMPARE = [("onboarding_completed", "Completed onboarding")] + [(f"user_return_{n}d", f"Came back on {n}+ later days") for n in (1, 2, 3, 5)]


def compare_table(full):
    """Pooled rates: ad users vs everyone else vs all sign-ups."""
    segs = full["segments"]
    cols = [("From ads", segs["ads"]["pooled"]), ("Everyone else", full["others_pooled"]), ("All sign-ups", segs["all"]["pooled"])]

    def c(r):
        if not r["n"]:
            return "<td>–</td>"
        return f"<td class='n'><b>{r['pct']}%</b><span class='p'>{r['k']} of {r['n']} · CI {r['lo']:.0f} to {r['hi']:.0f}%</span></td>"
    head = "".join(f"<th>{name}</th>" for name, _ in cols)
    signups = "".join(f"<td class='n'><b>{n}</b></td>" for n in (
        segs["ads"]["total_signups"], full["others_signups"], segs["all"]["total_signups"]))
    rows = [f"<tr><td>Sign-ups</td>{signups}</tr>"]
    rows += [f"<tr><td>{label}</td>" + "".join(c(p[ev]) for _, p in cols) + "</tr>" for ev, label in COMPARE]
    return f"<table class='nv cmp'><thead><tr><th></th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def main():
    full = json.loads((HERE / "datapoints.json").read_text())
    d = full["segments"]["ads"]  # Igor (2026-11-12): the report is filtered to users coming from ads
    p, ob = d["pooled"], d["onboarding"]
    share_ads = d["total_signups"] / full["segments"]["all"]["total_signups"] * 100
    others_entered = full["segments"]["all"]["onboarding"]["created_from_entered"] - ob["created_from_entered"]
    oc = d["order_check"]
    cc_ok = all(v["per_day_sum"] == v["pooled"] for v in d["cross_check"].values())
    first, end = d["first_day"], d["end"]
    deep = max((i for i, ev in enumerate(EV, start=1) if p[ev]["k"]), default=0)
    no_entry = d["total_signups"] - ob["created_from_entered"]
    entered_dupes = ob["entered"] - d["naive"].get("onboarding_entered", 0)
    retention_cutoff = (dt.date.fromisoformat(first) + dt.timedelta(days=61)).strftime("%b %-d")

    css = """
:root{--bg:#fff;--ink:#1a1a1a;--ink2:#555;--muted:#888;--line:#ddd;--bar:#2563eb;--flag:#b45309;--card:#f6f7f9}
@media (prefers-color-scheme:dark){:root{--bg:#141518;--ink:#eee;--ink2:#bbb;--muted:#888;--line:#333;--bar:#5b8def;--flag:#f0a050;--card:#1d1f23}}
body{background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;margin:0 0 4px}.sub{color:var(--muted);font-size:14px;margin:0 0 28px}
h2{font-size:20px;margin:40px 0 8px}.note{color:var(--ink2);font-size:14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}
.kpi{background:var(--card);border-radius:10px;padding:14px 16px}.kpi b{font-size:28px;display:block}.kpi span{color:var(--ink2);font-size:14px}
svg{width:100%;max-width:760px;height:auto}.ax{fill:var(--muted);font-size:12px}.lbl{fill:var(--ink2);font-size:12px}
.base{stroke:var(--line);stroke-width:1}.bar{fill:var(--bar)}.ci{stroke:var(--ink2);stroke-width:1.5}.m:hover .bar{opacity:.8}
.scroll{overflow-x:auto}table{border-collapse:collapse;font-size:13px;width:100%}
th,td{padding:5px 5px;text-align:center;border-bottom:1px solid var(--line)}th{color:var(--ink2);font-weight:600;font-size:12px}
.ct td{min-width:34px;font-variant-numeric:tabular-nums}.ct .p{display:block;color:var(--ink2);font-size:10px}
.wk{text-align:left;white-space:nowrap}.na{color:var(--muted)}.n{font-variant-numeric:tabular-nums}.sep{border-left:1px solid var(--line)}
.flag{color:var(--flag);font-weight:700}.nv td:first-child,.nv th:first-child{text-align:left}
.funnel{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}.funnel div{background:var(--card);border-radius:8px;padding:10px 14px}
.funnel b{font-size:22px;display:block}.funnel span{color:var(--ink2);font-size:13px}.arrow{color:var(--muted)}
ol li{margin-bottom:10px}code{font-size:13px}
.cmp td{text-align:left}.cmp .p{display:block;color:var(--ink2);font-size:11px;font-weight:400}
"""
    body = f"""
<main>
<h1>Thought Saver: sign-ups from ads, day by day</h1>
<p class="sub">{timestamp()} · GA4 property "Thought Saver - App And Landing Page", app.thoughtsaver.com only · sign-ups {fmt_date(first)} to {fmt_date(end)}, 2026 · only the 13 events in Samar's sheet · <b>users whose first visit came from an ad</b></p>

<p>The cohort analysis agreed with Samar (thread "clarification on user events", Oct 9-13), filtered to people who came from ads: first visit with
<code>utm_medium=cpc</code>, the marker agreed in the "Note about tracking users from Ads" thread. In this period every one of them came from the Google Ads
Performance Max campaign "[MAX] User Acq. - Classic" (no Meta traffic appears). They are {share_ads:.0f}% of all sign-ups. Each day's sign-ups are followed from their
own <code>account_created</code>, so people who signed up earlier cannot inflate the return counts.</p>

<div class="kpis">
<div class="kpi"><b>{d['total_signups']}</b><span>accounts created from ads, {fmt_date(first)} to {fmt_date(end)}</span></div>
<div class="kpi"><b>{p['onboarding_completed']['pct']:.0f}%</b><span>of them completed onboarding ({p['onboarding_completed']['k']} people)</span></div>
<div class="kpi"><b>{p['user_return_1d']['pct']}%</b><span>came back on at least 1 later day ({p['user_return_1d']['k']} of {p['user_return_1d']['n']}; 95% CI {p['user_return_1d']['lo']:.0f} to {p['user_return_1d']['hi']:.0f}%)</span></div>
<div class="kpi"><b>{p['user_return_2d']['pct']}%</b><span>came back on 2 or more days ({p['user_return_2d']['k']} people); nobody past {deep} so far</span></div>
</div>

<p><b>The bottom line:</b> {100 - p['user_return_1d']['pct']:.0f}% of the people who sign up from an ad never come back on a later day, although
{p['onboarding_completed']['pct']:.0f}% finish onboarding. The big drop is between finishing onboarding and the first return.
Beyond 2 return days the counts are a handful of people at most, too few to read anything into.</p>

<h2>Ad users vs everyone else</h2>
<p class="note">Pooled over all sign-up days old enough for each row. "Everyone else" = the 12 Levers newsletter, Clearer Thinking referrals, direct and organic visitors.
CI = 95% confidence interval; with {full['others_signups']} non-ad sign-ups the intervals are wide, so only a large gap would mean anything.</p>
<div class="scroll">{compare_table(full)}</div>
<p class="note">Ad users come back for a first time about as often as everyone else ({p['user_return_1d']['pct']}% vs {full['others_pooled']['user_return_1d']['pct']}%).
All {p['user_return_2d']['k'] + full['others_pooled']['user_return_2d']['k']} people with 2+ return days came from ads ({full['others_pooled']['user_return_2d']['k']} of
{full['others_pooled']['user_return_2d']['n']} others), but with so few people that could easily be chance. The one large, solid gap is onboarding completion, which most likely
reflects a different sign-up path for non-ad users rather than ad users being more engaged (data issue 3).</p>

<h2>Onboarding funnel</h2>
<div class="funnel">
<div><b>{ob['entered']}</b><span>entered onboarding</span></div><span class="arrow">→</span>
<div><b>{ob['created_from_entered']}</b><span>of them created an account ({ob['entered_to_created']['pct']}%)</span></div><span class="arrow">·</span>
<div><b>{d['total_signups']}</b><span>accounts created in all</span></div><span class="arrow">→</span>
<div><b>{p['onboarding_completed']['k']}</b><span>completed onboarding ({p['onboarding_completed']['pct']}%)</span></div>
</div>
<p class="note">Entered = people who fired <code>onboarding_entered</code> on a given day, summed over days; signed up = those of them who later fired
<code>account_created</code>. {no_entry} of the {d['total_signups']} sign-ups have no <code>onboarding_entered</code> before it in this period (data issue 3).</p>

<h2>Share of sign-ups reaching each number of return days</h2>
<p class="note">All sign-up days that have had at least N days to get there (so the base drops from {p['user_return_1d']['n']} to {p['user_return_10d']['n']} as N grows).
Whiskers are 95% confidence intervals. Hover a bar for the counts.</p>
<div class="scroll">{curve_svg(p)}</div>

<h2>Day by day</h2>
<p class="note">One row per sign-up day. Cells show the number of that day's sign-ups who did it, with the % of the day's sign-ups underneath (darker = higher).
"·" = not enough days have passed yet; "–" = nobody signed up that day.
<span class="flag">*</span> = more people at a higher N than a lower one, which a clean count can't do (data issue 2).
"Onboarding that day" counts different people from the sign-up columns: those who entered onboarding that day, and how many of them went on to sign up.
With {min(r["signups"] for r in d["cohorts"])} to {max(r["signups"] for r in d["cohorts"])} sign-ups a day, single days are noisy; read the pooled numbers above for rates.</p>
<div class="scroll">{cohort_table(d['cohorts'])}</div>

<h2>Why the old numbers looked wrong</h2>
<p class="note">Left: users per event over the same period with no cohort (the view that confused us). Right: the cohort count.
{d['naive'].get('user_return_1d', 0) - p['user_return_1d']['k']} of the {d['naive'].get('user_return_1d', 0)} people who fired <code>user_return_1d</code> in the period
are not among its sign-ups as GA4 sees them: they signed up earlier, or are a sign-up returning on another device (issue 2). All the 8+ day returns are such people.</p>
<div class="scroll">{naive_table(d['naive'], p, d['total_signups'])}</div>

<h2>Data issues to raise with Samar</h2>
<ol>
<li><b>GA4 keeps event data for only two months on this property.</b> Admin → Data settings → Data retention is set to "2 months". This analysis fits inside it
today, but per-person queries will lose Oct 11 around {retention_cutoff} and keep losing a day each day, so it cannot be re-run on this period later.
Switching to 14 months is one click and free (I did not change it).</li>
<li><b>Return milestones go missing for some accounts.</b> {oc['created_then_2d']['user_return_2d']} sign-ups fired <code>user_return_2d</code>, but only
{oc['created_then_1d_then_2d']['user_return_2d']} of them fired <code>user_return_1d</code> before it; {len(d['non_monotonic_days'])} sign-up days show more people at a higher N.
The likeliest cause is a return on another device or browser, which GA4 treats as a different person. Ask Samar whether the GA4 <code>user_id</code> is set on every
event once someone is logged in, so GA4 can join devices. Until then, every return number here is a <b>floor</b>.</li>
<li><b><code>onboarding_entered</code> does not behave as the sheet describes.</b> The sheet says it fires once per user, but summed by day it counts {ob['entered']} people
against {d['naive'].get('onboarding_entered', 0)} distinct people over the period, so it fired on more than one day for some of them ({entered_dupes} extra), and {no_entry} of {d['total_signups']} sign-ups have no <code>onboarding_entered</code> before their <code>account_created</code> in the period
(they may have entered before Oct 11, used "I have an account", or the event did not fire). Worth asking Samar which.
Outside ads the gap is far bigger: only {others_entered} of the {full['others_signups']} non-ad sign-ups entered onboarding before signing up, and
{full['others_pooled']['onboarding_completed']['pct']:.0f}% completed it, against {p['onboarding_completed']['pct']:.0f}% of ad sign-ups. They seem to arrive through a different
sign-up path (for example a link from the 12 Levers newsletter) that skips onboarding; Samar can confirm.</li>
<li><b>Developer traffic lands in the production property.</b> <code>localhost</code> and Vercel preview deploys report to it. This report keeps only
app.thoughtsaver.com; a GA4 data filter or a separate dev property would keep it clean everywhere.</li>
<li><b>The full history may already exist in BigQuery.</b> The property has a BigQuery export (Google Cloud project 200310840257) that is not subject to the
two-month limit. I don't have access; with read access the per-person data would be kept permanently.</li>
</ol>

<h2>How this was measured</h2>
<p class="note">Only the events in Samar's sheet: <code>onboarding_entered</code>, <code>account_created</code>, <code>onboarding_completed</code>, <code>user_return_1d</code> to
<code>user_return_10d</code>. A <b>sign-up cohort</b> = people who fired <code>account_created</code> on app.thoughtsaver.com on that day. They count for an event if they fired it at any
point after their <code>account_created</code> (for returns: on at least N separate later days, per the sheet). Built with GA4 closed funnels, which follow each person, one funnel per
day and event. Independent check: one funnel per event over the whole period gave exactly the same totals as the per-day funnels
({'all matched' if cc_ok else 'MISMATCH, see datapoints.json'}). Confidence intervals: Wilson 95%. Returns counted through {fmt_date(end)}; data pulled {d['pulled_at'].replace('T', ' ')}.
Code: <code>reports/thoughtsaver_retention_cohorts_2026-11-11_src/</code>; tests: <code>tests/test_thoughtsaver_retention_cohorts.py</code>.</p>
</main>"""
    OUT.write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                   f'<title>Thought Saver cohorts</title><style>{css}</style></head><body>{body}</body></html>')
    print("wrote", OUT)


if __name__ == "__main__":
    main()
