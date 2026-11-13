/**
 * Flow tab model: first-touch source -> landing-page category -> outcome, as unique users.
 * Pure functions (tested in flow.test.ts). The snapshot carries exact blocks for the presets
 * (periods[preset].current.flow, from GA4 with one multi-range query set) and daily rows for custom
 * ranges (daily_window.flow), which sliceFlowDaily sums the way every other daily series is summed.
 * Rules and names mirror flow_model.py at the repo root.
 */

export interface FlowRow {
  source: string;
  page: string;
  users: number;
}

export interface FlowOutcomeRow extends FlowRow {
  outcome: string;
}

export interface FlowBlock {
  landing: FlowRow[];
  outcomes: FlowOutcomeRow[];
}

export interface FlowDailyRow {
  date: string;
  source: string;
  page: string;
  users: number;
  email_submitted: number;
  plus_sign_up: number;
}

export const SOURCE_ORDER = ["Organic Search", "Direct", "Paid Media", "Email", "Social", "Referral", "AI Assistant", "Other"];
export const PAGE_ORDER = ["Home", "Articles", "Tools", "Other"];
export const OUTCOMES = ["Email Submitted", "CT+ Sign Up"];
export const NO_OUTCOME = "No tracked outcome";

export interface FlowNode {
  id: string;
  name: string;
  col: 0 | 1 | 2;
}

export interface FlowLink {
  source: number;
  target: number;
  value: number;
  kind: "source" | "outcome" | "none";
  src?: string;
}

export interface FlowGraph {
  nodes: FlowNode[];
  links: FlowLink[];
  totals: { users: number; email: number; plus: number };
  pageUsers: Map<string, number>;
  /** page -> outcome -> users */
  pageOutcomes: Map<string, Map<string, number>>;
}

/** Sum the daily rows inside [start, end] into one block (same overcount of multi-day visitors as the other tabs). */
export function sliceFlowDaily(rows: FlowDailyRow[], start: string, end: string): FlowBlock {
  const landing = new Map<string, number>();
  const outcomes = new Map<string, number>();
  for (const r of rows) {
    if (r.date < start || r.date > end) continue;
    const k = `${r.source}\u0000${r.page}`;
    landing.set(k, (landing.get(k) || 0) + (r.users || 0));
    if (r.email_submitted) outcomes.set(`${k}\u0000Email Submitted`, (outcomes.get(`${k}\u0000Email Submitted`) || 0) + r.email_submitted);
    if (r.plus_sign_up) outcomes.set(`${k}\u0000CT+ Sign Up`, (outcomes.get(`${k}\u0000CT+ Sign Up`) || 0) + r.plus_sign_up);
  }
  return {
    landing: [...landing.entries()].filter(([, u]) => u > 0).map(([k, users]) => {
      const [source, page] = k.split("\u0000");
      return { source, page, users };
    }),
    outcomes: [...outcomes.entries()].map(([k, users]) => {
      const [source, page, outcome] = k.split("\u0000");
      return { source, page, outcome, users };
    }),
  };
}

/**
 * Nodes and links for the diagram. Sources under `foldBelow` of all users fold into Other so thin
 * nodes do not pile up labels; node ids are column-prefixed because "Other" is both a source and a page.
 */
export function buildFlowGraph(block: FlowBlock, showNone: boolean, foldBelow = 0.004): FlowGraph {
  const users = block.landing.reduce((s, r) => s + r.users, 0);
  const bySource = new Map<string, number>();
  for (const r of block.landing) bySource.set(r.source, (bySource.get(r.source) || 0) + r.users);
  const srcName = (s: string) => (s === "Other" || (bySource.get(s) || 0) >= users * foldBelow ? s : "Other");

  const sp = new Map<string, Map<string, number>>(); // source -> page -> users
  for (const r of block.landing) {
    const s = srcName(r.source);
    if (!sp.has(s)) sp.set(s, new Map());
    const m = sp.get(s)!;
    m.set(r.page, (m.get(r.page) || 0) + r.users);
  }
  const pageOutcomes = new Map<string, Map<string, number>>();
  for (const r of block.outcomes) {
    if (!pageOutcomes.has(r.page)) pageOutcomes.set(r.page, new Map());
    const m = pageOutcomes.get(r.page)!;
    m.set(r.outcome, (m.get(r.outcome) || 0) + r.users);
  }

  const sources = SOURCE_ORDER.filter((s) => sp.has(s));
  const pages = PAGE_ORDER.filter((p) => sources.some((s) => (sp.get(s)?.get(p) || 0) > 0));
  const outcomes = showNone ? [...OUTCOMES, NO_OUTCOME] : [...OUTCOMES];
  const nodes: FlowNode[] = [
    ...sources.map((n) => ({ id: "s:" + n, name: n, col: 0 as const })),
    ...pages.map((n) => ({ id: "p:" + n, name: n, col: 1 as const })),
    ...outcomes.map((n) => ({ id: "o:" + n, name: n, col: 2 as const })),
  ];
  const idx = new Map(nodes.map((n, i) => [n.id, i]));
  const links: FlowLink[] = [];
  for (const s of sources)
    for (const p of pages) {
      const v = sp.get(s)?.get(p) || 0;
      if (v > 0) links.push({ source: idx.get("s:" + s)!, target: idx.get("p:" + p)!, value: v, kind: "source", src: s });
    }
  const pageUsers = new Map(pages.map((p) => [p, sources.reduce((s, src) => s + (sp.get(src)?.get(p) || 0), 0)]));
  for (const p of pages) {
    let tracked = 0;
    for (const o of OUTCOMES) {
      const v = pageOutcomes.get(p)?.get(o) || 0;
      if (v > 0) {
        links.push({ source: idx.get("p:" + p)!, target: idx.get("o:" + o)!, value: v, kind: "outcome" });
        tracked += v;
      }
    }
    if (showNone) {
      const rest = Math.max(0, (pageUsers.get(p) || 0) - tracked);
      if (rest > 0) links.push({ source: idx.get("p:" + p)!, target: idx.get("o:" + NO_OUTCOME)!, value: rest, kind: "none" });
    }
  }
  const totals = {
    users,
    email: block.outcomes.filter((r) => r.outcome === "Email Submitted").reduce((s, r) => s + r.users, 0),
    plus: block.outcomes.filter((r) => r.outcome === "CT+ Sign Up").reduce((s, r) => s + r.users, 0),
  };
  return { nodes, links, totals, pageUsers, pageOutcomes };
}

/** Rows for the table view: one per (source, page), largest first. */
export function flowTableRows(block: FlowBlock): { source: string; page: string; users: number; email: number; plus: number }[] {
  const out = new Map<string, { source: string; page: string; users: number; email: number; plus: number }>();
  for (const r of block.landing) {
    const k = `${r.source}\u0000${r.page}`;
    const row = out.get(k) || { source: r.source, page: r.page, users: 0, email: 0, plus: 0 };
    row.users += r.users;
    out.set(k, row);
  }
  for (const r of block.outcomes) {
    const k = `${r.source}\u0000${r.page}`;
    const row = out.get(k) || { source: r.source, page: r.page, users: 0, email: 0, plus: 0 };
    if (r.outcome === "Email Submitted") row.email += r.users;
    else if (r.outcome === "CT+ Sign Up") row.plus += r.users;
    out.set(k, row);
  }
  return [...out.values()].sort((a, b) => b.users - a.users);
}
