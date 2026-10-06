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
ANGLOSPHERE = ("United States", "United Kingdom", "Canada", "Australia", "Ireland", "New Zealand")
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


def group_share(rows: list[dict], labels: tuple) -> float:
    return sum(r["pct"] for r in rows if r["label"] in labels)


# --------------------------------------------------------------------------- html pieces
def esc(s: str) -> str:
    return html.escape(s, quote=False)


CHARTS: list[dict] = []  # collected chart specs, serialised into the page's script


def chart(cid: str, title: str, n: int, rows: list[dict], question: str = "", note: str = "",
          highlight: tuple = (), height: int | None = None, series: list[dict] | None = None, n_label: str = "n",
          wide: bool = False) -> str:
    """A section with one horizontal bar chart. Single series: rows; comparison: series=[{name, rows, color}].

    wide=True means the chart spans the page (not a two-column cell), so labels can wrap at a longer width."""
    count = len(series[0]["rows"]) if series else len(rows)
    h = height or (count * (38 if series else 30) + 16)
    spec = {"id": cid, "n": n, "wrap": 48 if (wide or series) else 26}
    if series:
        spec["labels"] = [r["label"] for r in series[0]["rows"]]
        spec["series"] = [{"name": s["name"], "data": [round(r["pct"], 1) for r in s["rows"]], "counts": [r["count"] for r in s["rows"]],
                           "color": s["color"], "n": s["n"]} for s in series]
    else:
        spec["labels"] = [r["label"] for r in rows]
        spec["data"] = [round(r["pct"], 1) for r in rows]
        spec["counts"] = [r["count"] for r in rows]
        spec["colors"] = [ORANGE if r["label"] in highlight else BLUE for r in rows]
    CHARTS.append(spec)
    legend = ""
    if series:
        legend = '<div class="legend">' + "".join(
            f'<span><span class="legend-dot" style="background:{s["color"]}"></span>{esc(s["name"])} ({n_label} = {s["n"]:,})</span>'
            for s in series) + "</div>"
    return (f'<div class="section-title">{esc(title)}' + (f' <span class="n">({n_label} = {n:,})</span>' if n else "") + "</div>"
            + (f'<div class="question-wording">{esc(question)}</div>' if question else "")
            + f'<div class="chart-wrap" style="height:{h}px"><canvas id="{cid}"></canvas></div>' + legend
            + (f'<div class="note">{note}</div>' if note else ""))


def two_col(a: str, b: str) -> str:
    return f'<div class="two-col"><div>{a}</div><div>{b}</div></div>'


def divider() -> str:
    return '<div class="divider"></div>'


def h2(text: str, sub: str = "") -> str:
    return f"<h2>{esc(text)}</h2>" + (f'<p class="section-lead">{sub}</p>' if sub else "")


def stat_row(items: list[tuple[str, str]]) -> str:
    return '<div class="stats">' + "".join(f'<div class="stat"><div class="v">{v}</div><div class="l">{esc(l)}</div></div>' for v, l in items) + "</div>"


