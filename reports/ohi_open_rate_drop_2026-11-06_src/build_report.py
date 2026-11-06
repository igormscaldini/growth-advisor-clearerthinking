"""datapoints.json -> reports/ohi_open_rate_drop_2026-11-06.html

    python analysis.py && python build_report.py [--open]

Every number in the page comes from datapoints.json (analysis.py) except the few constants under "Quoted from
elsewhere" below, each with its source.
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "ohi_open_rate_drop_2026-11-06.html"
DP = json.load(open(HERE / "datapoints.json"))
OHI = DP["ohi"]
FILT = [m for m in OHI if m["audience"] == "filtered"]
WHOLE = [m for m in OHI if m["audience"] == "whole"]
OTHER = DP["other"]

# ---- Quoted from elsewhere (not in data.json) ------------------------------------------------------------------
# Main newsletter sends from the same domain, per-provider rows pulled for the 2026-09-25 send-strategy report
# (reports/newsletter_send_strategy_2026-09-25_src/data/isp_trend.json): Gmail unique opens / delivered.
MAIN_NEWSLETTER_GMAIL = {"2026-08-20": 63729 / 237804, "2026-09-18": 61547 / 240187}
# Same-email split sends not in the provider pull (beehiiv v2 API totals): unique opens / delivered, first half then second.
SPLIT_OCT8 = (31597 / 163904, 49855 / 163561)

X0, X1 = date(2026, 1, 1), date(2026, 10, 31)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def pct(x: float, d: int = 0) -> str:
    return f"{100 * x:.{d}f}%"


def k(n: float) -> str:
    return f"{n / 1000:.0f}k"


def nice_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{MONTHS[d.month - 1]} {d.day}"


def by_date(rows: list[dict], iso: str, min_recipients: int = 0) -> dict:
    return next(r for r in rows if r["date"] == iso and r["recipients"] >= min_recipients)


class Plot:
    """A time-series frame: x = date within 2026, y = linear. No gridlines, no box: a baseline and tick labels only."""

    def __init__(self, w, h, left, right, top, bottom, ymax, yticks, yfmt):
        self.w, self.h, self.l, self.r, self.t, self.b = w, h, left, right, top, bottom
        self.ymax, self.yticks, self.yfmt = ymax, yticks, yfmt

    def x(self, iso: str) -> float:
        return self.l + (date.fromisoformat(iso) - X0).days / (X1 - X0).days * (self.w - self.l - self.r)

    def y(self, v: float) -> float:
        return self.h - self.b - v / self.ymax * (self.h - self.t - self.b)

    def frame(self) -> str:
        out = [f'<line x1="{self.l}" x2="{self.w - self.r}" y1="{self.y(0):.1f}" y2="{self.y(0):.1f}" stroke="var(--rule)"/>']
        for v in self.yticks:
            out.append(f'<text x="{self.l - 8}" y="{self.y(v) + 4:.1f}" text-anchor="end" class="ax">{self.yfmt(v)}</text>')
        for mth in range(1, 11):
            xx = self.x(f"2026-{mth:02d}-01")
            out.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{self.y(0):.1f}" y2="{self.y(0) + 4:.1f}" stroke="var(--rule)"/>')
            out.append(f'<text x="{xx + 3:.1f}" y="{self.h - self.b + 17:.1f}" class="ax">{MONTHS[mth - 1]}</text>')
        return "".join(out)

    def open(self, label: str) -> str:
        return f'<svg viewBox="0 0 {self.w} {self.h}" width="100%" style="max-width:{self.w}px" role="img" aria-label="{esc(label)}">'


def dot(x, y, filled=True, color="var(--s1)") -> str:
    if filled:
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="var(--bg)" stroke-width="2"/>'
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--bg)" stroke="{color}" stroke-width="2"/>'


def hit(x, y, tip, r=13) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="transparent" tabindex="0" data-tip="{esc(tip)}"/>'


def aud_label(m: dict) -> str:
    return "whole list" if m["audience"] == "whole" else "engaged readers only"


# ------------------------------------------------------------------------------------------------ charts
def chart_headline() -> str:
    p = Plot(880, 300, 44, 60, 22, 30, 0.5, [0, 0.1, 0.2, 0.3, 0.4, 0.5], lambda v: pct(v))
    s = [p.open("Open rate of every One Helpful Idea send in 2026"), p.frame()]
    for m in OHI:
        s.append(dot(p.x(m["date"]), p.y(m["open_rate"]), m["audience"] == "filtered"))
    first, last = OHI[0], OHI[-1]
    s.append(f'<text x="{p.x(first["date"]) + 9:.1f}" y="{p.y(first["open_rate"]) - 9:.1f}" class="lab">{pct(first["open_rate"])}</text>')
    s.append(f'<text x="{p.x(last["date"]) + 10:.1f}" y="{p.y(last["open_rate"]) + 4:.1f}" class="lab">{pct(last["open_rate"])}</text>')
    for m in OHI:
        tip = f'{nice_date(m["date"])}: {pct(m["open_rate"], 1)} opened\n{m["subject"]}\n{m["recipients"]:,} recipients, {aud_label(m)}'
        s.append(hit(p.x(m["date"]), p.y(m["open_rate"]), tip))
    return "".join(s) + "</svg>"


def chart_gmail_vs_others() -> str:
    p = Plot(880, 340, 44, 150, 46, 30, 0.7, [0, 0.2, 0.4, 0.6], lambda v: pct(v))
    s = [p.open("Gmail and other providers, open rate on engaged-audience sends"), p.frame()]
    top, base = p.t - 6, p.y(0)
    xj, xb = p.x("2026-07-01"), (p.x(DP["split"]["last_before"]) + p.x(DP["split"]["first_after"])) / 2
    for xx in (xj, xb):
        s.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{top:.1f}" y2="{base:.1f}" stroke="var(--rule)"/>')
    s.append(f'<text x="{xj - 6:.1f}" y="{top + 8:.1f}" text-anchor="end" class="ax">Jul 1: main newsletter moves onto this domain</text>')
    s.append(f'<text x="{xb + 6:.1f}" y="{top + 8:.1f}" class="ax">Mid August: Gmail breaks away</text>')
    for key, color in (("control_rate", "var(--s2)"), ("gmail_rate", "var(--s1)")):
        pts = " ".join(f'{p.x(m["date"]):.1f},{p.y(m[key]):.1f}' for m in FILT)
        s.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for m in FILT:
            s.append(f'<circle cx="{p.x(m["date"]):.1f}" cy="{p.y(m[key]):.1f}" r="4" fill="{color}" stroke="var(--bg)" stroke-width="2"/>')
    last = FILT[-1]
    xe = p.x(last["date"]) + 12
    s.append(f'<text x="{xe:.1f}" y="{p.y(last["control_rate"]) + 4:.1f}" class="lab">Other providers {pct(last["control_rate"])}</text>')
    s.append(f'<text x="{xe:.1f}" y="{p.y(last["gmail_rate"]) + 4:.1f}" class="lab">Gmail {pct(last["gmail_rate"])}</text>')
    for m in FILT:
        tip = (f'{nice_date(m["date"])}, {m["recipients"]:,} recipients\n{pct(m["control_rate"], 1)} other providers\n'
               f'{pct(m["gmail_rate"], 1)} Gmail\n{m["subject"]}')
        s.append(f'<rect x="{p.x(m["date"]) - 8:.1f}" y="{p.t}" width="16" height="{base - p.t:.1f}" fill="transparent" tabindex="0" data-tip="{esc(tip)}"/>')
    return "".join(s) + "</svg>"


def chart_ratio() -> str:
    p = Plot(880, 290, 44, 150, 16, 30, 1.2, [0, 0.4, 0.8, 1.2], lambda v: f"{v:.1f}")
    sp = DP["split"]
    s = [p.open("Gmail open rate divided by other providers' open rate, every OHI send"), p.frame()]
    xr = p.w - p.r
    s.append(f'<line x1="{p.x(FILT[0]["date"]):.1f}" x2="{xr}" y1="{p.y(sp["mean_before"]):.1f}" y2="{p.y(sp["mean_before"]):.1f}" stroke="var(--rule)" stroke-width="2"/>')
    s.append(f'<line x1="{p.x(sp["first_after"]):.1f}" x2="{xr}" y1="{p.y(sp["mean_after"]):.1f}" y2="{p.y(sp["mean_after"]):.1f}" stroke="var(--rule)" stroke-width="2"/>')
    s.append(f'<text x="{xr + 8}" y="{p.y(sp["mean_before"]) + 4:.1f}" class="lab">{sp["mean_before"]:.2f} until Aug 5</text>')
    s.append(f'<text x="{xr + 8}" y="{p.y(sp["mean_after"]) + 4:.1f}" class="lab">{sp["mean_after"]:.2f} since Aug 18</text>')
    for m in OHI:
        s.append(dot(p.x(m["date"]), p.y(m["ratio"]), m["audience"] == "filtered"))
    for m in OHI:
        tip = (f'{nice_date(m["date"])}: ratio {m["ratio"]:.2f}\nGmail {pct(m["gmail_rate"], 1)}, other providers {pct(m["control_rate"], 1)}\n'
               f'{m["recipients"]:,} recipients, {aud_label(m)}')
        s.append(hit(p.x(m["date"]), p.y(m["ratio"]), tip))
    return "".join(s) + "</svg>"


def chart_volume() -> str:
    rows = [r for r in DP["domain_months"] if r["from_domain"] == "ohi" and r["month"] <= "2026-10"]
    w, h, left, top, bottom = 880, 270, 44, 26, 30
    ymax, bw = 3.6e6, 24
    step = (w - left - 20) / len(rows)

    def y(v):
        return h - bottom - v / ymax * (h - top - bottom)

    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px" role="img" aria-label="Emails delivered per month from the OHI sending domain">',
         f'<line x1="{left}" x2="{w - 20}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="var(--rule)"/>']
    for v in (0, 1e6, 2e6, 3e6):
        s.append(f'<text x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end" class="ax">{v / 1e6:.0f}M</text>')
    labelled = {"2026-06", "2026-07", "2026-09"}
    for i, r in enumerate(rows):
        cx = left + step * (i + 0.5)
        x0, low, reg = cx - bw / 2, r["low_open_delivered"], r["delivered"] - r["low_open_delivered"]
        yt = y(r["delivered"])
        if low:
            yr = y(reg)
            s.append(f'<rect x="{x0:.1f}" y="{yr + 1:.1f}" width="{bw}" height="{y(0) - yr - 1:.1f}" fill="var(--s1)"/>')
            s.append(f'<path d="M{x0:.1f},{yr - 1:.1f} V{yt + 4:.1f} q0,-4 4,-4 h{bw - 8} q4,0 4,4 V{yr - 1:.1f} Z" fill="var(--s2)"/>')
        else:
            s.append(f'<path d="M{x0:.1f},{y(0):.1f} V{yt + 4:.1f} q0,-4 4,-4 h{bw - 8} q4,0 4,4 V{y(0):.1f} Z" fill="var(--s1)"/>')
        mth = int(r["month"][5:])
        s.append(f'<text x="{cx:.1f}" y="{h - bottom + 17}" text-anchor="middle" class="ax">{MONTHS[mth - 1]}{" " + r["month"][:4] if mth in (12, 1) else ""}</text>')
        if r["month"] in labelled:
            s.append(f'<text x="{cx:.1f}" y="{yt - 7:.1f}" text-anchor="middle" class="lab">{r["delivered"] / 1e6:.1f}M</text>')
        tip = (f'{MONTHS[mth - 1]} {r["month"][:4]}: {r["delivered"]:,} emails delivered in {r["sends"]} sends\n'
               f'{low:,} of them in sends that opened under 15%\nAverage open rate {pct(r["open_rate"], 1)}')
        s.append(f'<rect x="{cx - step / 2:.1f}" y="{top}" width="{step:.1f}" height="{y(0) - top:.1f}" fill="transparent" tabindex="0" data-tip="{esc(tip)}"/>')
    return "".join(s) + "</svg>"


# ------------------------------------------------------------------------------------------------ page
CSS = """
:root{--bg:#fcfcfb;--t1:#0b0b0b;--t2:#52514e;--rule:#dddbd5;--s1:#2a78d6;--s2:#eb6834;--card:#f4f3f0;color-scheme:light}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a19;--t1:#f0efec;--t2:#c3c2b7;--rule:#3d3d3a;--s1:#3987e5;--s2:#d95926;--card:#232322;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#1a1a19;--t1:#f0efec;--t2:#c3c2b7;--rule:#3d3d3a;--s1:#3987e5;--s2:#d95926;--card:#232322;color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--t1);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:900px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;line-height:1.2;margin:0 0 6px}h2{font-size:20px;margin:40px 0 8px}h3{font-size:16px;margin:0 0 6px}
.sub{color:var(--t2);font-size:13px;margin:0 0 22px}p{margin:10px 0}li{margin:6px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:18px 0}
.kpi{background:var(--card);border-radius:10px;padding:12px 14px}.kpi b{display:block;font-size:24px;line-height:1.15;margin-bottom:4px;font-weight:650}.kpi span{color:var(--t2);font-size:13px}
.fig{margin:14px 0 6px}.fig h3{margin-bottom:2px}.cap{color:var(--t2);font-size:13px;margin:0 0 6px}
.legend{display:flex;gap:18px;flex-wrap:wrap;color:var(--t2);font-size:13px;margin:4px 0 2px}.legend i{display:inline-block;vertical-align:middle;margin-right:6px}
.k-dot{width:10px;height:10px;border-radius:50%;background:var(--s1)}.k-ring{width:7px;height:7px;border-radius:50%;border:2px solid var(--s1)}
.k-l1,.k-l2{width:18px;height:2px}.k-l1{background:var(--s1)}.k-l2{background:var(--s2)}.k-b1,.k-b2{width:11px;height:11px;border-radius:2px}.k-b1{background:var(--s1)}.k-b2{background:var(--s2)}
svg text{font-family:inherit}.ax{fill:var(--t2);font-size:12px;font-variant-numeric:tabular-nums}.lab{fill:var(--t1);font-size:12.5px;font-weight:600}
svg [data-tip]{outline:none;cursor:default}svg [data-tip]:focus-visible{stroke:var(--t2);stroke-width:1}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:10px 0}th,td{text-align:left;padding:6px 10px 6px 0;border-bottom:1px solid var(--rule);vertical-align:top}
th{color:var(--t2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow-x:auto}.note{background:var(--card);border-radius:10px;padding:12px 16px;margin:14px 0}
.rec{background:var(--card);border-radius:10px;padding:12px 16px;margin:10px 0}.rec p{margin:6px 0}
.sc{display:inline-block;min-width:44px;text-align:center;border-radius:8px;background:var(--t1);color:var(--bg);font-weight:700;padding:1px 6px;margin-right:8px;font-size:14px}
details{margin:14px 0}summary{cursor:pointer;color:var(--t2)}
#tip{position:fixed;display:none;pointer-events:none;background:var(--t1);color:var(--bg);font-size:12.5px;line-height:1.4;padding:7px 10px;border-radius:7px;max-width:320px;white-space:pre-line;z-index:9}
"""

JS = """
(function(){var tip=document.getElementById('tip');
function show(el,e){tip.textContent=el.getAttribute('data-tip');tip.style.display='block';
 var r=el.getBoundingClientRect(),x=(e&&e.clientX!=null?e.clientX:r.left+r.width/2)+14,y=(e&&e.clientY!=null?e.clientY:r.top)+14;
 var w=tip.offsetWidth,h=tip.offsetHeight;if(x+w>window.innerWidth-8)x=Math.max(8,x-w-28);if(y+h>window.innerHeight-8)y=Math.max(8,y-h-28);
 tip.style.left=x+'px';tip.style.top=y+'px';}
function hide(){tip.style.display='none';}
document.querySelectorAll('[data-tip]').forEach(function(el){
 el.addEventListener('pointermove',function(e){show(el,e);});el.addEventListener('pointerleave',hide);
 el.addEventListener('focus',function(){show(el,null);});el.addEventListener('blur',hide);});})();
"""


def ideas() -> str:
    c = DP["counterfactual"]
    pairs = {p["whole_date"]: p for p in DP["whole_vs_filtered"]}
    items = [
        (9, "Look at Google Postmaster Tools for ohi.clearerthinking.net",
         "Google's free dashboard of how Gmail itself sees a sending domain: the share of recipients who press \"Report spam\", authentication, "
         "delivery errors and whether the domain meets Gmail's bulk-sender rules (spam rate under 0.1%, never 0.3%). If the domain is not set up "
         "there yet, it takes one DNS record.",
         "It is the only place Gmail's spam complaints are visible (beehiiv's spam counts leave Gmail out), and ten minutes there confirms or kills the diagnosis in this report.",
         "It tells you how bad things are, not how to fix them, and it may hold no history if the domain was never verified."),
        (9, "Send OHI to proven readers only for six weeks",
         "Use a strict engaged audience (the segment as it is defined today, open rate of 30% or more, about 161k people, is strict enough) for every OHI "
         f"send, and watch whether Gmail's open rate climbs back toward the {pct(DP['periods']['before_break']['gmail_rate'])} of early August.",
         f"Since July, mailing more people has not produced more opens: the Aug 10 send to {k(pairs['2026-08-10']['whole_recipients'])} got "
         f"{abs(pairs['2026-08-10']['extra_unique_opens']):,} fewer opens than the Aug 5 send to {k(pairs['2026-08-10']['filtered_recipients'])}. So there is little to lose, "
         "and steady engagement from a smaller audience is how a sender earns its way back at Gmail.",
         "The reported subscriber reach of OHI drops, which matters for sponsor numbers, and Gmail readers whose opens are currently not being recorded could be cut by an open-based filter."),
        (8, "Keep resends to non-openers and whole-list blasts off this domain",
         "The Sep 14 re-launch (6% opened), the Oct 29 resend (2.6% opened, 1.0% at Gmail) and whole-list sends teach Gmail that mail from this domain is mostly ignored. "
         "Stop them, or send them rarely and from a different subdomain so OHI and the main newsletter are not graded with them.",
         "It removes the most likely cause, and it costs only the few hundred clicks each of those sends brings (434 verified clicks on Oct 29).",
         "Launch emails lose their second wave, and a separate subdomain is one more thing to maintain."),
        (6, "Test OHI with and without the second tracking pixel",
         "Since Aug 5 every OHI email carries your own open-tracking pixel, hosted on a shared vercel.app address, next to beehiiv's. The main newsletter does not carry it. "
         "Send one OHI in two random halves, one with the pixel and one without, and compare Gmail's open rate. "
         "In plain terms: spam filters also judge the web addresses inside an email, and free shared hosting addresses have a poor name because scammers use them.",
         "It is free, takes one send, and the pixel is redundant for counting (it follows beehiiv's numbers at a constant ratio).",
         "The evidence is thin: April's main newsletters carried the same pixel with no visible effect, and the first two OHI sends with it (Aug 5, Aug 10) were normal."),
        (6, "Run an inbox placement test",
         "Services such as GlockApps send your email to a panel of test mailboxes and report where it landed: inbox, Promotions or Spam, per provider.",
         "It answers directly the one thing this data cannot: whether Gmail is hiding OHI in Spam, moving it to Promotions or just not loading images.",
         "Test mailboxes have no reading history, so they show the worst case, not what an engaged reader gets. It costs a little money."),
        (5, "Re-test the old sending domain on a small engaged sample",
         "info@clearerthinking.net has barely been used since July. Repeat the Aug 13 two-domain test on about 20k engaged readers per half.",
         "If the rested domain has recovered at Gmail, that is proof that rest plus engaged-only sending works, and it gives you a fallback.",
         "A dormant domain that suddenly sends volume is itself suspicious to Gmail, hence the small sample. It also does not fix anything by itself."),
        (2, "Move OHI to a fresh sending domain",
         "Set up a new subdomain and send OHI from it.",
         "A new domain starts with no bad history, and the July move did lift opens for a few weeks.",
         "This is what was done in July. The old domain's Gmail ratio had fallen from 0.98 to 0.51 in six weeks at the start of the year; the new one lasted about six weeks "
         "before it followed. The standing follows the sending habits, not the name, and a brand-new domain has to be warmed up slowly."),
    ]
    out = []
    for score, name, what, pro, con in items:
        out.append(f'<div class="rec"><h3><span class="sc">{score}/10</span>{esc(name)}</h3><p>{esc(what)}</p>'
                   f'<p><b>For:</b> {esc(pro)}</p><p><b>Against:</b> {esc(con)}</p></div>')
    return "".join(out)


def build() -> str:
    P, C, SP, CL = DP["periods"], DP["counterfactual"], DP["split"], DP["clicks"]
    jan, bb, ab, octo = P["january"], P["before_break"], P["after_break_same_audience"], P["october"]
    total_drop = jan["open_rate"] - octo["open_rate"]
    drift, gmail_part, wider = jan["open_rate"] - bb["open_rate"], C["october_cf"] - C["october_actual"], bb["open_rate"] - C["october_cf"]
    gmail_share = mean(m["gmail_share"] for m in FILT if m["date"][5:7] == "10")
    aug5, aug18, aug25 = (by_date(OHI, d) for d in ("2026-08-05", "2026-08-18", "2026-08-25"))
    aug10, jul14 = by_date(OHI, "2026-08-10"), by_date(OHI, "2026-07-14")
    feb3, mar10 = by_date(OHI, "2026-02-03"), by_date(OHI, "2026-03-10")
    sep9, sep21, sep28, oct20 = (by_date(OHI, d) for d in ("2026-09-09", "2026-09-21", "2026-09-28", "2026-10-20"))
    months = {r["month"]: r for r in DP["domain_months"] if r["from_domain"] == "ohi"}
    jul30, oct22, oct29 = by_date(OTHER, "2026-07-30"), by_date(OTHER, "2026-10-22"), by_date(OTHER, "2026-10-29")
    sep1o, sep10o = by_date(OTHER, "2026-09-01"), by_date(OTHER, "2026-09-10")
    nov5 = sorted((m for m in OTHER if m["date"] == "2026-11-05"), key=lambda m: m["open_rate"])
    ct = {m["date"]: m for m in OTHER if m["from_domain"] == "ct"}
    pairs = DP["whole_vs_filtered"]
    stamp = datetime.now().strftime("%Y-%m-%d %I:%M%p").lower()

    pair_rows = "".join(
        f'<tr><td>{nice_date(p["whole_date"])}</td><td class="n">{p["whole_recipients"]:,}</td><td>{nice_date(p["filtered_date"])}</td>'
        f'<td class="n">{p["filtered_recipients"]:,}</td><td class="n">{p["extra_unique_opens"]:+,}</td><td class="n">{p["extra_gmail_opens"]:+,}</td></tr>' for p in pairs)
    data_rows = "".join(
        f'<tr><td>{nice_date(m["date"])}</td><td>{esc(m["subject"].replace("One Helpful Idea: ", ""))}</td><td>{"Whole list" if m["audience"] == "whole" else "Engaged"}</td>'
        f'<td class="n">{m["recipients"]:,}</td><td class="n">{pct(m["open_rate"], 1)}</td><td class="n">{pct(m["gmail_rate"], 1)}</td>'
        f'<td class="n">{pct(m["control_rate"], 1)}</td><td class="n">{m["ratio"]:.2f}</td><td class="n">{m["click_ratio"]:.2f}</td></tr>' for m in OHI)
    month_rows = "".join(
        f'<tr><td>{MONTHS[int(r["month"][5:]) - 1]} {r["month"][:4]}</td><td class="n">{r["sends"]}</td><td class="n">{r["delivered"]:,}</td>'
        f'<td class="n">{r["low_open_delivered"]:,}</td><td class="n">{pct(r["open_rate"], 1)}</td></tr>'
        for r in DP["domain_months"] if r["from_domain"] == "ohi" and r["month"] <= "2026-10")

    body = f"""
<h1>Why One Helpful Idea opens fell in 2026</h1>
<p class="sub">{stamp} · {len(OHI)} One Helpful Idea sends, Jan 6 to Oct 20, 2026 · beehiiv send statistics split by mailbox provider, cross-checked against your own open pixel in GA4</p>

<p>The open rate of One Helpful Idea (OHI) went from {pct(jan["open_rate"])} in January to {pct(octo["open_rate"])} in October. Most of that is not readers losing interest. It is three separate things stacked on top of each other:</p>
<ul>
<li><b>Gmail stopped registering opens, about {100 * gmail_part:.0f} points.</b> Between Aug 5 and Aug 25, on the same engaged audience, Gmail's open rate fell from {pct(aug5["gmail_rate"], 1)} to {pct(aug25["gmail_rate"], 1)}. Readers on Yahoo, Hotmail, Outlook and AOL opened the very same emails at {pct(aug5["control_rate"], 1)} and then {pct(aug25["control_rate"], 1)}. Gmail is {pct(gmail_share)} of the audience, so it drags the whole number, and it has not recovered: {pct(octo["gmail_rate"])} in October.</li>
<li><b>A slow drift before that, about {100 * drift:.0f} points.</b> From January to early August, on the same size of audience, the rate eased from {pct(jan["open_rate"])} to {pct(bb["open_rate"])} (Gmail {pct(jan["gmail_rate"], 1)} to {pct(bb["gmail_rate"], 1)}, the other providers {pct(jan["control_rate"], 1)} to {pct(bb["control_rate"], 1)}).</li>
<li><b>A wider audience, about {100 * wider:.1f} points.</b> In September the "engaged" audience OHI goes to grew from about {k(ab["recipients"])} to about {k(octo["recipients"])} people. The added readers open less, which lowers the rate without anyone reading less.</li>
</ul>
<p>The timing points at the sending domain's standing with Gmail, not at the content. On Jul 1 the main newsletter moved onto OHI's sending domain (ohi.clearerthinking.net). Mail from that domain went from {months["2026-06"]["delivered"] / 1e6:.1f}M emails a month to {months["2026-07"]["delivered"] / 1e6:.1f}M, then {months["2026-09"]["delivered"] / 1e6:.1f}M in September, and it started carrying sends to the whole list and resends to people who never open. Gmail's treatment of OHI changed six weeks later.</p>

<div class="kpis">
<div class="kpi"><b>{pct(jan["open_rate"])} → {pct(octo["open_rate"])}</b><span>OHI open rate, January vs October (3 sends each)</span></div>
<div class="kpi"><b>{pct(jan["gmail_rate"])} → {pct(octo["gmail_rate"])}</b><span>Gmail readers</span></div>
<div class="kpi"><b>{pct(jan["control_rate"])} → {pct(octo["control_rate"])}</b><span>Yahoo, Hotmail, Outlook and AOL readers</span></div>
<div class="kpi"><b>{pct(C["october_cf"], 1)}</b><span>October open rate if Gmail had kept its usual gap to the others (actual {pct(C["october_actual"], 1)}): about {C["october_missing_gmail_opens"] / 1000:.0f}k Gmail opens missing per send</span></div>
</div>

<h2>1. The headline number mixes two audiences</h2>
<div class="fig"><h3>Open rate of every OHI send in 2026</h3>
<div class="legend"><span><i class="k-dot"></i>Sent to engaged readers only</span><span><i class="k-ring"></i>Sent to the whole list</span></div>
{chart_headline()}</div>
<p>Until July, every dip to around 25% is a send to the whole list and every recovery is a send to engaged readers only. Those swings are a choice of audience, not a change in readers. The real change is on the right: from mid August the engaged-only sends fall too, and the audience was then widened (277k on Sep 9, 376k on Sep 28), which pushes the rate down further.</p>

<h2>2. From mid August, Gmail and everyone else part ways</h2>
<div class="fig"><h3>Open rate by mailbox provider, engaged-audience sends</h3>
<div class="legend"><span><i class="k-l2"></i>Yahoo, Hotmail, Outlook and AOL together</span><span><i class="k-l1"></i>Gmail</span></div>
{chart_gmail_vs_others()}</div>
<p>A Gmail reader and a Yahoo reader of the same send get the same topic, subject line, send time and audience rule. If readers were tiring of OHI, both lines would fall. Only Gmail's does. The orange line eases from September because of the wider audience; it shows no break.</p>
<div class="fig"><h3>Gmail's open rate as a share of the other providers' open rate</h3>
<p class="cap">1.0 would mean Gmail readers open as often as readers elsewhere. Every OHI send of 2026.</p>
<div class="legend"><span><i class="k-dot"></i>Engaged readers only</span><span><i class="k-ring"></i>Whole list</span></div>
{chart_ratio()}</div>
<p>For {SP["n_before"]} engaged-audience sends in a row (Jan 6 to Aug 5) this ratio stayed between {SP["min_before"]:.2f} and {SP["max_before"]:.2f}. For the {SP["n_after"]} sends since, between {SP["min_after"]:.2f} and {SP["max_after"]:.2f}. The two ranges do not overlap. A change-point search over the series places the break between {nice_date(SP["last_before"])} and {nice_date(SP["first_after"])} without being told where to look, and lands on the same date when Yahoo alone is the comparison ({DP["split_yahoo_only"]["mean_before"]:.2f} before, {DP["split_yahoo_only"]["mean_after"]:.2f} after). Sends to the whole list broke a month earlier: {DP["split_whole"]["mean_before"]:.2f} on average through Jun 11, then {jul14["ratio"]:.2f} on Jul 14 and {aug10["ratio"]:.2f} on Aug 10.</p>

<h2>3. What changed on the sending domain</h2>
<div class="fig"><h3>Emails delivered per month from ohi.clearerthinking.net</h3>
<div class="legend"><span><i class="k-b1"></i>Sends that opened at 15% or more</span><span><i class="k-b2"></i>Sends that opened under 15%</span></div>
{chart_volume()}</div>
<ul>
<li><b>Jul 1:</b> the main newsletter starts sending from this domain. Until then it carried OHI only, 3 or 4 sends a month.</li>
<li><b>Jul 14:</b> first sign. OHI to the whole list ({jul14["recipients"]:,}) gets {pct(jul14["gmail_rate"], 1)} at Gmail, against 23% to 27% for the seven whole-list sends before it, and fewer opens in total than the engaged-only send a week later.</li>
<li><b>Jul 30:</b> the book-launch email is the first where Gmail collapses against the rest (ratio {jul30["ratio"]:.2f}).</li>
<li><b>Aug 10:</b> OHI goes to {aug10["recipients"]:,} people, the largest send from this domain up to then. It returns {abs(pairs[-1]["extra_unique_opens"]):,} fewer opens than the Aug 5 send to {aug5["recipients"]:,}.</li>
<li><b>Aug 18 and Aug 25:</b> on the engaged audience, Gmail goes {pct(aug5["gmail_rate"], 1)}, {pct(aug18["gmail_rate"], 1)}, {pct(aug25["gmail_rate"], 1)}. The other providers go {pct(aug5["control_rate"], 1)}, {pct(aug18["control_rate"], 1)}, {pct(aug25["control_rate"], 1)}.</li>
<li><b>September:</b> {months["2026-09"]["sends"]} sends and {months["2026-09"]["delivered"] / 1e6:.1f}M emails, of which {months["2026-09"]["low_open_delivered"] / 1000:.0f}k in three sends that opened under 15% (the dating app update, the "everyone else" half of a tool launch at {pct(sep10o["open_rate"], 1)}, and a re-launch to non-openers). OHI's engaged audience is widened in the same weeks.</li>
<li><b>Oct 22 and Oct 29:</b> the main newsletter goes to {oct22["recipients"]:,} people, then a resend to {oct29["recipients"]:,} opens at {pct(oct29["open_rate"], 1)} ({pct(oct29["gmail_rate"], 1)} at Gmail).</li>
</ul>
<p><b>Since July, mailing more people no longer produces more opens.</b> Each whole-list OHI send, compared with the nearest send to the narrow engaged audience:</p>
<div class="scroll"><table><tr><th>Whole-list send</th><th class="n">Recipients</th><th>Nearest engaged-only send</th><th class="n">Recipients</th><th class="n">Extra unique opens</th><th class="n">Extra Gmail opens</th></tr>{pair_rows}</table></div>
<p>The old sending domain (info@clearerthinking.net) went through the same thing earlier. Its Gmail ratio was {ct["2026-01-08"]["ratio"]:.2f} on Jan 8, then {ct["2026-02-17"]["ratio"]:.2f} on Feb 17, {ct["2026-03-19"]["ratio"]:.2f} on Mar 19 and {ct["2026-06-02"]["ratio"]:.2f} on Jun 2, while it carried the whole-list sends and the next-day resends to non-openers. The pattern moved to the OHI domain along with those sending habits.</p>

<h2>4. Are Gmail readers gone, or just not counted?</h2>
<p>Partly not counted. Opens overstate the damage. Gmail's click rate, measured against the other providers' click rate on the same send, was {CL["ratio_before"]:.2f} before the break, {CL["ratio_after_aug_sep"]:.2f} from Aug 18 to Sep 28 and {CL["ratio_october"]:.2f} in October. So through September the Gmail readers who click were still receiving and reading OHI, while recorded opens had already halved. In October Gmail clicks are down by about a fifth as well ({CL["gmail_per_10k_october"]:.0f} per 10,000 delivered, from {CL["gmail_per_10k_before"]:.0f}).</p>
<p>That pattern is what you get when Gmail moves a sender's mail out of the inbox (to Spam or Promotions) or stops loading its images, starting with the least engaged recipients. All three are Gmail reacting to a domain whose mail many recipients ignore. Which of the three it is cannot be read from beehiiv: Google Postmaster Tools and an inbox placement test can show it.</p>

<h2>5. What I checked and ruled out</h2>
<div class="scroll"><table>
<tr><th>Possible cause</th><th>Check</th><th>Result</th></tr>
<tr><td>Content, subject lines, send time, reader fatigue</td><td>Other providers on the same sends</td><td>No break: {pct(bb["control_rate"])} before, {pct(ab["control_rate"])} just after, on the same audience</td></tr>
<tr><td>Gmail clipping long emails, which can hide the tracking pixel</td><td>HTML size of all {len(OHI)} emails; pixel position in three delivered copies</td><td>Median {DP["html"]["median_before_kb"]:.0f} KB before the break and {DP["html"]["median_after_kb"]:.0f} KB after, against a 102 KB clip limit (one email over it, on Jul 28). The pixel sits 17 KB in</td></tr>
<tr><td>Broken authentication</td><td>Headers of copies delivered Aug 5, Aug 26 and Oct 21</td><td>SPF and DKIM pass and one-click unsubscribe is present on all three, unchanged</td></tr>
<tr><td>beehiiv changed how it counts opens</td><td>Your own pixel (GA4 event email_open), in every OHI since Aug 5</td><td>It follows beehiiv's opens at a steady {DP["pixel"]["min_ratio"]:.2f} to {DP["pixel"]["max_ratio"]:.2f} across the break</td></tr>
<tr><td>Dropping the "One Helpful Idea:" subject prefix (Sep 28 to Oct 13)</td><td>Gmail ratio with and without it</td><td>{sep28["ratio"]:.2f}, {by_date(OHI, "2026-10-05")["ratio"]:.2f}, {by_date(OHI, "2026-10-13")["ratio"]:.2f} without; {sep21["ratio"]:.2f} before and {oct20["ratio"]:.2f} after with it. No visible effect</td></tr>
<tr><td>Apple Mail Privacy Protection</td><td>iCloud addresses</td><td>iCloud swings between 8% and 89% from send to send, but it is about 2% of the audience and it went up on Aug 25, when Gmail went down</td></tr>
</table></div>

<h2>6. What does not add up yet</h2>
<ul>
<li><b>The segments have been edited and I cannot see the history.</b> The Oct 20 send targeted "OHI Audience - Engaged Subs" and reached {oct20["recipients"]:,} people, but that segment today is defined as an open rate of 30% or more and holds about 161k. "OHI Audience - All Subscribers" reached 358,641 on Oct 13 and holds about 660k today. I worked from recipient counts, not segment names.</li>
<li><b>Two halves of the same email get very different results.</b> On Oct 8 the half sent first opened at {pct(SPLIT_OCT8[0], 1)} and the half sent 71 minutes later at {pct(SPLIT_OCT8[1], 1)}. On Nov 5 the first half is at {pct(nov5[0]["open_rate"], 1)} and the second at {pct(nov5[1]["open_rate"], 1)}; the gap is all Gmail ({pct(nov5[0]["gmail_rate"], 1)} against {pct(nov5[1]["gmail_rate"], 1)}) while the other providers lean the opposite way ({pct(nov5[0]["control_rate"], 1)} against {pct(nov5[1]["control_rate"], 1)}). Nov 5 has under a day of data. If the halves are random, Gmail is making different bulk decisions about identical emails, which is filtering and not reader behaviour. It also means the rating-box order test those variants were built for is confounded.</li>
<li><b>OHI does somewhat worse at Gmail than the main newsletter from the same domain.</b> Gmail opened the main newsletter at {pct(MAIN_NEWSLETTER_GMAIL["2026-08-20"], 1)} on Aug 20 and {pct(MAIN_NEWSLETTER_GMAIL["2026-09-18"], 1)} on Sep 18; OHI got {pct(aug25["gmail_rate"], 1)} on Aug 25 and {pct(sep21["gmail_rate"], 1)} on Sep 21. One known difference: since Aug 5 every OHI email carries your second tracking pixel on a vercel.app address and the main newsletter does not. That is a hypothesis, not a finding (see the fourth idea below).</li>
<li><b>An early step in March.</b> Between Feb 3 and Mar 10, after three whole-list sends in a row, Gmail went from {pct(feb3["gmail_rate"], 1)} to {pct(mar10["gmail_rate"], 1)} on the engaged audience while the others stayed at {pct(feb3["control_rate"], 1)} and {pct(mar10["control_rate"], 1)}. Same mechanism, smaller scale.</li>
<li><b>beehiiv's spam-report counts say nothing about Gmail.</b> Gmail does not pass individual complaints back to senders, so the low counts on these sends (9 to 26 per send) come from the other providers.</li>
<li><b>No OHI has gone out since Oct 20</b> (as of Nov 6), so there is no reading yet on the current, stricter segment.</li>
</ul>

<h2>7. What I would do, in order</h2>
{ideas()}

<h2>Method and data</h2>
<p>Rates are unique opens divided by delivered. Totals per send come from the beehiiv API; the per-provider rows come from beehiiv's deliverability breakdown and cover the six largest providers. "Other providers" is Yahoo, Hotmail, Outlook and AOL pooled (about 13k to 23k recipients per engaged send); iCloud is excluded because Apple's privacy feature makes its open rate meaningless. A send counts as "whole list" at {DP["whole_list_min"]:,} recipients or more; the other providers' open rate confirms the two groups are cleanly apart (25% to 31% against 46% to 67%). The "October if Gmail had kept its usual gap" figure multiplies each October send's other-provider open rate by the median pre-break ratio ({C["baseline_ratio"]:.2f}) and leaves everything else as observed; this assumes a wider audience would dilute Gmail and the other providers in the same proportion. The split of the {100 * total_drop:.0f}-point fall into {100 * drift:.0f}, {100 * wider:.1f} and {100 * gmail_part:.0f} points follows from those definitions. Source, data and tests: <code>reports/ohi_open_rate_drop_2026-11-06_src/</code> and <code>tests/test_ohi_open_rate_drop.py</code>.</p>
<details><summary>Every OHI send of 2026</summary><div class="scroll"><table>
<tr><th>Sent</th><th>Subject</th><th>Audience</th><th class="n">Recipients</th><th class="n">Open rate</th><th class="n">Gmail</th><th class="n">Other providers</th><th class="n">Gmail / others, opens</th><th class="n">Gmail / others, clicks</th></tr>{data_rows}</table></div></details>
<details><summary>Monthly mail volume from ohi.clearerthinking.net</summary><div class="scroll"><table>
<tr><th>Month</th><th class="n">Sends</th><th class="n">Delivered</th><th class="n">Of which in sends under 15% opens</th><th class="n">Open rate</th></tr>{month_rows}</table></div></details>
"""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>OHI open rate drop</title><style>{CSS}</style></head><body><main>{body}</main><div id="tip" role="status"></div><script>{JS}</script></body></html>')


def main() -> None:
    page = build()
    assert "—" not in page, "no em dashes (Igor's rule)"
    OUT.write_text(page, encoding="utf-8")
    print("wrote", OUT, f"({len(page) / 1024:.0f} KB)")
    if "--open" in sys.argv:
        subprocess.run(["open", "-a", "Google Chrome", str(OUT)], check=False)


if __name__ == "__main__":
    main()
