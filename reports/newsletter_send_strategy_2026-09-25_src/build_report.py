"""Build reports/newsletter_send_strategy_2026-09-25.html from datapoints.json (run analysis.py first)."""
from __future__ import annotations

import html
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "newsletter_send_strategy_2026-09-25.html"
D = json.load(open(HERE / "datapoints.json"))
BLUE, ORANGE, AQUA = "var(--s1)", "var(--s2)", "var(--s3)"
TXT, TXT2, RULE = "var(--t1)", "var(--t2)", "var(--rule)"
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
esc = html.escape


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def per_k(x):
    return f"{x * 1000:.1f}"


def fmt_int(n):
    return f"{int(n):,}"


# ----------------------------------------------------------------------------- svg helpers
def svg_open(w, h):
    return f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;font-family:inherit" role="img">'


def text(x, y, s, size=12, anchor="start", color=TXT2, weight="normal", dy=0):
    return (f'<text x="{x:.1f}" y="{y + dy:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" '
            f'font-weight="{weight}">{esc(str(s))}</text>')


def dot(x, y, color, r=4.5, title=""):
    t = f"<title>{esc(title)}</title>" if title else ""
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" stroke="var(--bg)" stroke-width="2">{t}</circle>'


def legend(x, y, items):
    out, cx = [], x
    for color, label in items:
        out.append(f'<circle cx="{cx + 5}" cy="{y - 4}" r="5" fill="{color}"/>')
        out.append(text(cx + 15, y, label, 12, color=TXT))
        cx += 15 + 7 * len(label) + 22
    return "".join(out)


def time_chart(rows, key, title, ymax, yfmt, w=860, h=230):
    """Dots over time coloured by sending domain, thin grey chronological line."""
    l, r, t, b = 52, 16, 34, 34
    rows = sorted(rows, key=lambda p: p["date_utc"])
    dates = [datetime.strptime(p["date_utc"], "%Y-%m-%d %H:%M") for p in rows]
    x0, x1 = dates[0], dates[-1]
    span = (x1 - x0).total_seconds() or 1

    def X(dt):
        return l + (dt - x0).total_seconds() / span * (w - l - r)

    def Y(v):
        return t + (1 - v / ymax) * (h - t - b)
    s = [svg_open(w, h), text(l, 16, title, 13, color=TXT, weight="600")]
    s.append(f'<line x1="{l}" y1="{Y(0):.1f}" x2="{w - r}" y2="{Y(0):.1f}" stroke="{RULE}" stroke-width="1"/>')
    for v in [ymax * k / 4 for k in range(1, 5)]:
        s.append(text(l - 6, Y(v) + 4, yfmt(v), 11, anchor="end"))
    # month ticks
    m = datetime(x0.year, x0.month, 1)
    while m <= x1:
        if m >= x0 and (m.month % 3 == 1):
            s.append(text(X(m), h - 12, m.strftime("%b %Y"), 11, anchor="middle"))
        m = datetime(m.year + (m.month == 12), 1 if m.month == 12 else m.month + 1, 1)
    pts = " ".join(f"{X(d):.1f},{Y(p[key]):.1f}" for d, p in zip(dates, rows))
    s.append(f'<polyline points="{pts}" fill="none" stroke="{RULE}" stroke-width="2" stroke-linejoin="round"/>')
    for d, p in zip(dates, rows):
        c = ORANGE if p["domain"] == "OHI" else BLUE
        s.append(dot(X(d), Y(p[key]), c, title=f"{p['date_et']} | {p['subject_line']} | {yfmt(p[key])} | {p['aud_label']}"))
    s.append(legend(w - 300, 16, [(BLUE, "CT domain (info@)"), (ORANGE, "OHI domain")]))
    s.append("</svg>")
    return "".join(s)


def dumbbell(groups, key, title, xfmt, w=420, xmax=None):
    """One row per campaign: two dots (first send blue, second orange) joined by a rule."""
    l, r, t, rowh = 60, 14, 30, 22
    h = t + rowh * len(groups) + 26
    vals = [g[i][key] for g in groups for i in (0, 1)]
    xmax = xmax or max(vals) * 1.15

    def X(v):
        return l + v / xmax * (w - l - r)
    s = [svg_open(w, h), text(l, 16, title, 13, color=TXT, weight="600")]
    for i, g in enumerate(groups):
        y = t + rowh * i + 12
        a, b = g[0], g[1]
        s.append(text(l - 8, y + 4, datetime.strptime(a['date_utc'], '%Y-%m-%d %H:%M').strftime('%b %d'), 11, anchor='end'))
        s.append(f'<line x1="{X(a[key]):.1f}" y1="{y}" x2="{X(b[key]):.1f}" y2="{y}" stroke="{RULE}" stroke-width="2"/>')
        s.append(dot(X(a[key]), y, BLUE, title=f"{a['aud_label']}: {xfmt(a[key])}"))
        s.append(dot(X(b[key]), y, ORANGE, title=f"{b['aud_label']}: {xfmt(b[key])}"))
        hi = max(a[key], b[key])
        s.append(text(X(hi) + 9, y + 4, xfmt(hi), 11))
    base = t + rowh * len(groups) + 6
    s.append(f'<line x1="{l}" y1="{base}" x2="{w - r}" y2="{base}" stroke="{RULE}" stroke-width="1"/>')
    for k in range(0, 5):
        v = xmax * k / 4
        s.append(text(X(v), base + 14, xfmt(v), 11, anchor="middle"))
    s.append("</svg>")
    return "".join(s)