# --------------------------------------------------------------------------- page
def build(stamp: str) -> str:
    CHARTS.clear()
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
    country = engaged_shares(GA4["newsletter"]["country"], top=12)
    anglo = group_share(engaged_shares(GA4["newsletter"]["country"])["rows"], ANGLOSPHERE)
    device = engaged_shares(GA4["newsletter"]["device"])
    language = engaged_shares(GA4["newsletter"]["language"], top=6)
    win = GA4["window"]
    win_txt = f"{dt.date.fromisoformat(win['start']):%b %Y} to {dt.date.fromisoformat(win['end']):%b %Y}"
    ea_sv = next(r["pct"] for r in ident_sv if r["label"] == EA)
    ea_pa = next(r["pct"] for r in ident_pa if r["label"] == EA)
    rat_sv = next(r["pct"] for r in ident_sv if r["label"].startswith("Rationalist"))
    impact_sv = next(r["pct"] for r in goals_sv if r["label"].startswith("Have a greater positive impact"))
    comparables = ", ".join(sv["comparables"][:6])

    body = f"""
<h1>Clearer Thinking audience breakdown</h1>
<div class="report-meta">Data as of {stamp} · Every chart shows its own sample size. Data from analytics and surveys.</div>


<div class="summary">
  <div class="summary-title">In short</div>
  <ul>
    <li>Readers describe themselves first as <b>lifelong learners</b> ({ident_sv[0]['pct']:.0f}%) and <b>science enthusiasts</b> ({ident_sv[1]['pct']:.0f}%); {rat_sv:.0f}% call themselves rationalists and {ea_pa:.0f} to {ea_sv:.0f}% effective altruists (aspiring included).</li>
    <li>About half ({impact_sv:.0f}%) of audience surveys responders in 2026 name <b>having a greater positive impact on the world</b> as a personal goal; the topics they ask for most are critical thinking, psychology and philosophy.</li>
    <li>Politically they lean progressive ({political[0]['pct']:.0f}% left of centre, {political[2]['pct']:.0f}% right), and the readers we have asked are highly educated ({degree:.0f}% with a bachelor's degree or higher).</li>
    <li>Readers most often compare Clearer Thinking to {esc(comparables)}.</li>
  </ul>
</div>

{h2("Who they are", "From the March 2026 audience survey of newsletter readers (539 opened it; each question shows how many answered) and the Clearer Thinking Paths quiz, a self-improvement planning tool completed by 7,889 people between July 2023 and July 2026.")}
{two_col(
    chart("identSurvey", "How newsletter readers describe themselves", sv["identities"]["n"], ident_sv,
          question='"Do any of the following categories apply to you?" Multi-select.'),
    chart("identPaths", "How Paths quiz takers describe themselves", pa["identities"]["n"], ident_pa,
          question="Same question, asked inside the Paths quiz. Multi-select."))}
{divider()}
{two_col(
    chart("employment", "Career stage", sv["employment"]["n"], employment, question='"Which of the following best describes your current primary role?"'),
    chart("industry", "Industry", sv["industry"]["n"], industry, question='"Which field or industry best describes your work?" Top 11 structured options.'))}
{divider()}
{two_col(
    chart("political", "Political self-placement", pol_n, political,
          question='"In political matters, where do your views generally fall on the scale from left (progressive) to right (conservative)?" 11-point scale, grouped.'),
    chart("education", "Education", edu["n"], education,
          question="Career Navigation Survey, September 2026: a smaller survey of readers thinking about a career change, so treat it as indicative.",
          note=f"{degree:.0f}% hold a bachelor's degree or higher."))}

{divider()}
{h2("What they are working on", "Priorities, goals and obstacles, as readers reported them in the March 2026 survey.")}
{two_col(
    chart("priorities", "High priorities right now", sv["priorities"]["n"], priorities, question='"Which of these are high priorities for you right now in your life?" Multi-select.'),
    chart("problems", "Biggest challenges right now", sv["problems"]["n"], problems, question='"Which of these problems is a big challenge for you right now?" Multi-select.'))}
{divider()}
{chart("goals", "Personal goals (top 12 of 46)", sv["goals"]["n"], goals_sv, question='"Which of these goals are major objectives of yours right now?" Multi-select.', wide=True)}

{divider()}
{h2("What they want to read, and what worries them")}
{two_col(
    chart("topics", "Topics readers want more of", sv["topics"]["n"], topics, question="Multi-select, top 15 options."),
    chart("concerns", "World trends that concern them most", sv["concerns"]["n"], concerns, question='"What trends or changes in the world concern you the most right now?" Multi-select.'))}

{divider()}
{h2("Where they are", f"Google Analytics, {win_txt}: visits to our website that came from a newsletter link, counted as engaged visits (over ten seconds, or more than one page); n is the number of such visits. Email link scanners create visits from data-centre locations but almost never engaged ones, so this is the cleaner view.")}
{two_col(
    chart("country", "Country of engaged newsletter visits", country["n"], country["rows"],
          note=f"{anglo:.0f}% from the US, UK, Canada, Australia, Ireland or New Zealand."),
    chart("language", "Browser language", language["n"], language["rows"], question="Top 6.")
    + chart("device", "Device", device["n"], device["rows"]))}

"""
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
    : [{ data: spec.data, counts: spec.counts, n: spec.n, backgroundColor: spec.colors, borderRadius: 3, borderSkipped: false, maxBarThickness: 16 }];
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
