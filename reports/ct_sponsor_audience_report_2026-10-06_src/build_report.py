"""Build the sponsor-facing audience report (HTML in reports/, PDF in ~/Downloads).

    .venv/bin/python reports/ct_sponsor_audience_report_2026-10-06_src/build_report.py

Reads datapoints.json next to this script (written by analysis.py from the fresh beehiiv and
GA4 pulls in data/) and the survey / Paths figures from
reports/ct_audience_personas_2026-09-25_src/datapoints.json, which stays their single source.
Chart helpers, CSS and the PDF printer are reused from that report's build_report.py.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PERSONAS_SRC = ROOT / "reports" / "ct_audience_personas_2026-09-25_src" / "build_report.py"
HTML_OUT = ROOT / "reports" / "ct_sponsor_audience_report_2026-10-06.html"
PDF_OUT = Path.home() / "Downloads" / "Clearer Thinking audience for sponsors 2026-10-06.pdf"

_spec = importlib.util.spec_from_file_location("personas_report", PERSONAS_SRC)
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)
esc, pct, bars, tiles, callout, ul, h2, h3, grid = pr.esc, pr.pct, pr.bars, pr.tiles, pr.callout, pr.ul, pr.h2, pr.h3, pr.grid

DP = json.loads((HERE / "datapoints.json").read_text())
SURVEY = pr.DATA["survey_2026_03"]
PATHS = pr.DATA["paths"]
CAREER = pr.DATA["career_2026_09"]

BLUE, ORANGE, GREY_MARK = "#0885f8", "#f8911b", "#c9ced3"
CPM = 25  # the per-1,000-unique-opens price quoted in the outreach email; used only for the cost-per-click line
# Past sponsors are described, not named, unless they have agreed to be named. Flip to False to name them.
ANONYMIZE = True
ANON = {
    "80,000 Hours": "Sponsor A (a careers organization in the effective altruism space)",
    "Game Over (The School of Thought)": "Sponsor B (a Kickstarter campaign for a game about AI risk)",
}
EA_LABEL_SURVEY = "Effective Altruist (or aspiring)"
IMPACT_SURVEY = "Have a greater positive impact on the world"
IMPACT_PATHS = "Greater positive impact on the world"


# --------------------------------------------------------------------------- helpers
def fmt_pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%"


def share(rows: list, label: str, n: int) -> float:
    return dict(rows)[label] / n


def month_name(d: str) -> str:
    return dt.date.fromisoformat(d).strftime("%b")


def opens_columns(editions: list[dict], median: int, title: str) -> str:
    """Column chart of unique opens per full-list edition; regular editions in blue, tool
    announcements in grey (they are shown for honesty, not counted). Only the highest and
    lowest regular edition carry a value; a hairline marks the median."""
    mx = max(e["unique_opens"] for e in editions)
    regular = [e for e in editions if e["kind"] in ("main", "ohi")]
    hi = max(regular, key=lambda e: e["unique_opens"])
    lo = min(regular, key=lambda e: e["unique_opens"])
    cols, axis, seen_months = [], [], set()
    for i, e in enumerate(editions):
        h = e["unique_opens"] / mx * 100  # of the plot height: bars and the median line share one scale
        color = BLUE if e["kind"] in ("main", "ohi") else GREY_MARK
        # the first and last labels hug the plot edge: Chrome's print clips anything that spills into the page margin
        edge = " first" if i == 0 else " last" if i == len(editions) - 1 else ""
        val = f'<div class="ocv{edge}">{e["unique_opens"] / 1000:.0f}k</div>' if e in (hi, lo) else ""
        cols.append(f'<div class="ocol" style="height:{h:.1f}%;background:{color}">{val}</div>')
        m = month_name(e["date"])
        axis.append(f'<div class="ocl">{"" if m in seen_months else m}</div>')
        seen_months.add(m)
    med_pct = median / mx * 100
    return (f'<div class="chart avoid"><div class="ch">{esc(title)}<span class="n">{len(regular)} regular editions, '
            f'{len(editions) - len(regular)} tool announcements</span></div>'
            f'<div class="oplot"><div class="omed" style="bottom:{med_pct:.1f}%"><span>median {median:,}</span></div>'
            f'<div class="ocols">{"".join(cols)}</div></div><div class="oaxis">{"".join(axis)}</div>'
            f'<div class="legend"><span><i class="sw" style="background:{BLUE}"></i>Regular edition (main newsletter or One Helpful Idea)</span>'
            f'<span><i class="sw" style="background:{GREY_MARK}"></i>Tool announcement, not counted in the figures</span></div></div>')


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def sponsor_name(s: str) -> str:
    return ANON.get(s, s) if ANONYMIZE else s


def ul_html(items: list[str]) -> str:
    """Bullet list whose items already contain markup (pr.ul escapes its items)."""
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def country_block() -> str:
    c = DP["country"]
    chart = bars(f"Visits to our website from newsletter links, by country (last {c['window_days']} days)",
                 [(r["country"], r["sessions"]) for r in c["rows"]], n=c["total_sessions"])
    top3 = ", ".join(r["country"] for r in c["rows"][:3])
    text = (f"<p><b>{fmt_pct(c['anglosphere_share'])} of visits come from the US, UK, Canada, Australia, Ireland or New "
            f"Zealand</b>; {top3} lead. These are Google Analytics sessions whose source is a newsletter link, over the last "
            f"{c['window_days']} days. We use them as a proxy for where readers live because the email platform does not "
            f"record subscriber country. Readers who open but never click are not represented, and a few countries block "
            f"or strip analytics more than others, so read the shares as approximate.</p>")
    return grid(chart, text)


# --------------------------------------------------------------------------- pages
def cover(stamp: str) -> str:
    s = DP["stats_recent"]["regular"]
    ea_survey = share(SURVEY["identities"]["rows"], EA_LABEL_SURVEY, SURVEY["identities"]["n"])
    ea_paths = share(PATHS["identities"]["rows"], EA_LABEL_SURVEY, PATHS["identities"]["n"])
    anglo = DP["country"]["anglosphere_share"]
    w = DP["window"]
    t = tiles([
        (f"{s['median_unique_opens']:,}", f"unique opens per regular edition (median of {s['n']}, Jul to Oct 2026)"),
        (f"{s['median_recipients']:,}", "recipients per edition (median)"),
        (f"{DP['regular_editions_per_week']:.1f}", "regular editions a week (main newsletter + One Helpful Idea)"),
        (f"{round(ea_paths * 100)} to {round(ea_survey * 100)}%", "of surveyed readers identify as effective altruists, aspiring included"),
        (f"{anglo * 100:.0f}%", "of newsletter web visits come from the US, UK, Canada, Australia, Ireland or New Zealand"),
    ])
    return f"""
