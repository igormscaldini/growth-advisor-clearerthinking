"""Build the sponsor-facing audience page (index.html next to this script) in the style of the
published partner page at https://igormscaldini.github.io/ct-audience-profile/.

    .venv/bin/python reports/ct_sponsor_audience_report_2026-10-06_src/build_page.py

Inputs: ga4_datapoints.json (written by fetch_data.py) and the survey / Paths figures in
reports/ct_audience_personas_2026-09-25_src/datapoints.json (their single source). The page is a
single self-contained HTML file (Chart.js from cdnjs) so it can be pushed to GitHub Pages as is.
It describes who the audience is; it deliberately carries no send, campaign or performance numbers.
"""
from __future__ import annotations

import datetime as dt
import html
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GA4 = json.loads((HERE / "ga4_datapoints.json").read_text())
SRC = json.loads((ROOT / "reports" / "ct_audience_personas_2026-09-25_src" / "datapoints.json").read_text())
SURVEY, PATHS, CAREER = SRC["survey_2026_03"], SRC["paths"], SRC["career_2026_09"]
OUT = HERE / "index.html"

MAIN_HOST, TOOLS_HOST = "www.clearerthinking.org", "programs.clearerthinking.org"
EXCLUDE_MONTHS = ("202608",)  # the August 2026 viral wave: 1.1M one-off visitors in a single month
# Country buckets for the "Where they are" chart (GA4 country names). Anything else is "Other"
# (Australia, New Zealand, Latin America, Africa).
EUROPE = {
    "Germany", "France", "Netherlands", "Spain", "Ireland", "Italy", "Sweden", "Poland", "Switzerland", "Belgium",
    "Austria", "Denmark", "Norway", "Finland", "Portugal", "Czechia", "Greece", "Hungary", "Romania", "Ukraine", "Russia",
    "Croatia", "Slovakia", "Slovenia", "Bulgaria", "Serbia", "Lithuania", "Latvia", "Estonia", "Luxembourg", "Iceland",
    "Malta", "Bosnia & Herzegovina", "North Macedonia", "Albania", "Montenegro", "Moldova", "Belarus", "Kosovo", "Cyprus",
    "Andorra", "Monaco", "Liechtenstein", "San Marino", "Vatican City", "Gibraltar", "Isle of Man", "Jersey", "Guernsey",
    "Faroe Islands", "Åland Islands",
}
ASIA = {
    "India", "Singapore", "Philippines", "Japan", "China", "Hong Kong", "Taiwan", "South Korea", "Indonesia", "Malaysia",
    "Thailand", "Vietnam", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Israel", "United Arab Emirates", "Saudi Arabia",
    "Qatar", "Türkiye", "Turkey", "Iran", "Iraq", "Jordan", "Lebanon", "Kuwait", "Bahrain", "Oman", "Kazakhstan",
    "Uzbekistan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Cambodia", "Myanmar (Burma)", "Laos", "Mongolia", "Macao",
    "Bhutan", "Maldives", "Brunei", "Timor-Leste", "Afghanistan", "Armenia", "Azerbaijan", "Georgia", "Yemen", "Syria",
    "Palestine", "North Korea",
}
REGION_ORDER = ["United States", "Canada", "United Kingdom", "Europe", "Asia", "Other"]
LANGUAGES = ("English", "German", "Spanish")
EA = "Effective Altruist (or aspiring)"
BLUE, ORANGE, GREY = "#0885f8", "#f8911b", "#a6a6a6"


# --------------------------------------------------------------------------- pure helpers (tested)
def shares(rows: list, n: int) -> list[dict]:
    """[(label, count), ...] -> [{label, count, pct}], pct as a percentage of n."""
    return [{"label": lab, "count": c, "pct": c / n * 100} for lab, c in rows]