def bars(labels, values, title, vfmt, w=860, h=220, color=BLUE, highlight=None, note=None):
    l, r, t, b = 40, 16, 34, 40
    n = len(values)
    slot = (w - l - r) / n
    bw = min(24, slot * 0.6)
    vmax = max(values) * 1.15 or 1

    def Y(v):
        return t + (1 - v / vmax) * (h - t - b)
    s = [svg_open(w, h), text(l, 16, title, 13, color=TXT, weight="600")]
    y0 = Y(0)
    s.append(f'<line x1="{l}" y1="{y0:.1f}" x2="{w - r}" y2="{y0:.1f}" stroke="{RULE}" stroke-width="1"/>')
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = l + slot * i + (slot - bw) / 2
        y = Y(v)
        hh = max(y0 - y, 0)
        c = color if (highlight is None or highlight(i)) else "var(--rule)"
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hh:.1f}" rx="4" fill="{c}"><title>{esc(lab)}: {vfmt(v)}</title></rect>')
        s.append(f'<rect x="{x:.1f}" y="{max(y0 - 4, y):.1f}" width="{bw:.1f}" height="{min(4, hh):.1f}" fill="{c}"/>')
        if n <= 12 or v == max(values):
            s.append(text(x + bw / 2, y - 5, vfmt(v), 11, anchor="middle"))
        if n <= 12 or i % 2 == 0:
            s.append(text(x + bw / 2, h - 22, lab, 11, anchor="middle"))
    if note:
        s.append(text(l, h - 6, note, 11))
    s.append("</svg>")
    return "".join(s)


def send_slot_chart(rows, w=860, h=250):
    """Weekday rows x hour-of-day (ET) columns; dot radius scales with number of sends."""
    l, r, t, b = 46, 16, 34, 30
    counts = {}
    for p in rows:
        counts[(p["weekday_et"], p["hour_et"])] = counts.get((p["weekday_et"], p["hour_et"]), 0) + 1
    rowh = (h - t - b) / 7
    colw = (w - l - r) / 24
    s = [svg_open(w, h), text(l, 16, f"When the {len(rows)} large primary sends went out (US Eastern)", 13, color=TXT, weight="600")]
    for i, d in enumerate(WD):
        y = t + rowh * i + rowh / 2
        s.append(text(l - 8, y + 4, d, 11, anchor="end"))
        s.append(f'<line x1="{l}" y1="{y:.1f}" x2="{w - r}" y2="{y:.1f}" stroke="{RULE}" stroke-width="1"/>')
    for hr in range(0, 24, 3):
        s.append(text(l + colw * hr + colw / 2, h - 8, f"{hr:02d}", 11, anchor="middle"))
    mx = max(counts.values())
    for (d, hr), n in counts.items():
        x = l + colw * hr + colw / 2
        y = t + rowh * WD.index(d) + rowh / 2
        rad = 4 + 10 * math.sqrt(n / mx)
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{BLUE}" fill-opacity="0.85" stroke="var(--bg)" stroke-width="2"><title>{d} {hr:02d}:00 ET: {n} sends</title></circle>')
        if n >= 5:
            s.append(text(x, y + 4, n, 11, anchor="middle", color="#fff"))
    s.append("</svg>")
    return "".join(s)


def effects_chart(click, opn, w=860):
    """Log-scale dot plot: per feature, click ratio (blue) and open ratio (orange) vs 1.0."""
    names = {"question": "Contains a question mark", "question_word": "Starts How / Why / What / Can...",
             "personal": "Says you / your", "number": "Contains a number", "bracket_tag": "Has a [tag]",
             "parenthetical": "Has a (parenthetical)", "tool": "Mentions a tool", "evidence": "Data / science / study / experts",
             "psych_topic": "Personality or psychology topic", "negative": "Warning framing (stop, myths...)",
             "short": "Short (7 words or fewer)", "rewritten": "Subject differs from title"}
    rows = [(names[c["feature"]], c, o) for c, o in zip(click, opn) if c["feature"] in names and c["n_with"] >= 2 and c["n_without"] >= 2]
    l, r, t, rowh = 320, 60, 34, 24
    h = t + rowh * len(rows) + 30
    lo, hi = math.log2(0.4), math.log2(3.5)

    def X(v):
        return l + (math.log2(max(v, 0.4)) - lo) / (hi - lo) * (w - l - r)
    s = [svg_open(w, h), text(8, 16, "Subject-line features: ratio of the click index and open index, with vs without the feature", 13, color=TXT, weight="600")]
    s.append(f'<line x1="{X(1):.1f}" y1="{t}" x2="{X(1):.1f}" y2="{t + rowh * len(rows)}" stroke="{TXT2}" stroke-width="1"/>')
    for i, (name, c, o) in enumerate(rows):
        y = t + rowh * i + 12
        s.append(text(l - 10, y + 4, f"{name}  (n={c['n_with']} vs {c['n_without']})", 12, anchor="end", color=TXT))
        s.append(f'<line x1="{X(min(c["ratio"], o["ratio"])):.1f}" y1="{y}" x2="{X(max(c["ratio"], o["ratio"])):.1f}" y2="{y}" stroke="{RULE}" stroke-width="2"/>')
        s.append(dot(X(c["ratio"]), y, BLUE, title=f"clicks x{c['ratio']:.2f}, p={c['p']:.2f}"))
        s.append(dot(X(o["ratio"]), y, ORANGE, title=f"opens x{o['ratio']:.2f}, p={o['p']:.2f}"))
        s.append(text(X(max(c["ratio"], o["ratio"])) + 9, y + 4, f"x{c['ratio']:.2f} / x{o['ratio']:.2f}" + (" *" if c["p"] < 0.05 or o["p"] < 0.05 else ""), 11))
    base = t + rowh * len(rows) + 6
    for v in [0.5, 0.7, 1, 1.5, 2, 3]:
        s.append(text(X(v), base + 14, f"x{v}", 11, anchor="middle"))
    s.append(legend(w - 210, 16, [(BLUE, "clicks"), (ORANGE, "opens")]))
    s.append("</svg>")
    return "".join(s)


