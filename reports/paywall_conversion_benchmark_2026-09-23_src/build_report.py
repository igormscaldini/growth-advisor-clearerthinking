"""Render the paywalled-post conversion benchmark report from datapoints.json + summary.html."""
import json, math, html, sys, os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "datapoints.json")))
SUMMARY = open(os.path.join(HERE, "summary.html")).read() if os.path.exists(os.path.join(HERE, "summary.html")) else "<p><em>Summary pending.</em></p>"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "paywall_benchmark_report.html")

FAMILIES = [
    ("post_hit_to_paid",  "Readers who hit the paywall who then pay",            "The metric you asked for: paying conversions divided by readers stopped by the wall."),
    ("post_hit_to_click", "Readers who hit the paywall who start the checkout",  "Clicked the subscribe button after being stopped. An upper bound on the metric above."),
    ("post_view_to_paid", "Paid conversions per view of a paywalled post",       "Denominator is every view of the post, not only readers who reached the wall."),
    ("visitor_to_paid",   "Paid conversions per visitor or reader (all traffic)","Site- or list-wide funnel rates: every visitor, not only those who hit a wall."),
    ("list_level",        "Paid subscribers as a share of the free list",        "The ratio Substack and beehiiv publish. A stock, not a per-post rate."),
    ("side_effect",       "What paywalling does to readership and sign-ups",     "Effects of adding or tightening a wall, from quasi-experiments and field tests."),
]
GRADE_TEXT = {
    "A": "A: peer-reviewed study, or a platform-wide first-party dataset with a stated sample",
    "B": "B: platform or vendor claim, or multi-publisher study, without a disclosed method",
    "C": "C: crowd-sourced self-reports or a literature statement",
    "D": "D: single creator or publisher anecdote",
}
BLUE = "#1d4ed8"; INK = "#1f2937"; INK2 = "#4b5563"; MUTED = "#9ca3af"; RULE = "#e5e7eb"

def esc(s): return html.escape(str(s)) if s is not None else ""

def fmt_pct(v):
    if v is None: return ""
    if v >= 10: return f"{v:.0f}%"
    if v >= 1: return f"{v:.1f}%"
    return f"{v:.2f}%"

# ---------- chart ----------
def chart():
    rows = []
    for fam, title, _ in FAMILIES:
        pts = [d for d in DATA if d["family"] == fam and d.get("value") is not None]
        if not pts: continue
        pts.sort(key=lambda d: d["value"])
        rows.append(("header", title, None))
        for d in pts: rows.append(("point", d["label"], d))
    if not rows: return ""
    W, LEFT, RIGHT, ROW, TOP, BOTTOM = 960, 372, 74, 26, 34, 40
    H = TOP + BOTTOM + ROW * len(rows) + 8 * sum(1 for r in rows if r[0] == "header")
    xmin, xmax = math.log10(0.005), math.log10(40)
    def X(v): return LEFT + (math.log10(v) - xmin) / (xmax - xmin) * (W - LEFT - RIGHT)
    def short(d):
        t = d.get("chart_value") or d["value_text"]
        for sep in (";", " ("):
            if sep in t: t = t.split(sep)[0]
        return t if len(t) <= 34 else t[:32] + "…"
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Conversion benchmarks on a log scale" style="font-family:inherit">']
    ticks = [0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30]
    y_axis = H - BOTTOM + 6
    s.append(f'<line x1="{LEFT}" x2="{W-RIGHT}" y1="{y_axis}" y2="{y_axis}" stroke="{RULE}" stroke-width="1"/>')
    for t in ticks:
        s.append(f'<text x="{X(t):.1f}" y="{y_axis+18}" text-anchor="middle" font-size="12" fill="{MUTED}">{fmt_pct(t)}</text>')
        s.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{y_axis}" y2="{y_axis+4}" stroke="{RULE}"/>')
    s.append(f'<text x="{W-RIGHT}" y="{TOP-14}" text-anchor="end" font-size="12" fill="{MUTED}">conversion rate, log scale</text>')
    y = TOP
    for kind, label, d in rows:
        if kind == "header":
            y += 8
            s.append(f'<text x="0" y="{y+16}" font-size="13" font-weight="600" fill="{INK}">{esc(label)}</text>')
            y += ROW
            continue
        cy = y + ROW / 2
        lab = label if len(label) <= 56 else label[:54] + "…"
        s.append(f'<text x="{LEFT-14}" y="{cy+4}" text-anchor="end" font-size="12.5" fill="{INK2}">{esc(lab)}</text>')
        lo, hi = d.get("value_low"), d.get("value_high")
        anchor_x = X(d["value"]); left_x = X(d["value"])
        if lo is not None and hi is not None:
            s.append(f'<line x1="{X(lo):.1f}" x2="{X(hi):.1f}" y1="{cy}" y2="{cy}" stroke="{BLUE}" stroke-width="2" stroke-opacity="0.35" stroke-linecap="round"/>')
            anchor_x = X(hi); left_x = X(lo)
        tip = f'{label}: {d["value_text"]} ({d["source_title"]})'
        s.append(f'<circle cx="{X(d["value"]):.1f}" cy="{cy}" r="5.5" fill="{BLUE}" stroke="#fff" stroke-width="2"><title>{esc(tip)}</title></circle>')
        txt = short(d); est = len(txt) * 6.4
        if anchor_x + 11 + est <= W - RIGHT - 4:
            s.append(f'<text x="{anchor_x+11:.1f}" y="{cy+4}" font-size="12" fill="{INK2}">{esc(txt)}</text>')
        else:
            s.append(f'<text x="{left_x-11:.1f}" y="{cy+4}" text-anchor="end" font-size="12" fill="{INK2}">{esc(txt)}</text>')
        s.append(f'<text x="{W-RIGHT+12}" y="{cy+4}" font-size="11" fill="{MUTED}">{esc(d["grade"])}</text>')
        y += ROW
    s.append("</svg>")
    return "\n".join(s)

