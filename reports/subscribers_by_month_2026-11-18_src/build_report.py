"""Render reports/subscribers_by_month_2026-11-18.html from datapoints.json (+ cross_check_results.json).

    .venv/bin/python reports/subscribers_by_month_2026-11-18_src/build_report.py [--no-open]

Numbers come from datapoints.json only; the wording that explains them is in NOTES below.
"""
import html
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from md_report import timestamp  # noqa: E402

OUT = HERE.parent / "subscribers_by_month_2026-11-18.html"
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Chart series: (label, analysis buckets folded into it, light colour, dark colour). Order = stack order
# from the baseline up; colours are slots 1-3 of the dataviz reference palette (validated in both modes).
SERIES = [
    ("Tools", lambda m: m["kept_tools"], "#2a78d6", "#3987e5"),
    ("Sign-up forms, podcast, recommendations",
     lambda m: sum(m["buckets"][b] for b in ("forms", "podcast", "recommendations")), "#eb6834", "#d95926"),
    ("Bulk uploads (Leaf batches and others)", lambda m: m["buckets"]["leaf"] + m["buckets"]["uploads"], "#1baf7a", "#199e70"),
]


def n(x) -> str:
    return f"{x:,}"


def month_label(month: str, partial_through=None) -> str:
    name = MONTH_NAMES[int(month[5:]) - 1]
    return f"{name} 1-{partial_through}" if partial_through else name


def approx(m: dict, value) -> str:
    """Thousands separator, with a leading "about" sign in the months whose ad sign-ups are estimated."""
    return ("≈" if m["estimated"] else "") + n(value)


def series_values(m: dict) -> list:
    return [fn(m) for _, fn, _, _ in SERIES]


def chart_svg(months: list, partial_through, annotations: dict) -> str:
    """Stacked columns of kept subscribers per month. Value on each cap, no gridlines, no y axis.
    `annotations` maps a month to a short line printed above its cap."""
    W, H, top, bottom = 720, 320, 46, 30
    plot_h = H - top - bottom
    band = W / len(months)
    col_w = 24
    peak = max(m["kept"] for m in months)
    scale = plot_h / peak
    base_y = top + plot_h
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="New subscribers kept per month, stacked by how '
             f'they arrived. The table below has every value." class="chart">']
    for i, m in enumerate(months):
        cx = band * i + band / 2
        x = cx - col_w / 2
        vals = series_values(m)
        y = base_y
        drawn = [(k, v) for k, v in enumerate(vals) if v * scale >= 1]
        for pos, (k, v) in enumerate(drawn):
            h = v * scale
            gap = 2 if pos < len(drawn) - 1 else 0  # 2px surface gap between stacked segments
            seg_h = max(h - gap, 1)
            y_top = y - h + gap
            if pos == len(drawn) - 1:  # data end: 4px rounded cap
                r = min(4, seg_h)
                d = (f"M{x:.1f},{y_top + seg_h:.1f} V{y_top + r:.1f} Q{x:.1f},{y_top:.1f} {x + r:.1f},{y_top:.1f} "
                     f"H{x + col_w - r:.1f} Q{x + col_w:.1f},{y_top:.1f} {x + col_w:.1f},{y_top + r:.1f} "
                     f"V{y_top + seg_h:.1f} Z")
                parts.append(f'<path d="{d}" class="s{k}"/>')
            else:
                parts.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{col_w}" height="{seg_h:.1f}" class="s{k}"/>')
            y -= h
        cap_y = base_y - m["kept"] * scale - 7
        parts.append(f'<text x="{cx:.1f}" y="{cap_y:.1f}" class="cap">{approx(m, m["kept"])}</text>')
        if m["month"] in annotations:
            parts.append(f'<text x="{cx:.1f}" y="{cap_y - 16:.1f}" class="note">{html.escape(annotations[m["month"]])}</text>')
        last = i == len(months) - 1
        parts.append(f'<text x="{cx:.1f}" y="{base_y + 19}" class="tick">'
                     f'{month_label(m["month"], partial_through if last else None)}</text>')
        tip = {"month": month_label(m["month"], partial_through if last else None) + " " + m["month"][:4],
               "kept": approx(m, m["kept"]), "rows": [[SERIES[k][0], n(v)] for k, v in enumerate(vals)]}
        parts.append(f'<rect x="{band * i:.1f}" y="0" width="{band:.1f}" height="{H}" class="hit" tabindex="0" '
                     f"data-tip='{html.escape(json.dumps(tip), quote=True)}'/>")
    parts.append(f'<line x1="0" x2="{W}" y1="{base_y + 0.5}" y2="{base_y + 0.5}" class="axis"/>')
    parts.append("</svg>")
    return "".join(parts)