# ----------------------------------------------------------------------------- tables
def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def subjects_table(rows, key):
    return table(["Subject line", "Sent (ET)", "Audience", "Type", "Open", "Click", "Click index", "Open index"],
                 [[esc(p["subject_line"]), p["date_et"], p["aud_label"], p["subtype"].replace("_", " "), pct(p["open_rate"]),
                   pct(p["click_rate"], 2), f"{p['click_index']:.2f}", f"{p['open_index']:.2f}"] for p in rows])


# ----------------------------------------------------------------------------- content
core = D["core"]
big = [p for p in core if p["recipients"] >= 100_000]
engaged_series = [p for p in big if p["aud_class"] in ("engaged", "all_minus_nonopeners")]
pairs = [g for g in D["pairs"] if len(g) == 2 and g[0]["aud_class"] == "engaged" and g[1]["aud_class"] == "rest"]
sep10 = next(g for g in D["pairs"] if "attracts" in g[0]["title"].lower())
domain_pair = next(g for g in D["pairs"] if "meditation" in g[0]["title"].lower())
isp = D["isp"]
isp_trend = json.load(open(HERE / "data" / "isp_trend.json")) if (HERE / "data" / "isp_trend.json").exists() else []
tm = D["timing"]
eff_c = {e["feature"]: e for e in D["subject_effects"]["click"]}
eff_o = {e["feature"]: e for e in D["subject_effects"]["open"]}
country = D["country"]
cats = D["category_counts"]


def pair_totals(pairs):
    e_clicks = sum(g[0]["verified_clicks"] for g in pairs)
    r_clicks = sum(g[1]["verified_clicks"] for g in pairs)
    e_del = sum(g[0]["delivered"] for g in pairs)
    r_del = sum(g[1]["delivered"] for g in pairs)
    e_uns = sum(g[0]["unsub_rate"] * g[0]["delivered"] for g in pairs)
    r_uns = sum(g[1]["unsub_rate"] * g[1]["delivered"] for g in pairs)
    e_spam = sum(g[0]["spam_rate"] * g[0]["delivered"] for g in pairs)
    r_spam = sum(g[1]["spam_rate"] * g[1]["delivered"] for g in pairs)
    return dict(e_clicks=e_clicks, r_clicks=r_clicks, e_del=e_del, r_del=r_del, e_uns=e_uns, r_uns=r_uns, e_spam=e_spam, r_spam=r_spam)


pt = pair_totals(pairs)
pairs_apr = [g for g in pairs if g[0]['date_utc'] < '2026-05-05']
pairs_may = [g for g in pairs if g[0]['date_utc'] >= '2026-05-05']
pa, pm = pair_totals(pairs_apr), pair_totals(pairs_may)
rel = lambda t: (t['r_clicks'] / t['r_del']) / (t['e_clicks'] / t['e_del'])
uns_ratio = (pt['r_uns'] / pt['r_del']) / (pt['e_uns'] / pt['e_del'])
spam_ratio = (pt['r_spam'] / pt['r_del']) / (pt['e_spam'] / pt['e_del'])
thu_evening = [p for p in big if p["weekday_et"] == "Thu" and 18 <= p["hour_et"] <= 21]
n_first24 = sum(tm["median_shares"][1:6])
tail = tm["tail_hours_et"]
tail_tot = sum(tail)
work_share = sum(tail[8:18]) / tail_tot
top5 = country["top"][:5]
na = sum(n for c, n in country["top"] if c in ("United States", "Canada")) / country["total_sessions"]
eu = sum(n for c, n in country["top"] if c in ("United Kingdom", "Germany", "Netherlands", "France", "Spain", "Ireland", "Poland", "Italy")) / country["total_sessions"]
apac = sum(n for c, n in country["top"] if c in ("Australia", "Singapore", "India", "New Zealand")) / country["total_sessions"]

by_month = {}
for p in engaged_series:
    by_month.setdefault(p["date_utc"][:7], []).append(p)
era_rows = [[m, v[0]["domain"], len(v), pct(statistics.mean(x["open_rate"] for x in v)), pct(statistics.mean(x["click_rate"] for x in v), 2),
             per_k(statistics.mean(x["unsub_rate"] for x in v))] for m, v in sorted(by_month.items())]

gm_o, gm_c = isp["ohi_domain"]["isps"]["gmail.com"], isp["ct_domain"]["isps"]["gmail.com"]
isp_rows = []
for name in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]:
    a, b = isp["ohi_domain"]["isps"][name], isp["ct_domain"]["isps"][name]
    isp_rows.append([name, fmt_int(a["delivered"]), pct(a["opens"] / a["delivered"]), fmt_int(a["clicks"]), fmt_int(b["delivered"]), pct(b["opens"] / b["delivered"]), fmt_int(b["clicks"])])

