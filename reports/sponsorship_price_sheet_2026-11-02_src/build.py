"""Render the sponsorship price sheet as HTML (reports/) and an A4 PDF (~/Downloads) from datapoints.json.

    .venv/bin/python reports/sponsorship_price_sheet_2026-11-02_src/fetch_newsletter_stats.py   # refresh beehiiv numbers
    .venv/bin/python reports/sponsorship_price_sheet_2026-11-02_src/build.py

Every number on the sheet comes from datapoints.json (hand-entered blocks carry their source) or is derived
from it here through pricing.py. Styling, logo and the Chrome print pipeline are the personas report's; the
"who reads" bullets are the sponsor audience page's own summary, so the two documents cannot drift.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import pricing as pz  # noqa: E402

HTML_OUT = ROOT / "reports" / "sponsorship_price_sheet_2026-11-02.html"
PDF_OUT = Path.home() / "Downloads" / "Clearer Thinking sponsorship price sheet 2026-11-02.pdf"
DP = json.loads((HERE / "datapoints.json").read_text())


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pr = load("personas_report", ROOT / "reports" / "ct_audience_personas_2026-09-25_src" / "build_report.py")
esc = pr.esc
money, num = pz.fmt_money, pz.fmt_int


# --------------------------------------------------------------------------- derived numbers
def unit_reach() -> dict:
    """Planning impressions per placement: newsletter median unique opens, podcast and YouTube planning figures."""
    return {"newsletter": DP["newsletter"]["stats"]["median"],
            "podcast": DP["podcast"]["planning_downloads"],
            "youtube": DP["youtube"]["planning_views"]}


def unit_range() -> dict:
    """Low/high planning impressions per placement (newsletter: middle half of editions)."""
    s = DP["newsletter"]["stats"]
    return {"newsletter": (s["p25"], s["p75"]),
            "podcast": (DP["podcast"]["planning_downloads"],) * 2,
            "youtube": (DP["youtube"]["planning_views"],) * 2}


def package_rows() -> list[dict]:
    p = DP["pricing"]
    reach, rng = unit_reach(), unit_range()
    out = []
    for pk in DP["packages"]:
        imp = pz.package_reach(reach, pk["counts"])
        lo = pz.package_reach({k: v[0] for k, v in rng.items()}, pk["counts"])
        hi = pz.package_reach({k: v[1] for k, v in rng.items()}, pk["counts"])
        typical = pz.cost(imp, p["cpm"], p["cost_step"])
        out.append({**pk, "impressions": imp, "cost": typical,
                    "cost_lo": pz.cost(lo, p["cpm"], p["cost_step"]), "cost_hi": pz.cost(hi, p["cpm"], p["cost_step"]),
                    "cap": pz.suggested_cap(typical, p["cap_headroom"], p["cap_step"])})
    return out


def youtube_stats() -> dict:
    vids = DP["youtube"]["recent_videos"]
    full = [v["views"] for v in vids if v["type"] == "full"]
    return {"all": pz.summarize(v["views"] for v in vids), "full": pz.summarize(full), "n_clips": len(vids) - len(full)}


def audience() -> tuple[list[str], str]:
    """The sponsor audience page's own 'In short' bullets plus the share of engaged readers in the US, Canada
    and the UK. Returns ([html bullets], note). Falls back to nothing if that report cannot be imported."""
    try:
        bp = load("audience_page", ROOT / "reports" / "ct_sponsor_audience_report_2026-10-06_src" / "build_page.py")
        c = bp.content()
        where = next(s for s in c["sections"] if s["title"] == "Where they are")
        country = where["rows"][0][0][0]
        share = sum(r["pct"] for r in country["rows"] if r["label"] in ("United States", "Canada", "United Kingdom"))
        bullets = list(c["summary"])
        bullets.append(f"{share:.0f}% of engaged newsletter readers are in the United States, Canada or the United Kingdom "
                       f"(engaged web sessions from newsletter links, Google Analytics, n = {country['n']:,}).")
        return bullets, c["meta"]
    except Exception as e:  # pragma: no cover - depends on the other report's files
        return [], f"audience breakdown unavailable: {e}"


# --------------------------------------------------------------------------- html pieces
def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def h2(text: str, sub: str = "") -> str:
    return f'<div class="h2">{esc(text)}</div>' + (f'<p class="sub">{sub}</p>' if sub else "")


def placements_table() -> str:
    nl, s = DP["newsletter"], DP["newsletter"]["stats"]
    pl, cpm, step = DP["placements"], DP["pricing"]["cpm"], DP["pricing"]["cost_step"]
    yt, ys = DP["youtube"], youtube_stats()
    reach = unit_reach()
    rows = [
        [f'<b>{esc(pl["newsletter"]["name"])}</b><div class="small">{esc(pl["newsletter"]["format"])}</div>',
         f'<b>{num(s["median"])}</b> unique opens<div class="small">Median of {s["n"]} editions, '
         f'{month_name(nl["window"]["since"])} to {month_name(nl["window"]["until"])} 2026. Middle half {num(s["p25"])} to '
         f'{num(s["p75"])}; lowest {num(s["min"])}, highest {num(s["max"])}.</div>',
         f'<b>{money(pz.cost(reach["newsletter"], cpm, step))}</b><div class="small">Middle half {money(pz.cost(s["p25"], cpm, step))} '
         f'to {money(pz.cost(s["p75"], cpm, step))}</div>',
         esc(DP["measurement"]["newsletter"])],
        [f'<b>{esc(pl["podcast"]["name"])}</b><div class="small">{esc(pl["podcast"]["format"])}</div>',
         f'<b>{num(reach["podcast"])}</b> downloads<div class="small">Planning figure per episode, from the show\'s hosting dashboard.</div>',
         f'<b>{money(pz.cost(reach["podcast"], cpm, step))}</b>',
         esc(DP["measurement"]["podcast"])],
        [f'<b>{esc(pl["youtube"]["name"])}</b><div class="small">{esc(pl["youtube"]["format"])}</div>',
         f'<b>{num(reach["youtube"])}</b> views<div class="small">Planning figure. The {ys["full"]["n"]} full-length videos '
         f'published July to October 2026 have a median of {num(ys["full"]["median"])} views (range {num(ys["full"]["min"])} to '
         f'{num(ys["full"]["max"])}); one June 2026 video reached {yt["outlier"]["views"]/1e6:.1f}M.</div>',
         f'<b>{money(pz.cost(reach["youtube"], cpm, step))}</b>',
         esc(DP["measurement"]["youtube"])],
    ]
    return table(["Placement", "Typical reach", f"Typical cost at ${cpm} CPM", "How it is measured"], rows, "price")


def packages_table() -> str:
    rows = []
    for pk in package_rows():
        rng = "" if pk["cost_lo"] == pk["cost_hi"] else f'<div class="small">Typical range {money(pk["cost_lo"])} to {money(pk["cost_hi"])}</div>'
        rows.append([f'<b>{esc(pk["name"])}</b><div class="small">{esc(pk["what"])}</div>',
                     f'<b>{num(pk["impressions"])}</b>', f'<b>{money(pk["cost"])}</b>{rng}', money(pk["cap"])])
    return table(["Package", "Typical impressions", "Typical cost", "Suggested cap"], rows, "pkg")


def month_name(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%B")


def newsletter_months_table() -> str:
    rows = [[dt.date.fromisoformat(m["month"] + "-01").strftime("%B %Y"), str(m["n"]), num(m["median"]), num(m["min"]), num(m["max"])]
            for m in DP["newsletter"]["by_month"]]
    return table(["Month", "Editions", "Median opens", "Lowest", "Highest"], rows, "months")


def youtube_table() -> str:
    vids = DP["youtube"]["recent_videos"]
    rows = [[dt.date.fromisoformat(v["date"]).strftime("%b %-d"), esc(v["title"]), num(v["views"])]
            for v in vids if v["type"] == "full"]
    clips = [v for v in vids if v["type"] == "clip"]
    note = ""
    if clips:
        lo, hi = min(c["views"] for c in clips), max(c["views"] for c in clips)
        d0, d1 = min(c["date"] for c in clips), max(c["date"] for c in clips)
        note = (f'<p class="small">Not listed: {len(clips)} short clips published {dt.date.fromisoformat(d0).strftime("%b %-d")} to '
                f'{dt.date.fromisoformat(d1).strftime("%b %-d")}, {num(lo)} to {num(hi)} views each. A sponsor read goes in a full-length video.</p>')
    return table(["Published", "Video", "Views"], rows, "videos") + note


def availability_table() -> str:
    rows = []
    for w in DP["availability"]["weeks"]:
        label = w.get("label") or "Week of " + dt.date.fromisoformat(w["week_of"]).strftime("%b %-d")
        status = ('<span class="sw" style="background:var(--green)"></span>Open' if w["status"] == "open"
                  else '<span class="sw" style="background:var(--light)"></span>Booked')
        rows.append([label, status, esc(w["channels"])])
    return table(["Week", "Status", ""], rows, "weeks")


def build_html(stamp: str) -> str:
    m, nl, p = DP["meta"], DP["newsletter"], DP["pricing"]
    s, reach, ys = nl["stats"], unit_reach(), youtube_stats()
    aud_bullets, _ = audience()
    header = (f'<img class="logo" src="data:image/png;base64,{pr.logo_b64()}" alt="Clearer Thinking">'
              f'<h1>{esc(m["title"])}</h1>'
              f'<div class="meta">{esc(m["season"])} · Prepared {stamp} · {esc(m["contact"])}</div>')
    how = pr.callout("How it works", "<ul>" + "".join(f"<li>{b}</li>" for b in DP["how_it_works"]) + "</ul>")
    tiles = pr.tiles([
        (num(nl["active_subscriptions"]), "active newsletter subscribers (beehiiv, " + nl["fetched"] + ")"),
        (num(s["median"]), f"median unique opens per edition ({s['n']} editions, Jul to Oct 2026)"),
        (num(reach["podcast"]), "downloads per podcast episode (planning figure)"),
        (num(reach["youtube"]), f"views per video (planning figure; recent median {num(ys['full']['median'])})"),
    ])
    page1 = (header + how + tiles
             + h2("Placements", "Three places your message can appear. Reach is what a typical placement has been getting; cost follows from it at "
                  f"${p['cpm']} per 1,000.")
             + placements_table())
    packages = (h2("Packages", "The usual way to buy: one sponsor owns the whole week. Costs are typical values at "
                   f"${p['cpm']} CPM; the cap is what we suggest you set (about {int(p['cap_headroom']*100)}% headroom, rounded up).")
                + packages_table())
    pod = DP["podcast"]
    reach_detail = (h2("Where the reach numbers come from")
                    + pr.grid(
                        f'<div class="h3">Newsletter: unique opens per edition</div>'
                        f'<p class="small">Source: beehiiv, fetched {nl["fetched"]}. Every regular edition (an article or One Helpful Idea sent to '
                        f'200,000+ readers) from {nl["window"]["since"]} to {nl["window"]["until"]}; a send split by segment counts as one edition. '
                        f'About {nl["editions_per_week"]:.1f} editions a week.</p>' + newsletter_months_table()
                        + f'<div class="h3">Podcast</div><p class="small">{pod["planning_downloads"]:,} downloads per episode is the planning figure from the '
                        f'show\'s hosting dashboard, used in all our 2026 proposals. {pod["episodes_total"]} episodes since 2020, '
                        f'{pod["episodes_2026_jan_oct"]} of them January to October 2026 (RSS feed, {pod["rss_checked"]}). {esc(pod["public_note"])}</p>',
                        f'<div class="h3">YouTube: views per upload</div>'
                        f'<p class="small">{esc(DP["youtube"]["channel"])}: {num(DP["youtube"]["subscribers"])} subscribers, {DP["youtube"]["videos"]} videos, '
                        f'{DP["youtube"]["lifetime_views"]/1e6:.1f}M lifetime views ({esc(DP["youtube"]["stats_source"])}, {DP["youtube"]["stats_date"]}). '
                        f'{esc(DP["youtube"]["window"])}. Median of the {ys["full"]["n"]} full-length videos {num(ys["full"]["median"])}; '
                        f'with the clips, {num(ys["all"]["median"])}.</p>'
                        + youtube_table()))
    avail = (h2("Availability", f'As of {DP["availability"]["as_of"]}. {esc(DP["availability"]["note"])} First come, first served.')
             + availability_table())
    process = h2("How a sponsorship runs") + "<ol class=\"steps\">" + "".join(f"<li>{b}</li>" for b in DP["process"]) + "</ol>"
    who = (pr.callout("Who reads Clearer Thinking", "<ul>" + "".join(f"<li>{b}</li>" for b in aud_bullets) + "</ul>"
                      + '<p class="small" style="margin-top:2mm">From the March 2026 reader survey, the Paths quiz and Google Analytics. The full audience breakdown is available on request.</p>', "#233b47")
           if aud_bullets else "")
    fine = '<div class="fine"><b>Fine print.</b> ' + " ".join(esc(x) for x in DP["fine_print"]) + "</div>"
    page2 = packages + process + avail
    page3 = reach_detail + who + fine
    body = "".join(f'<div class="page">{pg}</div>' for pg in (page1, page2, page3))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Clearer Thinking {esc(m["title"].lower())}</title>
<style>{pr.CSS}{EXTRA_CSS}</style></head>
<body>{body}</body></html>"""


