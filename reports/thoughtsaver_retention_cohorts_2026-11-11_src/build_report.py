"""datapoints.json -> reports/thoughtsaver_retention_cohorts_2026-11-11.html (single source: datapoints.json)."""
import datetime as dt
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "thoughtsaver_retention_cohorts_2026-11-11.html"
EV = [f"user_return_{n}d" for n in range(1, 11)]


def fmt_date(iso):
    d = dt.date.fromisoformat(iso)
    return d.strftime("%b %-d")


def week_label(iso):
    d = dt.date.fromisoformat(iso)
    return f"{fmt_date(iso)} to {(d + dt.timedelta(days=6)).strftime('%b %-d')}"


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
    parts = []
    for t in (0, 5, 10, 15, 20):
        parts.append(f'<text x="{left - 8}" y="{y(t) + 4:.1f}" class="ax" text-anchor="end">{t}%</text>')
    parts.append(f'<line x1="{left}" x2="{w - right}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="base"/>')
    for i in range(1, 11):
        r = pooled[str(i)]
        cx = left + slot * (i - 0.5)
        x0 = cx - bw / 2
        top_y = y(r["pct"])
        bar_h = max(y(0) - top_y, 0)
        rad = min(4, bar_h)
        tip = f"{i}+ return days: {r['k']} of {r['n']} sign-ups = {r['pct']}% (95% CI {r['lo']} to {r['hi']}%)"
        parts.append(f'<g class="m"><title>{html.escape(tip)}</title>'
                     f'<rect x="{x0 - 6:.1f}" y="{top}" width="{bw + 12:.1f}" height="{ph}" fill="transparent"/>'
                     f'<path d="M{x0:.1f},{y(0):.1f} V{top_y + rad:.1f} Q{x0:.1f},{top_y:.1f} {x0 + rad:.1f},{top_y:.1f} '
                     f'H{x0 + bw - rad:.1f} Q{x0 + bw:.1f},{top_y:.1f} {x0 + bw:.1f},{top_y + rad:.1f} V{y(0):.1f} Z" class="bar"/>'
                     f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(r["lo"]):.1f}" y2="{y(r["hi"]):.1f}" class="ci"/>'
                     f'<line x1="{cx - 5:.1f}" x2="{cx + 5:.1f}" y1="{y(r["hi"]):.1f}" y2="{y(r["hi"]):.1f}" class="ci"/>'
                     f'<line x1="{cx - 5:.1f}" x2="{cx + 5:.1f}" y1="{y(r["lo"]):.1f}" y2="{y(r["lo"]):.1f}" class="ci"/></g>')
        if i in (1, 2, 3):
            parts.append(f'<text x="{cx + bw / 2 + 4:.1f}" y="{top_y + 12:.1f}" class="lbl">{r["pct"]}%</text>')
        parts.append(f'<text x="{cx:.1f}" y="{h - bottom + 18}" class="ax" text-anchor="middle">{i}</text>')
    parts.append(f'<text x="{left + pw / 2:.1f}" y="{h - 6}" class="ax" text-anchor="middle">'
                 'came back on at least this many separate days after signing up</text>')
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Share of sign-ups reaching each number of return days">'
            + "".join(parts) + "</svg>")


def cell(r):
    if r is None:
        return '<td class="na">not yet</td>'
    alpha = min(r["pct"] / 30, 1) if r["pct"] else 0
    return (f'<td style="background: rgba(37,99,235,{alpha * 0.55:.2f})" title="{r["k"]} of {r["n"]}">'
            f'{r["pct"]:.0f}%<span class="k">{r["k"]}</span></td>')