top_click = sorted(big, key=lambda p: -p["click_index"])[:10]
bot_click = sorted(big, key=lambda p: p["click_index"])[:10]
top_open = sorted(big, key=lambda p: -p["open_index"])[:8]
ab_tested = [p for p in core if p.get("split_tested")]

odd_slots = [p for p in big if not (p["weekday_et"] == "Thu" and 17 <= p["hour_et"] <= 22)]


RECS = [
    (9, "Treat the sending domain as the asset it is",
     "Stop sending the newsletter to the whole list and to people who have not opened anything in months. Keep the engaged segment as the only routine audience, review the Gmail open rate on every send (beehiiv's ISP breakdown), and use a separate subdomain for one-off blasts (partner promos, re-launches, study recruitment) so they cannot damage the newsletter's reputation.",
     "The Aug 13 split test is causal evidence: identical content, audience and hour, and Gmail opened 31% of the OHI-domain copy vs 5% of the CT-domain copy (2.3x the clicks). Open rates on the CT domain slid from 45% to 21% over the months it was used for whole-list and never-opener sends.",
     "The OHI domain now carries everything and its Gmail opens have eased from 34% to 26% since July; a subdomain split contains future damage but does not repair a reputation that has already slipped."),
    (8, "Send in engagement tiers, not to 'everyone'",
     "Main send to the engaged segment on Thursday evening. Readers with zero opens in 90 days move to a monthly 'best of' email only, and are sunset after 6 months without an open. A resend goes only to non-openers of the first send, three or more days later, with a new subject line (the Sep 14 resend to non-openers added about 22% more clicks at a very low unsubscribe rate, which is the pattern to keep).",
     f"In the April pairs the whole-list remainder clicked at {rel(pa)*100:.0f}% of the engaged rate per email, with {uns_ratio:.1f}x the unsubscribes and {spam_ratio:.1f}x the spam reports per email across all eight pairs, and the never-openers inside it are what Gmail counts against the domain. On Sep 10 the top 29% of the engaged segment (50%+ openers) produced 58% of all clicks at 2.25% click rate vs 0.66% for the rest.",
     "Fewer recipients per send means fewer absolute clicks in the short run (the remainder still added roughly 500 clicks per campaign in April)."),
    (7, "Run a real send-time test; the history cannot answer it",
     "For six consecutive newsletters, split the engaged segment into two random static halves. Half A keeps Thursday 7pm ET; half B gets the same email Friday 8am ET (or Thursday 7am ET). Compare verified clicks per delivered email across the six pairs, then switch the whole send if B wins by 10%+.",
     f"{len(thu_evening)} of the {len(big)} large sends went out Thursday 6-9pm ET; the other slots are single sends confounded by audience and content. With ~1,000 clicks per send, six paired sends detect a 10% difference. Only 11% of a campaign's clicks happen in the first hour and 43% in the first 24 hours, so the send hour is worth testing but is unlikely to be a large lever.",
     "Two versions of every send for six weeks is real overhead, and beehiiv's A/B feature cannot do it (it tests subject lines, not send time), so the split is manual."),
    (7, "Lead with the tool or the concrete offer",
     "Tool launches earned 1.5x the clicks of neighbouring articles even though they opened 30% less. For article weeks, put a related tool link above the fold and name the payoff in the subject: '82 self-help techniques', '100 self-help books', 'a personality disorder most people have never heard of' all sit at the top of the click index; abstract framings ('what's scaring people about AI', 'four overlooked ideas', 'career advice experts wish you knew') sit at the bottom.",
     "The top 10 sends by click index are 7 tool or offer subjects and 3 concrete-payoff articles; the bottom 10 are all abstract article subjects.",
     "Every launch email dilutes the next one: the Sep 14 resend of the attraction tool to non-openers opened at 5%, and a list that gets a launch every week stops treating launches as news."),
    (6, "A/B test every subject line and keep a log",
     "Turn on beehiiv's A/B test (20% sample, 60 minutes) on every newsletter. The API stores no results, so record the variants and the winner in a sheet after each send. Test 'How / Why / What' openers against concrete-payoff statements first: question-word subjects opened 13% more but clicked 18% less in this data (p about 0.07, suggestive only).",
     "Only 6 sends have ever been split tested; the beehiiv UI holds those results and they are not visible here. No subject-line feature reached significance on 52 sends, so structured testing is the only way to learn.",
     "beehiiv picks winners on opens, which Apple Mail Privacy inflates; a subject that wins opens can lose clicks, as the question-word pattern hints."),
    (5, "Fix the UTM hygiene on follow-up links",
     "Links to a newsletter article pasted into later emails carry the original campaign's utm_campaign, so GA4 attributes clicks from OHI and later sends back to the newsletter. Paste clean URLs and let beehiiv tag them.",
     "The 'day 7+' bucket holds 15% of clicks and the tail spikes at 10pm ET on Tuesdays, which is the OHI send hour, not a reading habit.",
     "Cosmetic for revenue; it only matters for measurement."),
]

