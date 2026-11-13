"""Render the Flow tab mockup from data.json into reports/flow_tab_mockup_2026-11-13.html.

    .venv/bin/python reports/flow_tab_mockup_2026-11-13_src/build.py

The page mimics the live dashboard's chrome (header, date presets, tab row) so the new tab can be judged in
context. The diagram is a three-column Sankey (source -> landing page -> outcome) drawn with d3-sankey; link
widths are linear in users, with a 1.5px floor so the rare outcomes stay visible, and labels are dodged apart
with leader lines when nodes are thin.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from flow_model import PAGE_ORDER, SOURCE_ORDER  # noqa: E402

OUT = HERE.parent / "flow_tab_mockup_2026-11-13.html"

# Validated categorical palette (dataviz skill reference instance), fixed order = SOURCE_ORDER; Other = gray.
SOURCE_COLORS_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#a1a1aa"]
SOURCE_COLORS_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#71717a"]


def main() -> None:
    data = json.loads((HERE / "data.json").read_text())
    stamp = datetime.now().strftime("%Y-%m-%d %I:%M%p").replace("AM", "am").replace("PM", "pm")
    payload = {
        "windows": data["windows"],
        "sourceOrder": SOURCE_ORDER,
        "pageOrder": PAGE_ORDER,
        "colorsLight": SOURCE_COLORS_LIGHT,
        "colorsDark": SOURCE_COLORS_DARK,
        "fetched": data["fetched"],
        "only30d": bool(data.get("only_30d")),
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(payload)).replace("__STAMP__", stamp)
    OUT.write_text(html)
    print("wrote", OUT)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flow tab mockup</title>
<style>
  :root {
    color-scheme: light;
    --bg: #fafafa; --card: #ffffff; --border: #e4e4e7; --border-soft: #f4f4f5;
    --text: #18181b; --text-2: #52525b; --text-3: #71717a; --text-4: #a1a1aa;
    --accent: #16a34a; --tab-bg: #f4f4f5; --tab-active: #ffffff;
    --node: #3f3f46; --node-outcome: #16a34a; --node-none: #d4d4d8; --link-outcome: #16a34a; --link-none: #d4d4d8;
    --tip-bg: #18181b; --tip-text: #fafafa;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --bg: #09090b; --card: #09090b; --border: #27272a; --border-soft: #1f1f23;
      --text: #f4f4f5; --text-2: #a1a1aa; --text-3: #a1a1aa; --text-4: #71717a;
      --accent: #4ade80; --tab-bg: #18181b; --tab-active: #27272a;
      --node: #d4d4d8; --node-outcome: #4ade80; --node-none: #3f3f46; --link-outcome: #4ade80; --link-none: #3f3f46;
      --tip-bg: #f4f4f5; --tip-text: #18181b;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --bg: #09090b; --card: #09090b; --border: #27272a; --border-soft: #1f1f23;
    --text: #f4f4f5; --text-2: #a1a1aa; --text-3: #a1a1aa; --text-4: #71717a;
    --accent: #4ade80; --tab-bg: #18181b; --tab-active: #27272a;
    --node: #d4d4d8; --node-outcome: #4ade80; --node-none: #3f3f46; --link-outcome: #4ade80; --link-none: #3f3f46;
    --tip-bg: #f4f4f5; --tip-text: #18181b;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  header { background: var(--card); border-bottom: 1px solid var(--border); }
  .wrap { max-width: 80rem; margin: 0 auto; padding: 0 1.5rem; }
  .head { display: flex; flex-wrap: wrap; gap: .75rem; justify-content: space-between; align-items: flex-start; padding: 1rem 0; }
  h1 { font-size: 1.5rem; margin: 0; }
  .sub { font-size: .75rem; color: var(--text-3); margin-top: .25rem; }
  .presets { display: inline-flex; border: 1px solid var(--border); border-radius: .5rem; padding: 2px; background: var(--tab-bg); }
  .presets button { border: 0; background: transparent; color: var(--text-2); font: inherit; font-size: .875rem; padding: .375rem .75rem; border-radius: .375rem; cursor: pointer; }
  .presets button[aria-selected="true"] { background: var(--tab-active); font-weight: 500; color: var(--text); box-shadow: 0 1px 2px rgba(0,0,0,.08); }
  .presets button:disabled { color: var(--text-4); cursor: not-allowed; }
  .tabs { display: flex; gap: .25rem; overflow-x: auto; margin-bottom: -1px; }
  .tabs span { padding: .625rem 1rem; font-size: .875rem; color: var(--text-3); border-bottom: 2px solid transparent; white-space: nowrap; }
  .tabs span.active { color: var(--text); font-weight: 500; border-bottom-color: var(--accent); }
  main { padding: 1.5rem 0; }
  .mock-note { font-size: .75rem; color: #92400e; background: #fffbeb; border: 1px solid #fde68a; border-radius: .375rem; padding: .5rem .75rem; margin-bottom: 1rem; }
  :root[data-theme="dark"] .mock-note, :root:not([data-theme="light"]) .mock-note { }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .mock-note { color: #fcd34d; background: rgba(120,53,15,.25); border-color: #78350f; } }
  :root[data-theme="dark"] .mock-note { color: #fcd34d; background: rgba(120,53,15,.25); border-color: #78350f; }
  h3 { font-size: 1.125rem; margin: 0 0 .25rem; }
  .lead { color: var(--text-3); font-size: .875rem; margin: 0 0 1rem; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); gap: .75rem; margin-bottom: 1rem; }
  .kpi { background: var(--card); border: 1px solid var(--border); border-radius: .75rem; padding: .875rem 1rem; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
  .kpi .l { font-size: .75rem; color: var(--text-3); }
  .kpi .v { font-size: 1.5rem; font-weight: 700; line-height: 1.2; margin-top: .125rem; }
  .kpi .c { font-size: .7rem; color: var(--text-4); margin-top: .125rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: .75rem; padding: 1.25rem; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
  .toolbar { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; justify-content: space-between; margin-bottom: .75rem; font-size: .8125rem; color: var(--text-2); }
  .toolbar label { display: inline-flex; gap: .375rem; align-items: center; cursor: pointer; }
  .seg { display: inline-flex; border: 1px solid var(--border); border-radius: .375rem; overflow: hidden; }
  .seg button { border: 0; background: transparent; color: var(--text-2); font: inherit; font-size: .8125rem; padding: .25rem .625rem; cursor: pointer; }
  .seg button[aria-selected="true"] { background: var(--tab-bg); color: var(--text); font-weight: 500; }
  .cols { display: grid; grid-template-columns: 1fr 1fr 1fr; font-size: .75rem; color: var(--text-3); text-transform: uppercase; letter-spacing: .04em; margin: 0 0 .25rem; }
  .cols span:nth-child(2) { text-align: center; } .cols span:nth-child(3) { text-align: right; }
  svg { display: block; width: 100%; height: auto; }
  .node-label { font-size: 12px; fill: var(--text); paint-order: stroke; stroke: var(--card); stroke-width: 3px; stroke-linejoin: round; }
  .node-label .n { fill: var(--text-3); }
  .leader { stroke: var(--text-4); stroke-width: 1; fill: none; }
  .stripe-box { font-size: 12px; }
  .legend { display: flex; flex-wrap: wrap; gap: .5rem 1rem; font-size: .75rem; color: var(--text-2); margin-top: .75rem; }
  .legend span { display: inline-flex; align-items: center; gap: .375rem; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
  .tip { position: fixed; pointer-events: none; background: var(--tip-bg); color: var(--tip-text); font-size: 12px; line-height: 1.4; padding: .375rem .5rem; border-radius: .375rem; max-width: 20rem; opacity: 0; transition: opacity .08s; z-index: 10; }
  table { width: 100%; border-collapse: collapse; font-size: .8125rem; }
  th, td { padding: .5rem .75rem; text-align: left; border-top: 1px solid var(--border-soft); }
  th { color: var(--text-3); font-weight: 500; background: var(--tab-bg); border-top: 0; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .notes { margin-top: 1rem; font-size: .8125rem; color: var(--text-2); }
  .notes h4 { font-size: .875rem; color: var(--text); margin: 1rem 0 .25rem; }
  .notes ul { margin: .25rem 0 0 1.125rem; padding: 0; } .notes li { margin: .2rem 0; }
  .hidden { display: none; }
  @media (max-width: 640px) { .wrap { padding: 0 1rem; } h1 { font-size: 1.25rem; } }
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="head">
      <div>
        <h1>ClearerThinking Growth Dashboard</h1>
        <div class="sub" id="sub">Mockup built __STAMP__</div>
      </div>
      <div class="presets" id="presets" role="tablist">
        <button role="tab" data-w="7d">Last 7 days</button>
        <button role="tab" data-w="30d">Last 30 days</button>
        <button role="tab" data-w="90d">Last 90 days</button>
        <button role="tab" disabled title="In the real tab this works like the other tabs (sliced from daily data). The mockup carries three windows.">This month</button>
        <button role="tab" disabled title="In the real tab this works like the other tabs (sliced from daily data). The mockup carries three windows.">Year to date</button>
        <button role="tab" disabled title="In the real tab this works like the other tabs (sliced from daily data). The mockup carries three windows.">Custom</button>
      </div>
    </div>
    <nav class="tabs"><span>Overview</span><span>Funnel</span><span>Modules by Channel</span><span>Monetization</span><span>Personas</span><span class="active">Flow</span></nav>
  </div>
</header>
<main>
  <div class="wrap">
    <div class="mock-note">Mockup for review, not the live dashboard: real GA4 and Stripe numbers for the three date presets, static HTML. The header and tab row are reproduced so the new tab can be judged in context.</div>
    <h3>Flow</h3>
    <p class="lead">Where unique users come from, which page they land on, and what they do: GA4 sessions in the window, grouped by traffic source and landing page, with the outcome events of those sessions. Hover any band or box for the numbers; switch to the table for every row.</p>

    <div class="kpis" id="kpis"></div>

    <div class="card">
      <div class="toolbar">
        <div class="seg" role="tablist"><button data-view="diagram" aria-selected="true">Diagram</button><button data-view="table" aria-selected="false">Table</button></div>
        <label><input type="checkbox" id="showNone" checked> Show users with no tracked outcome</label>
      </div>
      <div id="diagram">
        <div class="cols"><span>Traffic source</span><span>Landing page</span><span>Outcome</span></div>
        <svg id="sankey"></svg>
        <div class="legend" id="legend"></div>
      </div>
      <div id="table" class="hidden"></div>
    </div>

    <div class="notes" id="notes"></div>
  </div>
</main>
<div class="tip" id="tip"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3-sankey/0.12.3/d3-sankey.min.js"></script>
<script>
const DATA = __DATA__;
const fmt = d3.format(",");
const pct = (a, b) => b ? (100 * a / b).toFixed(a / b < 0.01 ? 2 : 1) + "%" : "0%";
const dark = () => (document.documentElement.dataset.theme === "dark") ||
  (document.documentElement.dataset.theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
const sourceColor = (name) => {
  const i = DATA.sourceOrder.indexOf(name);
  const cols = dark() ? DATA.colorsDark : DATA.colorsLight;
  return cols[i < 0 ? cols.length - 1 : i];
};
let windowKey = "30d", view = "diagram";

function model(w, showNone) {
  // Fold sources / pages under 0.4% of users into Other so thin nodes do not pile up labels.
  const users = d3.sum(w.landing, r => r.users);
  const bySource = d3.rollup(w.landing, v => d3.sum(v, r => r.users), r => r.source);
  const byPage = d3.rollup(w.landing, v => d3.sum(v, r => r.users), r => r.page);
  const floor = users * 0.004;
  const srcName = s => (bySource.get(s) || 0) >= floor || s === "Other" ? s : "Other";
  const pageName = p => (byPage.get(p) || 0) >= users * 0.001 || p === "Other pages" ? p : "Other pages";
  const sp = d3.rollup(w.landing, v => d3.sum(v, r => r.users), r => srcName(r.source), r => pageName(r.page));
  const po = d3.rollup(w.outcomes, v => d3.sum(v, r => r.users), r => pageName(r.page), r => r.outcome);
  const sources = DATA.sourceOrder.filter(s => sp.has(s));
  const pages = DATA.pageOrder.filter(p => [...sp.values()].some(m => m.has(p)));
  const outcomes = ["Email Submitted", "CT+ Sign Up"].concat(showNone ? ["No tracked outcome"] : []);
  const nodes = [...sources.map(n => ({ name: n, col: 0 })), ...pages.map(n => ({ name: n, col: 1 })), ...outcomes.map(n => ({ name: n, col: 2 }))];
  const idx = new Map(nodes.map((n, i) => [n.name, i]));
  const links = [];
  for (const s of sources) for (const p of pages) { const v = sp.get(s)?.get(p) || 0; if (v > 0) links.push({ source: idx.get(s), target: idx.get(p), value: v, kind: "source", src: s }); }
  const pageUsers = new Map(pages.map(p => [p, d3.sum(sources, s => sp.get(s)?.get(p) || 0)]));
  for (const p of pages) {
    let tracked = 0;
    for (const o of ["Email Submitted", "CT+ Sign Up"]) { const v = po.get(p)?.get(o) || 0; if (v > 0) { links.push({ source: idx.get(p), target: idx.get(o), value: v, kind: "outcome" }); tracked += v; } }
    if (showNone) { const rest = Math.max(0, pageUsers.get(p) - tracked); if (rest > 0) links.push({ source: idx.get(p), target: idx.get("No tracked outcome"), value: rest, kind: "none" }); }
  }
  const totals = { users, email: d3.sum(w.outcomes.filter(r => r.outcome === "Email Submitted"), r => r.users),
                   plus: d3.sum(w.outcomes.filter(r => r.outcome === "CT+ Sign Up"), r => r.users) };
  return { nodes, links, totals, bySource, pageUsers, po };
}

function render() {
  const w = DATA.windows[windowKey];
  const showNone = document.getElementById("showNone").checked;
  const m = model(w, showNone);
  document.getElementById("sub").textContent = `${w.start} → ${w.end} · ${w.days} days · Mockup built __STAMP__ (GA4 + Stripe pulled ${DATA.fetched})`;
  document.querySelectorAll("#presets button").forEach(b => b.setAttribute("aria-selected", b.dataset.w === windowKey));
  if (DATA.only30d) document.querySelectorAll("#presets button[data-w]").forEach(b => { if (b.dataset.w !== "30d") { b.disabled = true; b.title = "GA4's hourly API quota was exhausted while building this mockup; the real tab carries every window."; } });

  // KPI row
  const k = [
    ["Users with a landing page", fmt(m.totals.users), `GA4 · ${fmt(w.dropped_no_landing_page)} more had no page (email pixel, server events)`],
    ["Email Submitted", fmt(m.totals.email), `${pct(m.totals.email, m.totals.users)} of users · GA4 "Submitted Email"`],
    ["CT+ Sign Up", fmt(m.totals.plus), `GA4 plus_sign_up · Stripe: ${fmt(w.stripe.new_subscriptions)} new subscriptions`],
    ["Cognitive Assessment sales", fmt(w.stripe.cognitive_sales), "Stripe · path not trackable yet"],
    ["Personality PDF sales", fmt(w.stripe.pdf_sales), "Stripe · path not trackable yet"],
  ];
  document.getElementById("kpis").innerHTML = k.map(([l, v, c]) => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="c">${c}</div></div>`).join("");

  drawSankey(m, w);
  drawTable(m, w);
  drawNotes(w);
}

function drawSankey(m, w) {
  const svg = d3.select("#sankey");
  svg.selectAll("*").remove();
  const width = Math.max(720, document.getElementById("diagram").clientWidth);
  const height = 620, mL = 150, mR = 190, mT = 8, mB = 90;
  svg.attr("viewBox", `0 0 ${width} ${height}`);
  const sankey = d3.sankey().nodeId((d, i) => i).nodeWidth(12).nodePadding(10).nodeAlign(d3.sankeyJustify)
    .nodeSort(null).linkSort(null).extent([[mL, mT], [width - mR, height - mB]]);
  const graph = sankey({ nodes: m.nodes.map(d => ({ ...d })), links: m.links.map(d => ({ ...d })) });
  const tip = d3.select("#tip");
  const show = (ev, html) => tip.style("opacity", 1).html(html).style("left", (ev.clientX + 14) + "px").style("top", (ev.clientY + 14) + "px");
  const hide = () => tip.style("opacity", 0);

  // Links: colored by source in column 1, by outcome in column 2; 1.5px floor so rare outcomes stay visible.
  svg.append("g").attr("fill", "none").selectAll("path").data(graph.links).join("path")
    .attr("d", d3.sankeyLinkHorizontal())
    .attr("stroke", d => d.kind === "source" ? sourceColor(d.src) : d.kind === "outcome" ? "var(--link-outcome)" : "var(--link-none)")
    .attr("stroke-opacity", d => d.kind === "none" ? 0.45 : 0.55)
    .attr("stroke-width", d => Math.max(1.5, d.width))
    .on("mousemove", (ev, d) => {
      const s = d.source.name, t = d.target.name;
      const ofS = pct(d.value, d.source.value), ofT = pct(d.value, d.target.value);
      show(ev, `<strong>${s} → ${t}</strong><br>${fmt(d.value)} users<br>${ofS} of ${s} · ${ofT} of ${t}`);
    }).on("mouseleave", hide);

  // Nodes (2px visual floor).
  svg.append("g").selectAll("rect").data(graph.nodes).join("rect")
    .attr("x", d => d.x0).attr("y", d => d.y0).attr("height", d => Math.max(2, d.y1 - d.y0)).attr("width", d => d.x1 - d.x0)
    .attr("rx", 2)
    .attr("fill", d => d.col === 0 ? sourceColor(d.name) : d.name === "No tracked outcome" ? "var(--node-none)" : d.col === 2 ? "var(--node-outcome)" : "var(--node)")
    .on("mousemove", (ev, d) => {
      let extra = "";
      if (d.col === 1) { const e = m.po.get(d.name)?.get("Email Submitted") || 0, p = m.po.get(d.name)?.get("CT+ Sign Up") || 0;
        extra = `<br>Email Submitted ${fmt(e)} (${pct(e, d.value)}) · CT+ ${fmt(p)}`; }
      show(ev, `<strong>${d.name}</strong><br>${fmt(d.value)} users · ${pct(d.value, m.totals.users)} of all${extra}`);
    }).on("mouseleave", hide);

  // Labels, dodged apart per column (14px minimum pitch) with a leader line when moved.
  const labels = svg.append("g").attr("class", "node-label");
  for (const col of [0, 1, 2]) {
    const ns = graph.nodes.filter(n => n.col === col).sort((a, b) => a.y0 - b.y0);
    let y = -Infinity;
    for (const n of ns) { n.ly = Math.max((n.y0 + n.y1) / 2, y + 14); y = n.ly; }
    // push back up if the column overflowed the bottom
    const over = ns.length ? ns[ns.length - 1].ly - (height - mB) : 0;
    if (over > 0) { let yb = Infinity; for (const n of [...ns].reverse()) { n.ly = Math.min(n.ly - over, yb - 14); yb = n.ly; } }
    for (const n of ns) {
      const right = col === 2, center = col === 1;
      const x = right ? n.x1 + 8 : center ? n.x0 - 8 : n.x0 - 8;
      const anchor = right ? "start" : "end";
      const moved = Math.abs(n.ly - (n.y0 + n.y1) / 2) > 7;
      if (moved) labels.append("path").attr("class", "leader")
        .attr("d", `M${right ? n.x1 : n.x0},${(n.y0 + n.y1) / 2} H${right ? n.x1 + 4 : n.x0 - 4} V${n.ly}`);
      const t = labels.append("text").attr("x", x).attr("y", n.ly).attr("dy", "0.35em").attr("text-anchor", anchor);
      t.append("tspan").text(n.name);
      t.append("tspan").attr("class", "n").text(` ${fmt(n.value)}`);
    }
  }

  // Stripe-only outcomes: drawn in the outcome column, dashed, because GA4 cannot place them on a path.
  const bx = width - mR + 8, by = height - mB + 14;
  const boxes = [["Cognitive Assessment", w.stripe.cognitive_sales], ["Personality PDF", w.stripe.pdf_sales]];
  const g = svg.append("g").attr("class", "stripe-box");
  boxes.forEach(([name, n], i) => {
    const y = by + i * 34;
    g.append("rect").attr("x", bx - 20).attr("y", y).attr("width", 12).attr("height", 24).attr("rx", 2)
      .attr("fill", "none").attr("stroke", "var(--node-outcome)").attr("stroke-dasharray", "3 2");
    g.append("text").attr("x", bx).attr("y", y + 9).attr("fill", "var(--text)").text(name + " ").append("tspan").attr("fill", "var(--text-3)").text(fmt(n));
    g.append("text").attr("x", bx).attr("y", y + 22).attr("fill", "var(--text-4)").style("font-size", "10px").text("Stripe sales · path not trackable yet");
  });
  g.append("text").attr("x", mL).attr("y", by + 9).attr("fill", "var(--text-4)").style("font-size", "11px")
    .text("Band width = users (1.5px minimum so rare outcomes stay visible). Dashed boxes: counted in Stripe, no GA4 path.");

  document.getElementById("legend").innerHTML = m.nodes.filter(n => n.col === 0).map(n => `<span><i style="background:${sourceColor(n.name)}"></i>${n.name}</span>`).join("")
    + `<span><i style="background:var(--link-outcome)"></i>Tracked outcome</span><span><i style="background:var(--link-none)"></i>No tracked outcome</span>`;
}

function drawTable(m, w) {
  const rows = [];
  const sp = d3.rollup(w.landing, v => d3.sum(v, r => r.users), r => r.source, r => r.page);
  const oc = d3.rollup(w.outcomes, v => d3.sum(v, r => r.users), r => r.source, r => r.page, r => r.outcome);
  for (const [s, pm] of sp) for (const [p, u] of pm) {
    const e = oc.get(s)?.get(p)?.get("Email Submitted") || 0, c = oc.get(s)?.get(p)?.get("CT+ Sign Up") || 0;
    rows.push({ s, p, u, e, c });
  }
  rows.sort((a, b) => b.u - a.u);
  document.getElementById("table").innerHTML = `<table><thead><tr><th>Traffic source</th><th>Landing page</th><th class="num">Users</th><th class="num">Email Submitted</th><th class="num">Rate</th><th class="num">CT+ Sign Up</th></tr></thead><tbody>`
    + rows.map(r => `<tr><td>${r.s}</td><td>${r.p}</td><td class="num">${fmt(r.u)}</td><td class="num">${fmt(r.e)}</td><td class="num">${pct(r.e, r.u)}</td><td class="num">${fmt(r.c)}</td></tr>`).join("")
    + `</tbody></table>`;
}

function drawNotes(w) {
  const top = w.top_pages.slice(0, 12).map(p => `${p.host}${p.path} (${fmt(p.users)})`).join(", ");
  document.getElementById("notes").innerHTML = `
    <h4>How this is measured</h4>
    <ul>
      <li><strong>Users</strong>: GA4 <code>totalUsers</code> by session default channel group and landing page (host + path). A person with sessions from two sources is counted under both. Sessions with no landing page are left out: in this window ${fmt(w.dropped_no_landing_page)} users, almost all the One Helpful Idea open pixel (<code>email_open</code>) and server-side purchase events.</li>
      <li><strong>Traffic source</strong> folds GA4's channel groups: Paid Media = Paid Search, Paid Social, Paid Other, Display and Cross-network (Performance Max); Social = Organic Social + Organic Video; Other = Unassigned and the rest. Sources under 0.4% of users fold into Other; pages under 0.1% into Other pages. "Unknown page" = sessions on a known host whose first hit was not a page view (GA4 records no landing page).</li>
      <li><strong>Landing page</strong> families: Who Attracts You study, Homepage, Personality Test (incl. the report page), Rationality Test, Cognitive Assessment page, Coaching page, CT+ page, Tools gallery, Articles (every /post/), Podcast, Other tools (other programs.* pages), Other pages. Top raw pages in this window: ${top}.</li>
      <li><strong>Email Submitted</strong> = users whose session fired GA4 "Submitted Email" (a tool finished, per GA4_EVENTS.md). <strong>CT+ Sign Up</strong> = users whose session fired <code>plus_sign_up</code> (the thank-you page of the sign-up flow). Stripe counts ${fmt(w.stripe.new_subscriptions)} new subscriptions in the window: the difference is sign-ups from the member dashboard, the article paywall and sessions GA4 could not tie to a page.</li>
      <li><strong>Cognitive Assessment and Personality PDF</strong> are Stripe sale counts. GA4 receives their purchase events from Paytics with source "(not set)", so they cannot be placed on a source or page until checkout carries the GA client id (the ct-checkout project). The <em>page</em> is known in principle (Cognitive page, Personality Test report); the <em>source</em> is not.</li>
      <li><strong>No tracked outcome</strong> = users of that landing page minus the two tracked outcomes (a user with both outcomes is counted in both, so this can be slightly low).</li>
    </ul>
    <h4>What the real tab would add</h4>
    <ul>
      <li>Daily rows (date × source × page × outcome) in the snapshot, so This month, Year to date and custom ranges slice client-side like every other tab; about 60k small rows for the 2026 window.</li>
      <li>A click on a page node to open the Funnel tab filtered to that page; a click on a source to filter the table.</li>
      <li>Optional fourth column "Tool started" (Accepted Privacy Policy) between landing page and outcome, if the drop-off inside tools matters here.</li>
    </ul>
    <h4>Open questions for this round</h4>
    <ul>
      <li>Session source (shown) or first-touch user acquisition (<code>firstUserDefaultChannelGroup</code>)? Session source answers "what brought this visit"; first-touch answers "how did we first meet them".</li>
      <li>Keep the "No tracked outcome" band (shows scale honestly, makes conversions look thin) or hide it by default (toggle above)?</li>
      <li>Page families: right level of detail? Each family can be split or merged.</li>
      <li>Outcomes: add "Tool started", coaching button clicks, or newsletter clicks as outcomes?</li>
    </ul>`;
}

document.querySelectorAll("#presets button[data-w]").forEach(b => b.addEventListener("click", () => { windowKey = b.dataset.w; render(); }));
document.querySelectorAll(".seg button").forEach(b => b.addEventListener("click", () => {
  view = b.dataset.view;
  document.querySelectorAll(".seg button").forEach(x => x.setAttribute("aria-selected", x === b));
  document.getElementById("diagram").classList.toggle("hidden", view !== "diagram");
  document.getElementById("table").classList.toggle("hidden", view !== "table");
}));
document.getElementById("showNone").addEventListener("change", render);
window.addEventListener("resize", render);
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