def demographic_shares(rows: list[dict], host: str, exclude_months: tuple = EXCLUDE_MONTHS, order: list | None = None) -> dict:
    """Known-value shares for one host, summing the monthly rows and dropping 'unknown'.

    Returns {"n": classified users, "rows": [{label, count, pct}, ...]} in `order` if given, else by size.
    """
    agg: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["host"] == host and r["month"] not in exclude_months and r["value"] != "unknown":
            agg[r["value"]] += r["users"]
    n = sum(agg.values())
    labels = order or sorted(agg, key=lambda k: -agg[k])
    return {"n": n, "rows": [{"label": k, "count": agg.get(k, 0), "pct": agg.get(k, 0) / n * 100 if n else 0.0} for k in labels]}


def engaged_shares(rows: list[dict], top: int | None = None, drop: tuple = ("(not set)", "(other)")) -> dict:
    """Share of engaged newsletter sessions per value (scanner traffic is mostly non-engaged)."""
    rows = [r for r in rows if r["value"] not in drop]
    n = sum(r["engaged_sessions"] for r in rows)
    out = [{"label": r["value"], "count": r["engaged_sessions"], "pct": r["engaged_sessions"] / n * 100 if n else 0.0} for r in rows]
    return {"n": n, "rows": out[:top] if top else out}


def region(country: str) -> str:
    if country in ("United States", "Canada", "United Kingdom"):
        return country
    if country in EUROPE:
        return "Europe"
    if country in ASIA:
        return "Asia"
    return "Other"


def language_bucket(language: str) -> str:
    return language if language in LANGUAGES else "Others"


def bucket_shares(rows: list[dict], bucket, order: list[str], drop: tuple = ("(not set)", "(other)")) -> dict:
    """Engaged newsletter sessions summed into buckets, listed in `order` (empty buckets omitted)."""
    agg: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["value"] not in drop:
            agg[bucket(r["value"])] += r["engaged_sessions"]
    n = sum(agg.values())
    return {"n": n, "rows": [{"label": k, "count": agg[k], "pct": agg[k] / n * 100 if n else 0.0} for k in order if k in agg]}


# --------------------------------------------------------------------------- html pieces
def esc(s: str) -> str:
    return html.escape(s, quote=False)


CHARTS: list[dict] = []  # collected chart specs, serialised into the page's script


def chart(s: dict) -> str:
    """A section with one horizontal bar chart, from a spec made by spec(). Collects the data for Chart.js."""
    h = len(s["rows"]) * 30 + 16
    CHARTS.append({"id": s["id"], "n": s["n"], "wrap": 48 if s["wide"] else 26, "labels": [r["label"] for r in s["rows"]],
                   "data": [round(r["pct"], 1) for r in s["rows"]], "counts": [r["count"] for r in s["rows"]]})
    return (f'<div class="section-title">{esc(s["title"])}' + (f' <span class="n">(n = {s["n"]:,})</span>' if s["n"] else "") + "</div>"
            + (f'<div class="question-wording">{esc(s["question"])}</div>' if s["question"] else "")
            + f'<div class="chart-wrap" style="height:{h}px"><canvas id="{s["id"]}"></canvas></div>'
            + (f'<div class="note">{s["note"]}</div>' if s["note"] else ""))


def two_col(a: str, b: str) -> str:
    return f'<div class="two-col"><div>{a}</div><div>{b}</div></div>'


def divider() -> str:
    return '<div class="divider"></div>'


def h2(text: str, sub: str = "") -> str:
    return f"<h2>{esc(text)}</h2>" + (f'<p class="section-lead">{sub}</p>' if sub else "")


def stat_row(items: list[tuple[str, str]]) -> str:
    return '<div class="stats">' + "".join(f'<div class="stat"><div class="v">{v}</div><div class="l">{esc(l)}</div></div>' for v, l in items) + "</div>"


# --------------------------------------------------------------------------- content, shared with build_pdf.py
TITLE = "Clearer Thinking audience breakdown"
META = "Every chart shows its own sample size. Data from analytics and surveys."


def spec(cid: str, title: str, n: int, rows: list[dict], question: str = "", note: str = "", wide: bool = False) -> dict:
    return {"id": cid, "title": title, "n": n, "rows": rows, "question": question, "note": note, "wide": wide}