def cohort_table(cohorts, view, n_key):
    head = "".join(f"<th>{i}+</th>" for i in range(1, 11))
    rows = []
    for c in cohorts:
        n = c[n_key]
        if n is None:
            continue
        flag = "" if c["monotonic"] or view != "to_date" else ' <span class="flag" title="More users at a higher N than a lower one: a milestone event went missing in GA4">*</span>'
        rows.append(f'<tr><th class="wk">{week_label(c["cohort"])}{flag}</th><td class="n">{n}</td>'
                    + "".join(cell(c[view][str(i)]) for i in range(1, 11)) + "</tr>")
    return (f'<table class="ct"><thead><tr><th>Sign-up week</th><th>Sign-ups</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def naive_table(naive, pooled):
    rows = []
    for i, ev in enumerate(EV, start=1):
        rows.append(f"<tr><td>{ev}</td><td class='n'>{naive.get(ev, 0)}</td><td class='n'>{pooled[str(i)]['k']}</td></tr>")
    return ("<table class='nv'><thead><tr><th>Event</th><th>All users firing it, last 28 days</th>"
            "<th>Of the sign-ups since Sep 14 (cohort method)</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def weekly_table(weekly, end):
    rows = []
    for wk, ev in weekly.items():
        y, w = int(wk[:4]), int(wk[4:])
        monday_d = dt.date.fromisocalendar(y, w, 1)
        if wk < "202632" or monday_d + dt.timedelta(days=6) > dt.date.fromisoformat(end):
            continue  # before account_created existed, or a partial week
        monday = monday_d.isoformat()
        oe = ev.get("onboarding_entered", [0, 0])
        ac = ev.get("account_created", [0, 0])
        oc = ev.get("onboarding_completed", [0, 0])
        share = f"{ac[0] / oe[0] * 100:.0f}%" if oe[0] else ""
        per = f"{ac[1] / ac[0]:.1f}" if ac[0] else ""
        rows.append(f"<tr><td>{week_label(monday)}</td><td class='n'>{oe[0]}</td><td class='n'>{ac[0]}</td>"
                    f"<td class='n'>{share}</td><td class='n'>{per}</td><td class='n'>{oc[0]}</td></tr>")
    return ("<table class='nv'><thead><tr><th>Week</th><th>Users entering onboarding</th><th>Users firing account_created</th>"
            "<th>Ratio</th><th>account_created events per user</th><th>Users completing onboarding</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def main():
    d = json.loads((HERE / "datapoints.json").read_text())
    pt, pw, ps = d["pooled_to_date"], d["pooled_window"], d["pooled_strict_to_date"]
    cc_ok = all(v["per_cohort_sum"] == v["pooled_two_step"] for v in d["cross_check"].values())
    first, last = d["cohorts"][0]["cohort"], d["cohorts"][-1]["cohort"]
    last_end = (dt.date.fromisoformat(last) + dt.timedelta(days=6)).isoformat()
    win_last_end = (dt.date.fromisoformat(d["window_cohorts"][-1]) + dt.timedelta(days=6)).isoformat()
    deep = sum(1 for i in range(5, 11) if pt[str(i)]["k"])

    css = """
:root{--bg:#fff;--ink:#1a1a1a;--ink2:#555;--muted:#888;--line:#ddd;--bar:#2563eb;--flag:#b45309;--card:#f6f7f9}
@media (prefers-color-scheme:dark){:root{--bg:#141518;--ink:#eee;--ink2:#bbb;--muted:#888;--line:#333;--bar:#5b8def;--flag:#f0a050;--card:#1d1f23}}
body{background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0}
main{max-width:860px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;margin:0 0 4px}.sub{color:var(--muted);font-size:14px;margin:0 0 28px}
h2{font-size:20px;margin:40px 0 8px}p,li{color:var(--ink)}.note{color:var(--ink2);font-size:14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}
.kpi{background:var(--card);border-radius:10px;padding:14px 16px}.kpi b{font-size:28px;display:block}.kpi span{color:var(--ink2);font-size:14px}
svg{width:100%;height:auto}.ax{fill:var(--muted);font-size:12px}.lbl{fill:var(--ink2);font-size:12px}
.base{stroke:var(--line);stroke-width:1}.bar{fill:var(--bar)}.ci{stroke:var(--ink2);stroke-width:1.5}
.m:hover .bar{opacity:.8}
.scroll{overflow-x:auto}table{border-collapse:collapse;font-size:13px;width:100%}
th,td{padding:6px 6px;text-align:center;border-bottom:1px solid var(--line)}th{color:var(--ink2);font-weight:600}
.ct td{min-width:40px}.ct .k{display:block;color:var(--ink2);font-size:11px}.wk{text-align:left;white-space:nowrap}
.na{color:var(--muted);font-size:11px}.n{font-variant-numeric:tabular-nums}.flag{color:var(--flag);font-weight:700}
.nv td:first-child,.nv th:first-child{text-align:left}
ol li{margin-bottom:10px}code{font-size:13px}
"""
    body = f"""
<main>
<h1>Thought Saver: who comes back after signing up</h1>
<p class="sub">{timestamp()} · GA4 property "Thought Saver - App And Landing Page", app.thoughtsaver.com only · sign-ups {fmt_date(first)} to {fmt_date(last_end)}, 2026 · returns counted through {fmt_date(d['end'])}</p>

<p>This is the cohort analysis agreed with Samar (thread "clarification on user events", Oct 9-13). The old event totals mixed in people who
signed up months ago, which is how <code>user_return_8d</code> could beat <code>user_return_7d</code>. Here each person is followed from their own sign-up.</p>

<div class="kpis">
<div class="kpi"><b>{d['total_signups']}</b><span>accounts created, {fmt_date(first)} to {fmt_date(last_end)}</span></div>
<div class="kpi"><b>{pt['1']['pct']}%</b><span>came back on at least 1 later day ({pt['1']['k']} people; 95% CI {pt['1']['lo']:.0f} to {pt['1']['hi']:.0f}%)</span></div>
<div class="kpi"><b>{pt['2']['pct']}%</b><span>came back on 2 or more days ({pt['2']['k']} people)</span></div>
<div class="kpi"><b>{pt['5']['k']}</b><span>{'person' if pt['5']['k'] == 1 else 'people'} reached 5+ return days; {pt['10']['k']} reached 10</span></div>
</div>

<p><b>The bottom line:</b> about 7 in 8 people who create an account never come back on a later day. Most of the drop happens before the
first return, so that is where to look first (the first-session experience and what brings someone back on day two). Beyond 3 return days
the numbers are single people, too few to read anything into.</p>

<h2>Share of sign-ups reaching each number of return days</h2>
<p class="note">All sign-ups whose week has had at least N days to get there (so the base drops from {pt['1']['n']} to {pt['10']['n']} as N grows).
Whiskers are 95% confidence intervals. Hover a bar for the counts.</p>
<div class="scroll">{curve_svg(pt)}</div>

<h2>By sign-up week, all returns so far</h2>
<p class="note">Each cell: % of that week's sign-ups who reached N return days (count underneath). "Not yet" = the week's last sign-ups have not had N days.
Older weeks have had more time, so compare rows with the next table instead.
<span class="flag">*</span> = a higher N has more people than a lower one, which a clean count can't do (see data issue 2).</p>
<div class="scroll">{cohort_table(d['cohorts'], 'to_date', 'signups')}</div>

<h2>By sign-up week, same {d['window_days']}-day window for everyone</h2>
<p class="note">Returns counted only up to {d['window_days']} days after the end of the sign-up week (14 to 20 days after signing up), so every row had the same time.
Only weeks up to {fmt_date(win_last_end)} have a complete window. Pooled: {pw['1']['pct']}% at 1+, {pw['2']['pct']}% at 2+, {pw['3']['pct']}% at 3+ of {d['window_signups']} sign-ups.</p>
<div class="scroll">{cohort_table(d['cohorts'], 'window', 'window_signups')}</div>
<p class="note">Weekly sign-ups range from 6 to 36, so a week-to-week difference of a couple of people is noise. No week stands out.</p>

<h2>Why the old numbers looked wrong</h2>
<p class="note">Left: what GA4 shows if you count users per event over the last 28 days (the view that confused us). Right: the cohort count above.
At least {d['naive_last_28d'].get('user_return_1d', 0) - pt['1']['k']} of the {d['naive_last_28d'].get('user_return_1d', 0)} people firing <code>user_return_1d</code> in the last 28 days
are not among the recent sign-ups as GA4 sees them: they signed up earlier, or are a recent sign-up returning on another device (issue 2). The higher milestones are almost all such people.</p>
<div class="scroll">{naive_table(d['naive_last_28d'], pt)}</div>

<h2>Data issues to raise with Samar</h2>
<ol>
<li><b>GA4 keeps event data for only two months on this property.</b> Admin → Data settings → Data retention is set to "2 months", so user-level
analysis (funnels, cohorts, explorations) cannot see anything before Sep 11, 2026. That is why this report starts there. Switching it to 14 months
takes one click and is free, but only protects data from now on. I did not change it.</li>
<li><b>Milestone events go missing for some accounts.</b> 13 accounts fired <code>user_return_2d</code> after signing up, but only 9 of them fired
<code>user_return_1d</code> first; requiring the milestones in order would give {ps['2']['pct']}% at 2+ and {ps['4']['k']} at 4+ instead of {pt['2']['pct']}% and {pt['4']['k']}.
The likeliest cause is a return on another device or browser, which GA4 treats as a different person, or a blocked tracker. Ask Samar whether the GA4
<code>user_id</code> is set on every event once someone is logged in (only ~1,500 GA4 users carry one); that would let GA4 join devices. Until then, every
number here is a <b>floor</b>: returns made only on a second device are invisible.</li>
<li><b>Sign-up tracking has changed several times.</b> In August <code>account_created</code> fired about 1.8 times per user (the duplicates Samar retired on Oct 8);
from Aug 31 to Oct 4 only 7 to 22 people a week fired it while 65 to 115 entered onboarding; since Oct 5 it is about 1 per user and 18 to 36 a week.
Worth checking against the app's own database: were sign-ups really that low in September, or was the event broken?</li>
<li><b>Developer traffic lands in the production property.</b> <code>localhost</code> (49 users firing account_created since July) and Vercel preview deploys report to it.
This report filters to app.thoughtsaver.com; a GA4 data filter or a separate dev property would keep it clean everywhere.</li>
<li><b>The full history may already exist in BigQuery.</b> The property has had a BigQuery export since Sep 2022 (Google Cloud project 200310840257). Export tables are
not subject to the two-month limit, and they hold per-user rows, so the same analysis could go back to July (when the return events started).
I don't have access to that project; if Samar or Spencer can grant read access, this becomes a much bigger sample.</li>
</ol>
<details><summary>Sign-up tracking by week (issue 3)</summary><div class="scroll">{weekly_table(d['weekly_events'], d['end'])}</div></details>

<h2>How this was measured</h2>
<p class="note">A <b>sign-up cohort</b> = people whose first visit fell in that Monday-to-Sunday week and who fired <code>account_created</code> on app.thoughtsaver.com
(97% sign up on the day of their first visit). A person counts for "N return days" if they fired <code>user_return_Nd</code> at any point after
<code>account_created</code>, the definition in Samar's spreadsheet (separate days, not necessarily in a row). Built with GA4 closed funnels, which follow each
person, so returns from people who signed up earlier cannot leak in. Independent check: one pooled query per N over all weeks gave exactly the same totals as
the per-week queries ({'all matched' if cc_ok else 'MISMATCH, see datapoints.json'}). Confidence intervals: Wilson 95%.
Code: <code>reports/thoughtsaver_retention_cohorts_2026-11-11_src/</code>; tests: <code>tests/test_thoughtsaver_retention_cohorts.py</code>.</p>
</main>"""
    OUT.write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                   f'<title>Thought Saver retention</title><style>{css}</style></head><body>{body}</body></html>')
    print("wrote", OUT, "deep milestones with people:", deep)


if __name__ == "__main__":
    main()