# ----------------------------------------------------------------------------- html
CSS = """
:root{--bg:#fcfcfb;--t1:#0b0b0b;--t2:#52514e;--rule:#e6e4df;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--card:#f4f3f0;color-scheme:light}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a19;--t1:#fff;--t2:#c3c2b7;--rule:#383835;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--card:#232322;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#1a1a19;--t1:#fff;--t2:#c3c2b7;--rule:#383835;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--card:#232322;color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--t1);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:900px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;margin:0 0 4px;line-height:1.2}h2{font-size:20px;margin:40px 0 10px;padding-top:12px;border-top:1px solid var(--rule)}h3{font-size:16px;margin:22px 0 6px}
.sub{color:var(--t2);margin:0 0 20px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:18px 0}
.kpi{background:var(--card);border-radius:10px;padding:12px 14px}.kpi b{display:block;font-size:24px;line-height:1.1;margin-bottom:4px}.kpi span{color:var(--t2);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0 16px}th{text-align:left;color:var(--t2);font-weight:600;border-bottom:1px solid var(--rule);padding:6px 8px}td{padding:6px 8px;border-bottom:1px solid var(--rule);vertical-align:top}
.wrap{overflow-x:auto}.fig{margin:14px 0 4px}.cap{color:var(--t2);font-size:13px;margin:0 0 14px}
.row{display:flex;gap:16px;flex-wrap:wrap}.row>div{flex:1 1 380px}
.rec{background:var(--card);border-radius:10px;padding:12px 16px;margin:10px 0}.rec h3{margin:0 0 6px}.rec .sc{display:inline-block;min-width:34px;text-align:center;border-radius:8px;background:var(--s1);color:#fff;font-weight:700;padding:2px 6px;margin-right:8px}
.rec p{margin:6px 0}.rec .pro b,.rec .con b{color:var(--t2)}
.note{border-left:3px solid var(--s2);padding:4px 12px;color:var(--t2);margin:12px 0}
details summary{cursor:pointer;color:var(--t2)}
"""

parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>CT newsletter send strategy</title><style>{CSS}</style></head><body><main>"]
parts.append(f"<h1>Clearer Thinking newsletter: what the send data says</h1><p class='sub'>Generated {D['generated_at']} · {len(core)} primary Clearer Thinking newsletter sends (Jun 2025 to Sep 2026) out of {D['n_posts']} confirmed beehiiv posts · One Helpful Idea, event reminders, updates, promos and tests excluded</p>")

parts.append(f"""<div class='kpis'>
<div class='kpi'><b>{pct(gm_o['opens']/gm_o['delivered'],0)} vs {pct(gm_c['opens']/gm_c['delivered'],0)}</b><span>Gmail open rate, same email and audience, OHI domain vs CT domain (Aug 13 split test)</span></div>
<div class='kpi'><b>{rel(pa)*100:.0f}%</b><span>clicks per email from the whole-list remainder relative to the engaged segment (4 April pairs), at {uns_ratio:.1f}x the unsubscribes</span></div>
<div class='kpi'><b>{len(thu_evening)} of {len(big)}</b><span>large sends went out Thursday 6-9pm ET; send time has never been tested</span></div>
<div class='kpi'><b>{pct(n_first24,0)}</b><span>of a campaign's clicks arrive in the first 24 hours (median); {pct(tm['median_shares'][1],0)} in the first hour</span></div>
<div class='kpi'><b>x{eff_c['tool']['ratio']:.1f}</b><span>click index of tool launches vs neighbouring articles (opens x{eff_o['tool']['ratio']:.1f})</span></div>
</div>""")

parts.append(f"""<h2>Headline findings</h2><ul>
<li><b>The sending domain is the biggest lever in the data.</b> On Aug 13 the same email went to two random halves of the engaged segment 36 minutes apart, one from ohi.clearerthinking.net and one from info@clearerthinking.net. Gmail, which is 81% of recipients, opened 31% of the first and 5% of the second, and the OHI copy produced 2.3x the Gmail clicks. The CT domain's open rate had slid from 45% (Dec) to 21% (Jun) over the months it was used for whole-list and never-opener sends; moving the newsletter to the OHI domain in July restored 40%; Gmail opens on that domain have since eased from 34% to 26% while Yahoo held steady, so the same slide may be starting again as the domain now carries every send type.</li>
<li><b>Audience choice matters more than anything about the email.</b> In the four April pairs the whole-list remainder clicked at {rel(pa)*100:.0f}% of the engaged segment's rate per email; across all eight pairs it cost {uns_ratio:.1f}x the unsubscribes and {spam_ratio:.1f}x the spam reports per email, and those sends coincide with the CT domain's reputation slide. Inside the engaged segment the 50%+ openers (29% of it) generated 58% of the clicks on Sep 10.</li>
<li><b>Send time cannot be ranked from history.</b> {len(thu_evening)} of the {len(big)} large primary sends left at Thursday 6-9pm ET; every other slot is a single send with a different audience or content. GA4 shows the newsletter is read over days, not minutes (11% of clicks in the first hour, 43% in 24 hours), and the audience is 54% North America, 17% Europe, 10% Asia-Pacific, so an evening ET send reaches Europe next morning. A six-week paired test is the only way to learn.</li>
<li><b>Subject-line form is a weak signal; the offer is the strong one.</b> No structural feature reached significance on 52 sends. Tool launches clicked 1.5x their neighbours while opening 0.7x; 'How / Why / What' openers opened 13% more and clicked 18% less (suggestive). The top of the click ranking is concrete payoffs, the bottom is abstract framings.</li>
</ul>""")