def content() -> dict:
    """Everything on the page, numbers and wording, as one structure:
    {"title", "meta", "summary": [html bullets], "sections": [{"title", "lead", "rows": [[cell, cell] | [cell]]}]}
    where a cell is a list of chart specs stacked vertically. build() renders it as HTML with Chart.js and
    build_pdf.py renders the same structure as a PDF, so the wording lives here only."""
    sv, pa = SURVEY, PATHS
    ident_sv = shares(sv["identities"]["rows"], sv["identities"]["n"])
    ident_pa = shares(pa["identities"]["rows"], pa["identities"]["n"])
    goals_sv = shares(sv["goals"]["rows"][:12], sv["goals"]["n"])
    priorities = shares(sv["priorities"]["rows"], sv["priorities"]["n"])
    problems = shares(sv["problems"]["rows"], sv["problems"]["n"])
    topics = shares(sv["topics"]["rows"], sv["topics"]["n"])
    concerns = shares(sv["concerns"]["rows"], sv["concerns"]["n"])
    employment = shares(sv["employment"]["rows"], sv["employment"]["n"])
    industry = shares(sv["industry"]["rows"], sv["industry"]["n"])
    pol = sv["political"]
    pol_n = pol["progressive"] + pol["center"] + pol["conservative"]
    political = shares([("Progressive (-5 to -1)", pol["progressive"]), ("Center (0)", pol["center"]),
                        ("Conservative (+1 to +5)", pol["conservative"])], pol_n)
    edu = CAREER["education"]
    education = shares(edu["rows"], edu["n"])
    degree = sum(r["pct"] for r in education if r["label"] in ("Bachelor's degree", "Master's degree", "Doctorate"))
    country = bucket_shares(GA4["newsletter"]["country"], region, REGION_ORDER)
    device = engaged_shares(GA4["newsletter"]["device"])
    language = bucket_shares(GA4["newsletter"]["language"], language_bucket, [*LANGUAGES, "Others"])
    ea_sv = next(r["pct"] for r in ident_sv if r["label"] == EA)
    ea_pa = next(r["pct"] for r in ident_pa if r["label"] == EA)
    rat_sv = next(r["pct"] for r in ident_sv if r["label"].startswith("Rationalist"))
    impact_sv = next(r["pct"] for r in goals_sv if r["label"].startswith("Have a greater positive impact"))
    comparables = ", ".join(sv["comparables"][:6])

    summary = [
        f"Readers describe themselves first as <b>lifelong learners</b> ({ident_sv[0]['pct']:.0f}%) and <b>science enthusiasts</b> ({ident_sv[1]['pct']:.0f}%); {rat_sv:.0f}% call themselves rationalists and {ea_pa:.0f} to {ea_sv:.0f}% effective altruists (aspiring included).",
        f"About half ({impact_sv:.0f}%) of audience surveys responders in 2026 name <b>having a greater positive impact on the world</b> as a personal goal; the topics they ask for most are critical thinking, psychology and philosophy.",
        f"Politically they lean progressive ({political[0]['pct']:.0f}% left of centre, {political[2]['pct']:.0f}% right), and the readers we have asked are highly educated ({degree:.0f}% with a bachelor's degree or higher).",
        f"Readers most often compare Clearer Thinking to {esc(comparables)}.",
    ]
    sections = [
        {"title": "Who they are",
         "lead": "From the March 2026 audience survey of newsletter readers (539 opened it; each question shows how many answered) and the Clearer Thinking Paths quiz, a self-improvement planning tool completed by 7,889 people between July 2023 and July 2026.",
         "rows": [
             [[spec("identSurvey", "How newsletter readers describe themselves", sv["identities"]["n"], ident_sv,
                    question='"Do any of the following categories apply to you?" Multi-select.')],
              [spec("identPaths", "How Paths quiz takers describe themselves", pa["identities"]["n"], ident_pa,
                    question="Same question, asked inside the Paths quiz. Multi-select.")]],
             [[spec("employment", "Career stage", sv["employment"]["n"], employment,
                    question='"Which of the following best describes your current primary role?"')],
              [spec("industry", "Industry", sv["industry"]["n"], industry,
                    question='"Which field or industry best describes your work?" Top 11 structured options.')]],
             [[spec("political", "Political self-placement", pol_n, political,
                    question='"In political matters, where do your views generally fall on the scale from left (progressive) to right (conservative)?" 11-point scale, grouped.')],
              [spec("education", "Education", edu["n"], education,
                    question="Career Navigation Survey, September 2026: a smaller survey of readers thinking about a career change, so treat it as indicative.",
                    note=f"{degree:.0f}% hold a bachelor's degree or higher.")]],
         ]},
        {"title": "What they are working on",
         "lead": "Priorities, goals and obstacles, as readers reported them in the March 2026 survey.",
         "rows": [
             [[spec("priorities", "High priorities right now", sv["priorities"]["n"], priorities,
                    question='"Which of these are high priorities for you right now in your life?" Multi-select.')],
              [spec("problems", "Biggest challenges right now", sv["problems"]["n"], problems,
                    question='"Which of these problems is a big challenge for you right now?" Multi-select.')]],
             [[spec("goals", "Personal goals (top 12 of 46)", sv["goals"]["n"], goals_sv,
                    question='"Which of these goals are major objectives of yours right now?" Multi-select.', wide=True)]],
         ]},
        {"title": "What they want to read, and what worries them", "lead": "",
         "rows": [
             [[spec("topics", "Topics readers want more of", sv["topics"]["n"], topics, question="Multi-select, top 15 options.")],
              [spec("concerns", "World trends that concern them most", sv["concerns"]["n"], concerns,
                    question='"What trends or changes in the world concern you the most right now?" Multi-select.')]],
         ]},
        {"title": "Where they are", "lead": "",
         "rows": [
             [[spec("country", "Country of engaged readers", country["n"], country["rows"])],
              [spec("language", "Browser language", language["n"], language["rows"]),
               spec("device", "Device", device["n"], device["rows"])]],
         ]},
    ]
    return {"title": TITLE, "meta": META, "summary": summary, "sections": sections}