<div class="cover page">
  <img class="logo" src="data:image/png;base64,{pr.logo_b64()}" alt="Clearer Thinking">
  <div class="eyebrow">Clearer Thinking · For prospective sponsors</div>
  <h1>Who reads Clearer Thinking</h1>
  <div class="subtitle">Reach, engagement and audience profile of the newsletter</div>
  <div class="stamp">Data as of {stamp}</div>
  <p class="lead">Clearer Thinking publishes free interactive tools and a free email newsletter on decision-making, psychology and thinking clearly. This document gives a prospective sponsor the numbers behind the audience: how many people a newsletter edition reaches, how engaged they are, what sponsor links have done so far, and who the readers are. Every figure names its source and sample size, and section 4 lists what the numbers do not capture.</p>
  {t}
  <div class="toc">
    <div class="t">Contents</div>
    <div class="row"><span class="k">1</span><span>Reach and engagement, {month_name(w['start'])} to {month_name(w['end'])} 2026</span></div>
    <div class="row"><span class="k">2</span><span>What sponsor links have done so far</span></div>
    <div class="row"><span class="k">3</span><span>Who the readers are</span></div>
    <div class="row"><span class="k">4</span><span>How the numbers are measured, and their limits</span></div>
    <div class="row"><span class="k">A</span><span>Appendix: every full-list edition since July 2026</span></div>
  </div>
  <div class="foot">Sources: beehiiv send statistics for every edition since 1 July 2026 (pulled {DP['pulled'][:10]}); Google Analytics 4, visits from newsletter links, last {DP['country']['window_days']} days; Clearer Thinking audience survey, March 2026 (539 respondents, 132 to 181 per question); Clearer Thinking Paths quiz, Jul 2023 to Jul 2026 (7,889 assessment-takers); Career Navigation Survey, Sep 2026 (113 to 143 respondents).</div>