# ---- audience
parts.append("<h2>1. Audience: who should get the newsletter</h2>")
parts.append("<p>Between April and June 2026 the newsletter was sent twice: first to the engaged segment on Thursday evening, then the next day to everyone else on the list. Those pairs are the cleanest audience evidence available (same email, same week).</p>")
parts.append("<div class='row'>")
parts.append("<div class='fig'>" + dumbbell(pairs, "click_rate", "Verified click rate", lambda v: pct(v, 2)) + "</div>")
parts.append("<div class='fig'>" + dumbbell(pairs, "open_rate", "Open rate", lambda v: pct(v, 0)) + "</div>")
parts.append("</div><div class='row'>")
parts.append("<div class='fig'>" + dumbbell(pairs, "unsub_rate", "Unsubscribes per email", lambda v: per_k(v) + "/1k") + "</div>")
parts.append("<div class='fig'>" + dumbbell(pairs, "spam_rate", "Spam reports per email", lambda v: f"{v*10000:.1f}/10k") + "</div>")
parts.append("</div>")
parts.append(f"<p class='cap'>Blue: engaged segment (Thursday evening). Orange: whole list minus the engaged segment (next day). Rows are the 8 paired campaigns, Apr 9 to May 29, 2026. Totals: engaged {fmt_int(pt['e_del'])} delivered, {fmt_int(pt['e_clicks'])} verified clicks ({pct(pt['e_clicks']/pt['e_del'],2)}), {per_k(pt['e_uns']/pt['e_del'])} unsubs/1k, {pt['e_spam']/pt['e_del']*10000:.2f} spam/10k. Remainder {fmt_int(pt['r_del'])} delivered, {fmt_int(pt['r_clicks'])} clicks ({pct(pt['r_clicks']/pt['r_del'],2)}), {per_k(pt['r_uns']/pt['r_del'])} unsubs/1k, {pt['r_spam']/pt['r_del']*10000:.2f} spam/10k. In the four April pairs, where the remainder was the whole rest of the list, it clicked at {rel(pa)*100:.0f}% of the engaged rate; from May 8 the remainder also excluded the 'disengaged' drip segment, leaving about 50k mostly recent or unflagged subscribers who clicked at {rel(pm)*100:.0f}% of the engaged rate. The cost of the remainder is not missing clicks, it is unsubscribes, spam reports and the domain reputation that the next section shows being spent.</p>")

parts.append("<h3>Engagement tiers inside the engaged segment (Sep 10, attraction tool launch)</h3>")
parts.append(table(["Send", "Audience", "Delivered", "Open", "Click", "Verified clicks", "Unsubs/1k"],
                   [[p["date_et"], p["aud_label"], fmt_int(p["delivered"]), pct(p["open_rate"]), pct(p["click_rate"], 2), fmt_int(p["verified_clicks"]), per_k(p["unsub_rate"])] for p in sep10]))
hi, rest, relaunch = sep10[0], sep10[1], sep10[2]
parts.append(f"<p>The 50-100% openers were {pct(hi['delivered']/(hi['delivered']+rest['delivered']),0)} of the recipients and produced {pct(hi['verified_clicks']/(hi['verified_clicks']+rest['verified_clicks']),0)} of the clicks. The Monday-morning re-launch four days later went, by the look of its provider breakdown, to the non-openers of the first send (Yahoo and Hotmail opened 10-17% instead of their usual 50-60%, so this is audience, not Gmail filtering). It opened at {pct(relaunch['open_rate'])} and still added {fmt_int(relaunch['verified_clicks'])} verified clicks, about {relaunch['verified_clicks']/(hi['verified_clicks']+rest['verified_clicks'])*100:.0f}% on top of the first send, at {per_k(relaunch['unsub_rate'])} unsubscribes per 1,000: a resend to non-openers with a fresh subject line is a reasonable tactic, a resend to everyone is not.</p>")

parts.append("<h3>All primary sends by audience class</h3>")
cls_rows = []
for c, label in [("all", "Whole list"), ("all_minus_nonopeners", "CT audience minus 0% openers"), ("engaged", "Engaged segment"), ("high", "Top openers")]:
    v = [p for p in core if p["aud_class"] == c]
    if not v:
        continue
    cls_rows.append([label, len(v), fmt_int(statistics.median(p["delivered"] for p in v)), pct(statistics.median(p["open_rate"] for p in v)), pct(statistics.median(p["click_rate"] for p in v), 2),
                     fmt_int(statistics.median(p["verified_clicks"] for p in v)), per_k(statistics.median(p["unsub_rate"] for p in v))])
parts.append(table(["Audience", "Sends", "Median delivered", "Median open", "Median click", "Median clicks per send", "Median unsubs/1k"], cls_rows))
parts.append(f"<p class='cap'>Whole-list sends were the norm from Sep 2025 to Mar 2026, when the list was growing through bulk imports (about 350k in Sep-Oct 2025). They yield about the same number of clicks per send as engaged-only sends, at 1.7x the unsubscribe rate, and they are the period in which the CT domain's reputation was spent. The engaged segment today means: CT audience flag, signed up over a week ago, and at least one open in six months or signed up within a month.</p>")