# --------------------------------------------------------------------------- page
def build(stamp: str) -> str:
    CHARTS.clear()
    c = content()
    parts = [f"<h1>{esc(c['title'])}</h1>",
             f'<div class="report-meta">Data as of {stamp} · {esc(c["meta"])}</div>',
             '<div class="summary"><div class="summary-title">In short</div><ul>'
             + "".join(f"<li>{b}</li>" for b in c["summary"]) + "</ul></div>"]
    for i, sec in enumerate(c["sections"]):
        if i:
            parts.append(divider())
        parts.append(h2(sec["title"], sec["lead"]))
        for j, row in enumerate(sec["rows"]):
            if j:
                parts.append(divider())
            cells = ["".join(chart(s) for s in cell) for cell in row]
            parts.append(two_col(*cells) if len(cells) == 2 else cells[0])
    body = "\n".join(parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Clearer Thinking audience breakdown</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="page">
{body}
</div>
<script>
const CHARTS = {json.dumps(CHARTS)};
{JS}
</script>
</body>
</html>"""


CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f4f0; color: #1a1a18; line-height: 1.6; }
.page { max-width: 860px; margin: 0 auto; padding: 2.5rem 2rem 4rem; }
h1 { font-size: 26px; font-weight: 600; margin-bottom: 4px; }
h2 { font-size: 20px; font-weight: 600; margin: 2.5rem 0 6px; }
.report-meta { font-size: 13px; color: #73726c; margin-bottom: 1.5rem; }
.lead { font-size: 15px; margin-bottom: 1.5rem; }
.section-lead { font-size: 13px; color: #73726c; margin-bottom: 1rem; }
.summary { background: #fff; border: 1px solid #d3d1c7; border-left: 3px solid #0885f8; border-radius: 8px; padding: 14px 18px; margin-bottom: 1rem; }
.summary-title { font-size: 13px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #73726c; margin-bottom: 6px; }
.summary ul { padding-left: 18px; font-size: 14px; }
.summary li { margin-bottom: 5px; }
.section-title { font-size: 15px; font-weight: 600; color: #1a1a18; border-bottom: 1px solid #d3d1c7; padding-bottom: 6px; margin: 1.5rem 0 4px; }
.section-title .n { font-weight: 400; color: #888780; font-size: 12px; }
.question-wording { font-size: 12px; color: #888780; font-style: italic; margin-bottom: 8px; line-height: 1.5; }
.note { font-size: 12px; color: #73726c; margin-top: 6px; }
.chart-wrap { position: relative; width: 100%; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 8px; font-size: 12px; color: #73726c; }
.legend span { display: flex; align-items: center; gap: 5px; }
.legend-dot { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.divider { height: 1px; background: #d3d1c7; margin: 2rem 0; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; align-items: start; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }
.stat { background: #fff; border: 1px solid #d3d1c7; border-radius: 8px; padding: 12px 14px; }
.stat .v { font-size: 22px; font-weight: 600; }
.stat .l { font-size: 12px; color: #73726c; }
.limits { padding-left: 18px; font-size: 13px; color: #1a1a18; }
.limits li { margin-bottom: 8px; }
@media (max-width: 640px) { .two-col, .stats { grid-template-columns: 1fr; } }
"""

JS = """
const tc = '#73726c';
// Percent labels at the bar tips, so no axis or gridlines are needed.
const tipLabels = { id: 'tipLabels', afterDatasetsDraw(c) {
  const { ctx } = c; ctx.save(); ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  ctx.fillStyle = tc; ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
  c.data.datasets.forEach((ds, i) => c.getDatasetMeta(i).data.forEach((bar, j) => ctx.fillText(ds.data[j].toFixed(0) + '%', bar.x + 5, bar.y)));
  ctx.restore(); } };
// Long category labels are split onto two lines so they never clip at the canvas edge.
function wrap(label, width = 26) {
  if (label.length <= width) return label;
  const words = label.split(' '), lines = [''];
  for (const w of words) {
    if (lines[lines.length - 1].length + w.length + 1 > width && lines[lines.length - 1]) lines.push(w);
    else lines[lines.length - 1] = (lines[lines.length - 1] + ' ' + w).trim();
  }
  return lines;
}
function draw(spec) {
  const el = document.getElementById(spec.id); if (!el) return;
  const datasets = spec.series
    ? spec.series.map(s => ({ label: s.name, data: s.data, counts: s.counts, n: s.n, backgroundColor: s.color, borderRadius: 3, borderSkipped: false, maxBarThickness: 16 }))
    : [{ data: spec.data, counts: spec.counts, n: spec.n, backgroundColor: '#0885f8', borderRadius: 3, borderSkipped: false, maxBarThickness: 16 }];
  const max = Math.min(100, Math.ceil(Math.max(...datasets.flatMap(d => d.data)) / 10) * 10 + 12);
  new Chart(el, { type: 'bar', data: { labels: spec.labels.map(l => wrap(l, spec.wrap)), datasets }, plugins: [tipLabels],
    options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', layout: { padding: { right: 36 } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => {
        const d = ctx.dataset; return `${d.counts[ctx.dataIndex].toLocaleString()} of ${d.n.toLocaleString()} (${ctx.parsed.x}%)`; } } } },
      scales: { x: { display: false, min: 0, max }, y: { ticks: { color: tc, font: { size: 11 }, autoSkip: false }, grid: { display: false }, border: { display: false } } } } });
}
CHARTS.forEach(draw);
"""


def main() -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")
    OUT.write_text(build(stamp))
    print(f"page: {OUT} ({len(CHARTS)} charts)")


if __name__ == "__main__":
    main()