</div>"""


def section1() -> str:
    s = DP["stats_recent"]
    reg, main, ohi = s["regular"], s["main"], s["ohi"]
    ytd = DP["stats_ytd"]["regular"]
    eng = DP["engaged"]
    w = DP["window"]
    chart = opens_columns(DP["editions_recent"], reg["median_unique_opens"],
                          f"Unique opens per full-list edition, {w['start']} to {w['end']}")
    rows = []
    for label, st_ in (("Main newsletter", main), ("One Helpful Idea", ohi), ("All regular editions", reg)):
        rows.append([f"<b>{label}</b>", str(st_["n"]), f"{st_['median_recipients']:,}", f"{st_['median_unique_opens']:,}",
                     f"{st_['min_unique_opens']:,} to {st_['max_unique_opens']:,}", fmt_pct(st_["median_open_rate"]),
                     f"{st_['median_verified_clicks']:,}", fmt_pct(st_["median_click_to_open"], 1)])
    rows.append([f"<span class='it'>Regular editions, 2026 to date</span>", str(ytd["n"]), f"{ytd['median_recipients']:,}",
                 f"{ytd['median_unique_opens']:,}", f"{ytd['min_unique_opens']:,} to {ytd['max_unique_opens']:,}",
                 fmt_pct(ytd["median_open_rate"]), f"{ytd['median_verified_clicks']:,}", fmt_pct(ytd["median_click_to_open"], 1)])
    tbl = table(["Edition type", "Editions", "Recipients (median)", "Unique opens (median)", "Unique opens (range)",
                 "Open rate (median)", "Verified clicks (median)", "Clicks per open"], rows, "stats")
    engaged_txt = (f"<p><b>{eng['count']:,} subscribers open more than 40% of the emails they receive</b> "
                   f"(beehiiv segment, calculated {eng['calculated']}). That is the core readership a sponsor message "
                   f"reaches repeatedly; the unique-open counts above are a single edition's reach.</p>")
    return f"""
<div class="page">
  {h2("1", f"Reach and engagement, {month_name(w['start'])} to {month_name(w['end'])} 2026",
      "We send two regular editions a week: the main newsletter (an article, often with a new tool) and the shorter One Helpful Idea. Each goes to the full list. The figures below count unique opens, the number of distinct subscribers who opened an edition at least once.")}
  {chart}
  {h3("By edition type")}
  {tbl}
  <p class="note">Recipients are addresses the edition was sent to. Unique opens and verified clicks are beehiiv's counts, verified clicks excluding automated link scanners. Clicks per open = verified clicks divided by unique opens. Tool announcements (three since July) are excluded from every row because they go to a different, less engaged slice of the list. The 2026-to-date row includes the spring, when editions were smaller but opened more.</p>
  {h3("Engaged readers")}
  {engaged_txt}