# ---- domain
parts.append("<h2>2. Sending domain and deliverability</h2>")
parts.append("<div class='fig'>" + time_chart(engaged_series, "open_rate", "Open rate of the regular newsletter (engaged-class audiences only)", 0.5, lambda v: pct(v, 0)) + "</div>")
parts.append("<div class='fig'>" + time_chart(engaged_series, "click_rate", "Verified click rate of the regular newsletter (engaged-class audiences only)", 0.012, lambda v: pct(v, 1)) + "</div>")
parts.append("<p class='cap'>Each dot is one primary send to the engaged segment (or, in Dec 2025, the CT audience minus 0% openers). Opens include Apple Mail Privacy prefetches, so use the click chart for real engagement. Hover a dot for the subject line.</p>")
parts.append("<div class='wrap'>" + table(["Month", "Domain", "Sends", "Mean open", "Mean verified click", "Mean unsubs/1k"], era_rows) + "</div>")
parts.append("<h3>The Aug 13 split test, by mailbox provider</h3>")
parts.append("<div class='wrap'>" + table(["Provider", "OHI domain delivered", "OHI open", "OHI clicks", "CT domain delivered", "CT open", "CT clicks"], isp_rows) + "</div>")
parts.append("<p class='cap'>The engaged segment was split into two static halves (176,761 and 176,146 recipients; provider mixes match to within 1%), sent at 6:16pm and 6:52pm ET. Gmail is where the two domains differ; Yahoo and Hotmail barely do, and iCloud's reversal is Apple's prefetch behaviour, not humans. Opens and clicks here include bot activity, per beehiiv.</p>")
if isp_trend:
    parts.append("<h3>Gmail open rate on the OHI domain since the switch</h3>")
    parts.append(table(["Send", "Subject", "Gmail delivered", "Gmail open", "Gmail clicks", "Yahoo open"],
                       [[r["date_et"], esc(r["subject"]), fmt_int(r["gmail"]["delivered"]), pct(r["gmail"]["opens"] / r["gmail"]["delivered"]), fmt_int(r["gmail"]["clicks"]), pct(r["yahoo"]["opens"] / r["yahoo"]["delivered"])] for r in isp_trend]))
    parts.append("<p class='cap'>Four OHI-domain sends. Yahoo is the control: where Yahoo holds while Gmail falls, the change is Gmail's reputation filtering rather than reader interest. Gmail slid from 34% to 26% between July and September while Yahoo stayed at 54-63%; part of that is the engaged segment's looser current definition (any open in six months), so this is a warning sign, not yet a diagnosis. The Sep 14 row is a resend to non-openers, and every provider is low there, which is what an audience effect looks like.</p>")

# ---- timing
parts.append("<h2>3. Timing: day and hour</h2>")
parts.append("<div class='fig'>" + send_slot_chart(big) + "</div>")
parts.append(f"<p class='cap'>Dot size is the number of sends in that weekday and hour. {len(thu_evening)} of {len(big)} large primary sends went out Thursday 6-9pm ET. beehiiv stores send times in UTC; they are shown here in US Eastern, where 54% of clicking readers are (US 49%, Canada 6%). Europe is 17% (UK 7%, Germany 3%), Asia-Pacific 10% (Australia 4%, Singapore 3%, India 2%).</p>")
odd_rows = [[p["date_et"], esc(p["subject_line"]), p["aud_label"], pct(p["open_rate"]), pct(p["click_rate"], 2), f"{p['click_index']:.2f}", f"{p['open_index']:.2f}"] for p in sorted(odd_slots, key=lambda p: -p["click_index"])]
parts.append("<details><summary>The sends outside Thursday 5-10pm ET (each is a single send with its own audience and content, so none of them is a fair timing comparison)</summary><div class='wrap'>" + table(["Sent (ET)", "Subject", "Audience", "Open", "Click", "Click index", "Open index"], odd_rows) + "</div></details>")
parts.append("<h3>How fast clicks arrive after a send</h3>")
parts.append("<div class='fig'>" + bars(tm["bucket_labels"], [s * 100 for s in tm["median_shares"]], f"Median share of a campaign's GA4 newsletter sessions by time since send ({len(tm['rows'])} campaigns since Jan 2026)", lambda v: f"{v:.0f}%") + "</div>")
parts.append(f"<p class='cap'>Source: GA4 sessions with utm_source clearerthinking.beehiiv.com, joined to each send by campaign slug; campaigns with 100+ sessions and 100k+ recipients. The 'after a week' bucket is inflated by later emails that reuse a link still carrying the original campaign tag.</p>")
parts.append("<div class='fig'>" + bars([f"{h:02d}" for h in range(24)], [v / tail_tot * 100 for v in tail], "Clicks arriving a day or more after the send, by hour of day (US Eastern)", lambda v: f"{v:.1f}%", highlight=lambda i: 8 <= i <= 17, note="Highlighted: 8am to 5pm ET") + "</div>")
parts.append(f"<p class='cap'>Once the send moment is out of the picture, reading spreads across the US working day: {pct(work_share,0)} of these late clicks fall between 8am and 5pm ET, peaking at 10-11am. The 10pm spike is the One Helpful Idea send hour (its emails link to newsletter articles with the newsletter's campaign tag), not a reading habit. Late clicks by weekday: " + ", ".join(f"{d} {n/sum(tm['tail_wdays'])*100:.0f}%" for d, n in zip(WD, tm["tail_wdays"])) + ".</p>")
parts.append("<div class='note'>What this does and does not say: the newsletter is not a moment, it is a queue item that gets read over several days by an audience spread over 15+ hours of time zones. That makes the send hour a second-order lever, and the history contains no controlled variation of it. The honest answer to 'best time' is the six-week paired test in the recommendations, with Friday 8am ET as the challenger (it lands in the morning for North America and early afternoon for Europe, and the late-click curve peaks mid-morning).</div>")