def table(headers: list, rows: list, total=None, note_cols=()) -> str:
    out = ["<div class='tablewrap'><table><thead><tr>"]
    out += [f"<th{' class=l' if i == 0 else ''}>{h}</th>" for i, h in enumerate(headers)]
    out.append("</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>" + "".join(
            f"<td class='{'l' if i == 0 else ''}{' key' if i in note_cols else ''}'>{c}</td>" for i, c in enumerate(r)) + "</tr>")
    out.append("</tbody>")
    if total:
        out.append("<tfoot><tr>" + "".join(
            f"<td class='{'l' if i == 0 else ''}{' key' if i in note_cols else ''}'>{c}</td>" for i, c in enumerate(total)) + "</tr></tfoot>")
    out.append("</table></div>")
    return "".join(out)


CSS = """
:root{--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--hair:#e1e0d9;--axis:#c3c2b7;
--s0:#2a78d6;--s1:#eb6834;--s2:#1baf7a;--keybg:#eef4fc}
@media (prefers-color-scheme: dark){:root{--surface:#1a1a19;--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
--hair:#2c2c2a;--axis:#383835;--s0:#3987e5;--s1:#d95926;--s2:#199e70;--keybg:#1c2a3d}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:16px;line-height:1.55}
main{max-width:860px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:28px;line-height:1.2;margin:0 0 6px}
.sub{color:var(--ink2);font-size:14px;margin:0 0 28px}
h2{font-size:20px;margin:44px 0 10px}
p,li{color:var(--ink)} li{margin:6px 0}
.answer{font-size:18px;line-height:1.5;margin:0 0 20px}
.tiles{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 28px}
.tile{flex:1 1 180px;background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:14px 16px}
.tile .v{font-size:28px;font-weight:600;line-height:1.15}
.tile .k{font-size:13px;color:var(--ink2);margin-top:4px}
.card{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:18px 18px 10px;position:relative}
.card h3{font-size:15px;margin:0 0 2px}
.card .cap2{font-size:13px;color:var(--ink2);margin:0 0 6px}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--ink2);margin:6px 0 4px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.chart{width:100%;height:auto;display:block;overflow:visible}
.chart .s0{fill:var(--s0)} .chart .s1{fill:var(--s1)} .chart .s2{fill:var(--s2)}
.chart .cap{font-size:12px;fill:var(--ink);text-anchor:middle;font-weight:600}
.chart .tick{font-size:12px;fill:var(--muted);text-anchor:middle}
.chart .note{font-size:11.5px;fill:var(--ink2);text-anchor:middle}
.chart .axis{stroke:var(--axis);stroke-width:1}
.chart .hit{fill:transparent;outline:none;cursor:default}
.chart .hit:hover,.chart .hit:focus{fill:var(--ink);fill-opacity:.05}
#tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--axis);border-radius:8px;
padding:8px 10px;font-size:13px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;min-width:190px;z-index:2}
#tip .t{color:var(--ink2);margin-bottom:4px}
#tip .r{display:flex;justify-content:space-between;gap:14px}
#tip .r b{font-weight:600} #tip .r span{color:var(--ink2)}
#tip .r span i{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
.tablewrap{overflow-x:auto;margin:10px 0 6px}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--hair);white-space:nowrap}
th{font-weight:600;color:var(--ink2);font-size:12.5px;white-space:normal;vertical-align:bottom;line-height:1.3}
.l{text-align:left} td.key{background:var(--keybg);font-weight:600}
tfoot td{font-weight:600;border-top:1px solid var(--axis);border-bottom:none}
.small{font-size:13.5px;color:var(--ink2)}
.callout{background:var(--surface);border:1px solid var(--hair);border-left:3px solid var(--s1);border-radius:8px;padding:12px 16px;margin:14px 0}
.callout b{font-weight:600} .callout p{margin:0} .callout ul{margin:8px 0} .callout ul+p{margin-top:8px}
code{font-size:.92em;background:var(--hair);padding:1px 5px;border-radius:4px}
"""