EXTRA_CSS = """
.logo{height:6.5mm;width:auto;margin:0 0 6mm;display:block}
h1{font-size:22pt;line-height:1.1;color:var(--navy);margin:0 0 1.5mm;font-weight:700;letter-spacing:-.01em}
.meta{font-size:9pt;color:var(--muted);margin:0 0 5mm}
.callout li{margin-bottom:1.2mm}
.h2{margin-top:4mm}
.h2:first-child{margin-top:0}
.small{font-size:7.8pt;color:var(--muted);line-height:1.35;margin-top:.8mm}
.it{font-style:italic;color:var(--muted)}
table.price td:nth-child(1){width:52mm}
table.price td:nth-child(2){width:50mm}
table.price td:nth-child(3){width:32mm}
table.pkg td:nth-child(1){width:88mm}
table.pkg td:nth-child(2),table.pkg td:nth-child(3){width:30mm}
table.months td,table.weeks td{padding:1.3mm 2.5mm 1.3mm 0;font-size:8.2pt}
table.videos td{padding:.8mm 2.5mm .8mm 0;font-size:8pt}
table.months td:not(:first-child){text-align:right;font-variant-numeric:tabular-nums}
table.months th:not(:first-child){text-align:right}
table.videos td:first-child{width:14mm;white-space:nowrap;color:var(--muted)}
table.videos td:last-child{text-align:right;font-variant-numeric:tabular-nums;width:16mm}
table.videos th:last-child{text-align:right}
table.weeks td:first-child{width:34mm;white-space:nowrap}
table.weeks td:nth-child(2){width:22mm;white-space:nowrap}
ol.steps{margin:0 0 5mm;padding-left:5mm}
ol.steps li{margin:0 0 1.8mm;font-size:9.2pt}
.fine{font-size:7.8pt;color:var(--muted);line-height:1.4;border-top:1px solid var(--line);padding-top:3mm;margin-top:2mm}
.tile .v{font-size:15pt}
"""


def main() -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")
    HTML_OUT.write_text(build_html(stamp))
    pr.render_pdf(HTML_OUT, PDF_OUT, stamp, footer_label="Sponsorship price sheet")
    for pk in package_rows():
        print(f'{pk["name"]}: {pk["impressions"]:,} impressions -> {money(pk["cost"])} (range {money(pk["cost_lo"])} to {money(pk["cost_hi"])}), cap {money(pk["cap"])}')
    print(f"html: {HTML_OUT}\npdf:  {PDF_OUT}")


if __name__ == "__main__":
    main()