</div>"""


def section2() -> str:
    res = DP["sponsor_results"]
    rows = []
    for r in res:
        name = sponsor_name(r["sponsor"])
        per_link = f" (summed over {r['links']} links)" if r["links"] > 1 else ""
        rows.append([r["date"], f"<b>{esc(name)}</b><br><span class='it'>{esc(r['format'])}</span>", f"{r['unique_opens']:,}",
                     f"{r['unique_clicks']:,}{per_link}", f"{r['clicks_per_1000_opens']:.1f}",
                     f"${CPM * r['unique_opens'] / 1000 / r['unique_clicks']:.2f}" if r["unique_clicks"] else "n/a"])
    tbl = table(["Edition", "Sponsor and format", "Unique opens", "Unique clicks to the sponsor", "Clicks per 1,000 opens",
                 f"Cost per click at ${CPM} CPM"], rows, "sponsor")
    spots = [r for r in res if r["format"].startswith("Sponsor spot")]
    lo, hi = min(spots, key=lambda r: r["clicks_per_1000_opens"]), max(spots, key=lambda r: r["clicks_per_1000_opens"])
    ded = [r for r in res if not r["format"].startswith("Sponsor spot")]
    body = (f"<p>Across the {len(spots)} sponsor spots inside regular editions, between {lo['clicks_per_1000_opens']:.1f} and "
            f"{hi['clicks_per_1000_opens']:.1f} readers per 1,000 unique opens clicked through to the sponsor. "
            + (f"The one dedicated edition, written around the sponsor's own material, reached {ded[0]['clicks_per_1000_opens']:.0f} per 1,000. "
               if ded else "")
            + f"The last column converts each placement into a cost per click at the ${CPM} per 1,000 unique opens offered in our email, "
              "so you can compare it with your other channels. Four placements are too few to call a benchmark: results depend on the "
              "copy, the offer and the edition's topic.</p>")
    return f"""
<div class="page">
  {h2("2", "What sponsor links have done so far",
      "Every sponsor placement we can identify in our 2026 send data, with the clicks its links received. Sponsors are described rather than named because we have not asked their permission to share their results.")}
  {tbl}
  {callout("Reading the table", body)}
  <p class="note">Unique clicks are beehiiv's per-link counts of distinct subscribers who clicked, with automated scanners removed. Where a placement contained several links, the per-link counts are summed, so a reader who clicked two links counts twice. Unique opens are for the whole edition, including the sender-domain split halves.</p>
</div>"""


def section3() -> str:
    sv, pa = SURVEY, PATHS
    ident_sv = bars("Which of these describe you? (audience survey)", sv["identities"]["rows"][:10], n=sv["identities"]["n"],
                    highlight=(EA_LABEL_SURVEY,), note="Multi-select. Share of respondents who ticked each identity.")
    ident_pa = bars("Which of these describe you? (Paths quiz)", pa["identities"]["rows"][:10], n=pa["identities"]["n"],
                    highlight=(EA_LABEL_SURVEY,), note="Multi-select, asked of everyone who completed the quiz's assessment, Jul 2023 to Jul 2026.")
    alt = next(cat for cat in pa["goal_categories"] if cat[0] == "Altruistic")[1]
    goals_sv = bars("Goals for the next year (audience survey, top 8)", sv["goals"]["rows"][:8], n=sv["goals"]["n"],
                    highlight=(IMPACT_SURVEY,), note="Multi-select.")
    goals_pa = bars("Altruistic goals picked in the Paths quiz", alt, n=pa["goals"]["n"], highlight=(IMPACT_PATHS,),
                    note="Multi-select from a list of 21 goals; the three altruistic ones shown.")
    topics = bars("Topics readers want more of (audience survey, top 9)", sv["topics"]["rows"][:9], n=sv["topics"]["n"],
                  highlight=("How to improve the world",))
    concerns = bars("Issues readers say they are concerned about (top 8)", sv["concerns"]["rows"][:8], n=sv["concerns"]["n"])
    pol = sv["political"]
    pol_n = pol["progressive"] + pol["center"] + pol["conservative"]
    political = bars("Political self-placement (audience survey)",
                     [("Progressive (-5 to -1)", pol["progressive"]), ("Center (0)", pol["center"]), ("Conservative (+1 to +5)", pol["conservative"])],
                     n=pol_n, note="Self-placed on an 11-point scale.")
    employment = bars("Career stage (audience survey)", sv["employment"]["rows"], n=sv["employment"]["n"])
    industry = bars("Industry (audience survey, top 8)", sv["industry"]["rows"][:8], n=sv["industry"]["n"])
    edu = CAREER["education"]
    degree = sum(v for k, v in edu["rows"] if k in ("Bachelor's degree", "Master's degree", "Doctorate"))
    education = bars("Education (Career Navigation Survey, Sep 2026)", edu["rows"], n=edu["n"],
                     note=f"{pct(degree, edu['n'])} hold a bachelor's degree or higher. A smaller survey of readers planning a career change, so treat it as indicative.")
    comp = ", ".join(sv["comparables"][:6])
    ea_sv = share(sv["identities"]["rows"], EA_LABEL_SURVEY, sv["identities"]["n"])
    ea_pa = share(pa["identities"]["rows"], EA_LABEL_SURVEY, pa["identities"]["n"])
    imp_sv = share(sv["goals"]["rows"], IMPACT_SURVEY, sv["goals"]["n"])
    imp_pa = share(pa["goals"]["rows"], IMPACT_PATHS, pa["goals"]["n"])
    summary = callout("In short", (
        f"<p>Readers describe themselves first as lifelong learners and science enthusiasts. Between {ea_pa * 100:.0f}% (Paths quiz, "
        f"n = {pa['identities']['n']:,}) and {ea_sv * 100:.0f}% (survey, n = {sv['identities']['n']}) identify as effective altruists "
        f"or aspiring ones, about a third as rationalists, and {imp_sv * 100:.0f}% to {imp_pa * 100:.0f}% name having a greater positive "
        f"impact on the world as a personal goal. Asked which other publications Clearer Thinking resembles, they most often named "
        f"{esc(comp)}. Both samples are self-selected (people who answer surveys or complete a long quiz are the more engaged readers), "
        f"so the shares are best read as upper bounds for the list as a whole.</p>"))
    return f"""