JS = """
const tip=document.getElementById('tip'),card=tip.parentElement;
function show(el,evt){const d=JSON.parse(el.dataset.tip);tip.textContent='';
const t=document.createElement('div');t.className='t';t.textContent=d.month;tip.appendChild(t);
const add=(label,value,key)=>{const r=document.createElement('div');r.className='r';const s=document.createElement('span');
if(key!==null){const i=document.createElement('i');i.style.background='var(--s'+key+')';s.appendChild(i);}
s.appendChild(document.createTextNode(label));const b=document.createElement('b');b.textContent=value;r.appendChild(s);r.appendChild(b);tip.appendChild(r);};
add('Kept',d.kept,null);d.rows.slice().reverse().forEach((row,idx)=>add(row[0],row[1],d.rows.length-1-idx));
tip.style.display='block';const c=card.getBoundingClientRect(),b=el.getBoundingClientRect();
let x=b.left-c.left+b.width/2+12;if(x+tip.offsetWidth>c.width-8)x=b.left-c.left+b.width/2-tip.offsetWidth-12;
tip.style.left=Math.max(8,x)+'px';tip.style.top=(evt&&evt.clientY?Math.max(8,evt.clientY-c.top-20):60)+'px';}
document.querySelectorAll('.hit').forEach(el=>{el.addEventListener('pointermove',e=>show(el,e));
el.addEventListener('focus',()=>show(el,null));el.addEventListener('pointerleave',()=>tip.style.display='none');
el.addEventListener('blur',()=>tip.style.display='none');});
"""