# ---------- tables ----------
def table(fam):
    pts = [d for d in DATA if d["family"] == fam]
    if not pts: return ""
    pts.sort(key=lambda d: (d.get("value") is None, d.get("value") if d.get("value") is not None else 0))
    r = ['<table><thead><tr><th style="width:24%">Source and population</th><th style="width:14%">Value</th><th>Definition and caveats</th><th style="width:7%">Grade</th></tr></thead><tbody>']
    for d in pts:
        comp = ' <span class="tag">computed from reported counts</span>' if d.get("computed") else ""
        r.append("<tr>"
                 f'<td><a href="{esc(d["source_url"])}">{esc(d["label"])}</a><div class="small">{esc(d["population"])}<br>{esc(d["platform"])}, {esc(d["year"])}</div></td>'
                 f'<td class="val">{esc(d["value_text"])}{comp}</td>'
                 f'<td>{esc(d["definition"])}<div class="small">{esc(d.get("notes",""))}</div>'
                 f'<details><summary>Quote from source</summary><blockquote>{esc(d["quote"])}</blockquote><div class="small"><a href="{esc(d["source_url"])}">{esc(d["source_title"])}</a></div></details></td>'
                 f'<td class="grade" title="{esc(GRADE_TEXT.get(d["grade"], d["grade"]))}">{esc(d["grade"])}</td></tr>')
    r.append("</tbody></table>")
    return "\n".join(r)

def sources():
    seen, items = set(), []
    for d in DATA:
        if d["source_url"] in seen: continue
        seen.add(d["source_url"])
        items.append(f'<li><a href="{esc(d["source_url"])}">{esc(d["source_title"])}</a> <span class="small">({esc(d["platform"])}, {esc(d["year"])}, grade {esc(d["grade"])})</span></li>')
    return "<ol>" + "\n".join(items) + "</ol>"

stamp = datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")
sections = []
for fam, title, sub in FAMILIES:
    t = table(fam)
    if t: sections.append(f'<section><h2>{esc(title)}</h2><p class="sub">{esc(sub)}</p>{t}</section>')

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paywalled-post conversion benchmark</title>
<style>
:root{{--ink:{INK};--ink2:{INK2};--muted:{MUTED};--rule:{RULE};--blue:{BLUE};--bg:#ffffff}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:40px 24px 80px}}
h1{{font-size:30px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}}
h2{{font-size:20px;margin:44px 0 4px}}
.stamp{{color:var(--muted);font-size:14px;margin:0 0 28px}}
.sub{{color:var(--ink2);margin:0 0 14px;font-size:14.5px}}
p{{margin:0 0 14px}}
.summary{{border-left:3px solid var(--blue);padding:4px 0 4px 18px;margin:8px 0 28px}}
.summary h3{{font-size:16px;margin:14px 0 4px}}
.summary ul{{margin:0 0 10px 18px;padding:0}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0 6px}}
th{{text-align:left;font-weight:600;color:var(--ink2);border-bottom:1px solid var(--rule);padding:8px 10px 8px 0;vertical-align:bottom}}
td{{border-bottom:1px solid var(--rule);padding:10px 10px 10px 0;vertical-align:top}}
td.val{{font-weight:600;color:var(--ink)}}
td.grade{{text-align:center;color:var(--ink2)}}
.small{{color:var(--ink2);font-size:12.5px;margin-top:4px}}
.tag{{display:inline-block;font-size:11px;font-weight:500;color:var(--ink2);background:#f3f4f6;border-radius:999px;padding:1px 8px;margin-top:4px}}
details{{margin-top:6px}} summary{{cursor:pointer;color:var(--blue);font-size:12.5px}}
blockquote{{margin:6px 0 4px;padding:6px 12px;border-left:2px solid var(--rule);color:var(--ink2);font-size:13px;font-style:italic}}
a{{color:var(--blue);text-decoration:none}} a:hover{{text-decoration:underline}}
figure{{margin:16px 0 8px}} figcaption{{color:var(--ink2);font-size:13px;margin-top:6px}}
ol li{{margin-bottom:6px;font-size:14px}}
.grades li{{font-size:14px}}
@media (max-width:640px){{table{{font-size:13px}} h1{{font-size:24px}}}}
</style></head>
<body><main>
<h1>Paywalled-post conversion benchmark</h1>
<p class="stamp">Generated {stamp}. Desk research; every figure links to the page it was read on.</p>
<div class="summary">{SUMMARY}</div>
<section><h2>All rate benchmarks on one scale</h2>
<p class="sub">Each dot is one published figure. Families are not interchangeable: read the denominators in the tables below before comparing dots across groups.</p>
<figure>{chart()}<figcaption>Log scale. A bar behind a dot marks a published range; the dot sits at the range's midpoint on the log scale. Grades: A peer-reviewed or platform-wide dataset, B undocumented platform or vendor claim, C crowd-sourced self-reports, D single-creator anecdote.</figcaption></figure>
</section>
{''.join(sections)}
<section><h2>How to read the evidence grades</h2>
<ul class="grades">{''.join(f'<li>{esc(v)}</li>' for v in GRADE_TEXT.values())}</ul>
</section>
<section><h2>Sources</h2>{sources()}</section>
</main></body></html>"""
open(OUT, "w").write(page)
print("wrote", OUT, len(page), "bytes;", len(DATA), "datapoints")