<div class="page">
  {h2("3", "Who the readers are",
      "Two sources: the March 2026 audience survey (sent to the newsletter list; each question shows its own number of answers) and the Clearer Thinking Paths quiz, a self-improvement planning tool on our site that 7,889 people completed between July 2023 and July 2026.")}
  {summary}
  {h3("How they describe themselves")}
  {grid(ident_sv, ident_pa)}
  {h3("What they are trying to do")}
  {grid(goals_sv, goals_pa)}
</div>
<div class="page">
  {h3("What they want to read, and what worries them")}
  {grid(topics, concerns)}
  {h3("Background")}
  {grid(political, education)}
  {grid(employment, industry)}
  {h3("Where readers are")}
  {country_block()}
</div>"""


def section4() -> str:
    eng = DP["engaged"]
    items = [
        "<b>Unique opens</b> are beehiiv's count of distinct subscribers who opened an edition. They are the closest measurable thing to \"people who saw the message\", but not the same thing: some mail apps open emails automatically on the reader's behalf (Apple Mail's privacy feature is the largest case), and not everyone who opens reads down to a sponsor spot. We have not estimated the size of either effect.",
        "<b>Verified clicks</b> are beehiiv's per-link counts of distinct subscribers who clicked, after removing automated link scanners. They are the better measure of attention, which is why section 2 reports them.",
        f"<b>Engaged readers</b> ({eng['count']:,}) is a beehiiv segment of active subscribers whose lifetime open rate exceeds 40%, calculated {eng['calculated']}.",
        "<b>Country shares</b> come from Google Analytics visits whose source is a newsletter link, not from subscriber records. Readers who open but never click are not represented, and a few countries block or strip analytics more than others.",
        "<b>Survey and quiz shares</b> are from self-selected samples: 539 people opened the March 2026 survey and 132 to 181 answered each question; the Paths quiz is completed by people planning self-improvement, not a random slice of the list. Multi-select questions do not sum to 100%.",
        "<b>Recipients</b> is the number of addresses an edition went to. It is not a count of readers and we do not suggest using it to size a placement.",
        "<b>Podcast and YouTube</b> audiences are not covered here; their figures are in the separate channel description.",
    ]
    return f"""