def build(dp: dict, xc: dict, notes: dict) -> str:
    months = dp["months"]
    partial = dp.get("partial_through_day")
    tot = lambda key: sum(m[key] for m in months)  # noqa: E731
    btot = lambda b: sum(m["buckets"][b] for m in months)  # noqa: E731
    label = lambda i, m: month_label(m["month"], partial if i == len(months) - 1 else None)  # noqa: E731
    dash = lambda v: n(v) if v else "-"  # noqa: E731
    any_est = any(m["estimated"] for m in months)
    total_mark = "≈" if any_est else ""

    main_rows = [[label(i, m), n(m["total"]), dash(m["buckets"]["study"]), approx(m, m["ads_all"]),
                  dash(m["buckets"]["backlog"]), approx(m, m["kept"]), approx(m, m["kept_active"])]
                 for i, m in enumerate(months)]
    main_total = ["2026 so far", n(tot("total")), n(btot("study")), total_mark + n(tot("ads_all")), n(btot("backlog")),
                  total_mark + n(tot("kept")), total_mark + n(tot("kept_active"))]
    main_table = table(
        ["Month", "All new subscribers (beehiiv)", "From the Who Attracts You study", "From Ads",
         "December backlog (uploaded Jan 1)", "Kept: neither study nor ads", "Of those, still subscribed today"],
        main_rows, main_total, note_cols=(5,))

    ads_rows = [[label(i, m), dash(m["buckets"]["ads"]), dash(m["buckets"]["partner_ads"]),
                 ("≈" + n(m["ads_untagged_est"])) if m["ads_untagged_est"] else "-", approx(m, m["ads_all"])]
                for i, m in enumerate(months)]
    ads_total = ["2026 so far", n(btot("ads")), n(btot("partner_ads")), "≈" + n(tot("ads_untagged_est")),
                 total_mark + n(tot("ads_all"))]
    ads_table = table(["Month", "Tagged cpc on the record", "Partner ad campaigns (MLA)",
                       "Estimated, before tags existed", "All ads"], ads_rows, ads_total, note_cols=(4,))

    route_keys = ["forms", "podcast", "recommendations", "leaf", "uploads"]
    route_rows = [[label(i, m), approx(m, m["kept_tools"])] + [dash(m["buckets"][k]) for k in route_keys]
                  + [approx(m, m["kept"])] for i, m in enumerate(months)]
    route_total = (["2026 so far", total_mark + n(tot("kept_tools"))] + [n(btot(k)) for k in route_keys]
                   + [total_mark + n(tot("kept"))])
    route_table = table(["Month", "Tools"] + [dp["labels"][k] for k in route_keys] + ["Kept"], route_rows,
                        route_total, note_cols=(len(route_keys) + 2,))

    by_month = {m["month"]: m for m in months}
    moves = dp["list_movement"]
    signed = lambda v: ("+" if v > 0 else "") + n(v)  # noqa: E731
    list_rows = [[label(i, by_month[m["month"]]), n(m["active_at_start"]), n(m["subscribed"]), n(m["unsubscribed"]),
                  f"{m['unsubscribe_rate']:.1%}", signed(m["net"]),
                  "-" if m["removed_without_unsubscribe"] is None else n(m["removed_without_unsubscribe"]),
                  n(by_month[m["month"]]["invalid"])] for i, m in enumerate(moves)]
    list_total = ["2026 so far", "", n(sum(m["subscribed"] for m in moves)), n(sum(m["unsubscribed"] for m in moves)), "",
                  signed(sum(m["net"] for m in moves)), n(sum(m["removed_without_unsubscribe"] or 0 for m in moves)),
                  n(tot("invalid"))]
    list_table = table(
        ["Month", "List size at the start", "New subscribers (all sources)", "Unsubscribed", "Unsubscribed, share of the list",
         "Net change", "Removed without an unsubscribe", "Sign-ups marked invalid"],
        list_rows, list_total, note_cols=(3,))
    list_end = (f"<p class='small'>List size at the start of {MONTH_NAMES[int(moves[-1]['month'][5:]) - 1]} "
                f"{partial + 1 if partial else 1}: {n(moves[-1]['active_at_end'])} active subscribers.</p>")

    nets = dp["net_without_imports"]
    net_rows = [[label(i, by_month[m["month"]]), n(m["subscribed"]), dash(m["manual_imports"]), n(m["new_without_imports"]),
                 n(m["unsubscribed"]), signed(m["net"])] for i, m in enumerate(nets)]
    net_total = ["2026 so far"] + [n(sum(m[k] for m in nets)) for k in
                                   ("subscribed", "manual_imports", "new_without_imports", "unsubscribed")] + [
        signed(sum(m["net"] for m in nets))]
    net_table = table(["Month", "New subscribers (beehiiv)", "Manual imports taken out", "New subscribers without imports",
                       "Unsubscribed", "Net change"], net_rows, net_total, note_cols=(5,))

    flows = dp["steady_flow"]
    flow_rows = [[label(i, by_month[f["month"]]), approx(by_month[f["month"]], f["organic"]),
                  approx(by_month[f["month"]], f["ads"]), dash(f["leaf"] + f["launch"]), n(f["unsubscribed"]),
                  signed(f["net_without_ads"]), signed(f["net_with_ads"])] for i, f in enumerate(flows)]
    flow_table = table(["Month", "Organic sign-ups", "Ad sign-ups", "One-offs left out (Leaf, launch)", "Unsubscribed",
                        "Net without ads", "Net with ads"], flow_rows, None, note_cols=(6,))

    legend = "".join(f"<span><i style='background:var(--s{k})'></i>{html.escape(s[0])}</span>"
                     for k, s in enumerate(SERIES))
    tiles = "".join(f"<div class='tile'><div class='v'>{v}</div><div class='k'>{k}</div></div>" for v, k in notes["tiles"])
    sections = "".join(f"<h2>{h}</h2>{body}" for h, body in notes["sections"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{notes['title']}</title>
<style>{CSS}</style></head><body><main>
<h1>{notes['title']}</h1>
<p class="sub">{notes['subtitle']} · generated {timestamp()}</p>
<p class="answer">{notes['answer']}</p>
<div class="tiles">{tiles}</div>
<div class="card"><h3>{notes['chart_title']}</h3><p class="cap2">{notes['chart_caption']}</p>
<div class="legend">{legend}</div>{chart_svg(months, partial, notes['annotations'])}<div id="tip"></div></div>
<h2>Month by month</h2>{main_table}<p class="small">{notes['table_note']}</p>
{notes['callouts']}
<h2>Unsubscribes and deletions per month (whole list)</h2>{list_table}{list_end}<p class="small">{notes['list_note']}</p>
{notes['deletions']}
<h2>Everyday flow: organic and ad sign-ups against unsubscribes</h2>{flow_table}<p class="small">{notes['flow_note']}</p>
<h2>Net change from sign-ups and unsubscribes only (whole list)</h2>{net_table}<p class="small">{notes['net_note']}</p>
<h2>Where the kept subscribers came from</h2>{route_table}<p class="small">{notes['route_note']}</p>
<h2>What was counted as Ads</h2>{ads_table}<p class="small">{notes['ads_note']}</p>
{sections}
</main><script>{JS}</script></body></html>"""


def main():
    dp = json.loads((HERE / "datapoints.json").read_text())
    xc_path = HERE / "cross_check_results.json"
    xc = json.loads(xc_path.read_text()) if xc_path.exists() else {}
    from report_notes import notes  # the wording, kept apart from the rendering
    OUT.write_text(build(dp, xc, notes(dp, xc)))
    print(f"wrote {OUT}")
    if "--no-open" not in sys.argv:
        subprocess.run(["open", "-a", "Google Chrome", str(OUT)], check=False)


if __name__ == "__main__":
    main()