# ---- subject lines
parts.append("<h2>4. Subject lines</h2>")
parts.append(f"<p>Each of the {len(big)} large primary sends is indexed against the median of its six nearest sends to the same audience class (three before, three after), so that a subject line is judged against its own era rather than against the list's drift. A click index of 1.5 means 50% more verified clicks per delivered email than its neighbours.</p>")
parts.append("<div class='fig'>" + effects_chart(D["subject_effects"]["click"], D["subject_effects"]["open"]) + "</div>")
parts.append(f"<p class='cap'>Ratio of the geometric-mean index with the feature to without it; * marks a permutation p-value below 0.05. Only 'mentions a tool' clears it (clicks x{eff_c['tool']['ratio']:.2f}, p={eff_c['tool']['p']:.3f}; opens x{eff_o['tool']['ratio']:.2f}, p={eff_o['tool']['p']:.3f}), and that is a content effect (the email offers a tool) rather than wording. 'Contains a number' and 'has a [tag]' rest on two sends each. Question-word openers: opens x{eff_o['question_word']['ratio']:.2f} (p={eff_o['question_word']['p']:.2f}), clicks x{eff_c['question_word']['ratio']:.2f} (p={eff_c['question_word']['p']:.2f}). Everything else is within noise.</p>")
parts.append("<h3>Highest click index</h3><div class='wrap'>" + subjects_table(top_click, "click_index") + "</div>")
parts.append("<h3>Lowest click index</h3><div class='wrap'>" + subjects_table(bot_click, "click_index") + "</div>")
parts.append("<h3>Highest open index</h3><div class='wrap'>" + subjects_table(top_open, "open_index") + "</div>")
parts.append("<p>Reading the two ends: the top is a specific payoff the reader can picture (82 techniques, 100 books, a free tool, a disorder nobody has heard of, the popular myths you might believe). The bottom is a topic rather than a payoff (what's scaring people about AI, four overlooked ideas, career advice from experts, the most important self-help tip). Opens follow curiosity and psychology topics; clicks follow the offer. A subject line that promises something concrete inside the email is the pattern that survives across audiences and eras.</p>")
parts.append("<p>" + f"{len(ab_tested)} newsletter sends were A/B tested in beehiiv ({', '.join(esc(p['subject_line'][:45]) for p in ab_tested)}). The API exposes only the winning line, not the variants or their rates; those sit in each post's A/B Test tab in the beehiiv app and are worth transcribing into a log." + "</p>")

# ---- recommendations
parts.append("<h2>5. Recommendations, scored</h2>")
for score, name, what, pro, con in sorted(RECS, key=lambda r: -r[0]):
    parts.append(f"<div class='rec'><h3><span class='sc'>{score}/10</span>{esc(name)}</h3><p>{esc(what)}</p><p class='pro'><b>For:</b> {esc(pro)}</p><p class='con'><b>Against:</b> {esc(con)}</p></div>")

# ---- appendix
parts.append("<h2>Appendix</h2><h3>What was included</h3>")
parts.append(table(["Category", "Posts", "Meaning"], [
    ["core", cats.get("core", 0), "Clearer Thinking newsletter proper: articles, data studies, tool launches (primary sends plus next-day resends and the domain-test halves)"],
    ["ohi", cats.get("ohi", 0), "One Helpful Idea (excluded)"],
    ["event", cats.get("event", 0), "Workshop and webinar invitations, reminders, recordings (excluded)"],
    ["promo", cats.get("promo", 0), "Book launch, CT+ announcement, partner promos, newsletter swap, dating-app update, link fixes (excluded)"],
    ["coaching_outreach", cats.get("coaching_outreach", 0), "Coaching trial invitations and outreach (excluded)"],
    ["recruitment", cats.get("recruitment", 0), "Beta-tester and study invitations, survey thank-you (excluded)"],
    ["wrapup", cats.get("wrapup", 0), "Monthly Debrief, mostly to CT+ members (excluded from the newsletter analysis)"],
    ["transactional / small / test", cats.get("transactional", 0) + cats.get("small", 0) + cats.get("test", 0), "Personality-report access, sends under 1,000 recipients, test sends (excluded)"],
]))
parts.append("<h3>Definitions</h3><ul><li>Open rate = unique opens / delivered (beehiiv's definition; includes Apple Mail Privacy Protection prefetches and scanners).</li><li>Click rate = unique verified clicks / delivered. beehiiv's 'verified' count removes bot and scanner clicks; it is the closest thing to real reader engagement in this data.</li><li>Click index / open index = the send's rate divided by the median rate of its six nearest primary sends to the same audience class.</li><li>Send times were converted from beehiiv's UTC timestamps to US Eastern. GA4's property clock is US Eastern (verified: the Sep 18 send at 23:00 UTC appears at hour 19).</li><li>Feature tests use a two-sided permutation test on the log index with 5,000 shuffles.</li></ul>")
all_rows = [[p["date_et"], esc(p["title"][:70]), p["category"] + (" (resend)" if p.get("resend") else ""), p["aud_label"], p["domain"], fmt_int(p["delivered"]), pct(p["open_rate"]), pct(p["click_rate"], 2)] for p in sorted(D["posts"], key=lambda p: p["date_utc"], reverse=True)]
parts.append("<details><summary>All 173 confirmed posts with their classification</summary><div class='wrap'>" + table(["Sent (ET)", "Title", "Category", "Audience", "Domain", "Delivered", "Open", "Click"], all_rows) + "</div></details>")
parts.append("<p class='cap'>Source code: reports/newsletter_send_strategy_2026-09-25_src (fetch_data.py, analysis.py, build_report.py); tests in tests/test_newsletter_send_strategy.py.</p>")
parts.append("</main></body></html>")
OUT.write_text("".join(parts))
print("wrote", OUT, f"{OUT.stat().st_size/1024:.0f} KB")