<div class="page">
  {h2("4", "How the numbers are measured, and their limits",
      "What each figure in this document does and does not capture, so you can weigh it on your own terms.")}
  {ul_html(items)}
  {h3("What a sponsor receives after a placement")}
  <p>The edition's beehiiv statistics (recipients, unique opens, verified clicks on your link), shared as a screenshot or export at the agreed measurement date, so the invoice can be checked against the source.</p>
  {h3("Sources")}
  {ul([
      f"beehiiv send statistics for every confirmed email edition, pulled {DP['pulled'][:10]}. Posts that beehiiv stores separately for the same edition (sender-domain splits, segment splits, test sends) are merged by subject line within three days before counting.",
      f"Google Analytics 4, sessions with a newsletter source, last {DP['country']['window_days']} days ({DP['country']['total_sessions']:,} sessions).",
      "Clearer Thinking audience survey, March 2026. Clearer Thinking Paths quiz export, Jul 2023 to Jul 2026. Career Navigation Survey, Sep 2026 (GuidedTrack).",
  ])}
</div>"""


def appendix() -> str:
    rows = []
    kind_label = {"main": "Main newsletter", "ohi": "One Helpful Idea", "promo": "Tool announcement"}
    for e in DP["editions_recent"]:
        rows.append([e["date"], esc(e["subject"][:60]), kind_label[e["kind"]], f"{e['recipients']:,}", f"{e['unique_opens']:,}",
                     fmt_pct(e["open_rate"]), f"{e['unique_verified_clicks']:,}"])
    tbl = table(["Date", "Subject line", "Type", "Recipients", "Unique opens", "Open rate", "Verified clicks"], rows, "editions")
    return f"""
<div class="page">
  {h2("A", "Appendix: every full-list edition since July 2026",
      f"Editions sent to at least {DP['full_list_threshold']:,} addresses, in order. Tool announcements are listed for completeness and excluded from the section 1 figures.")}
  {tbl}
</div>"""


EXTRA_CSS = """
.stats td,.sponsor td,.editions td{font-variant-numeric:tabular-nums}
.stats td:first-child,.sponsor td:first-child,.editions td:first-child{white-space:nowrap}
.sponsor td:nth-child(2){min-width:52mm}
.editions{font-size:7.6pt}
.editions td{padding:1mm 2mm 1mm 0}
.it{font-style:italic;color:var(--muted)}
/* opens-per-edition columns: the plot box IS the scale (bars and median line are % of its height) */
.oplot{position:relative;height:40mm;margin:7mm 26mm 0 0}
.ocols{position:absolute;inset:0;display:flex;align-items:flex-end;gap:1.6mm}
.ocol{flex:1;max-width:6mm;position:relative;border-radius:2px 2px 0 0;min-height:1px}
.ocv{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);margin-bottom:.6mm;font-size:7pt;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.ocv.first{left:0;transform:none}
.ocv.last{left:auto;right:0;transform:none}
.oaxis{display:flex;gap:1.6mm;margin:1mm 26mm 0 0}
.ocl{flex:1;max-width:6mm;font-size:7pt;color:var(--muted);white-space:nowrap}
.omed{position:absolute;left:0;right:0;border-top:1px solid var(--navy);z-index:2}
.omed span{position:absolute;left:100%;top:-2mm;margin-left:1.5mm;font-size:7pt;color:var(--navy);white-space:nowrap}
.legend{display:flex;gap:6mm;font-size:7.6pt;color:var(--muted);margin-top:1.4mm}
.legend .sw{width:2.4mm;height:2.4mm;border-radius:1px;margin-right:1.4mm}
.cover .tiles{margin-top:2mm}
.cover .tile .v{font-size:15pt}
"""


def build_html(stamp: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Who reads Clearer Thinking: audience information for sponsors</title>
<style>{pr.CSS}{EXTRA_CSS}</style></head>
<body>
{cover(stamp)}
{section1()}
{section2()}
{section3()}
{section4()}
{appendix()}
</body></html>"""


def main() -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")
    HTML_OUT.write_text(build_html(stamp))
    pr.render_pdf(HTML_OUT, PDF_OUT, stamp, footer_label="Who reads Clearer Thinking")
    print(f"html: {HTML_OUT}\npdf:  {PDF_OUT}")


if __name__ == "__main__":
    main()
