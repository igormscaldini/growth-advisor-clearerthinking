"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { sankey, sankeyJustify, sankeyLinkHorizontal } from "d3-sankey";
import type { SankeyLink, SankeyNode } from "d3-sankey";
import { fmtInt } from "@/lib/format";
import { PeriodEntry } from "@/lib/snapshot";
import { buildFlowGraph, flowTableRows, NO_OUTCOME, SOURCE_ORDER, type FlowLink, type FlowNode } from "@/lib/flow";

interface Props {
  period: PeriodEntry;
}

type LaidNode = SankeyNode<FlowNode, FlowLink> & { ly?: number };
type LaidLink = SankeyLink<FlowNode, FlowLink>;

const HEIGHT = 520;
const ML = 150; // room for source labels
const MR = 200; // room for outcome labels and the Stripe boxes
const MT = 8;
const MB = 84;

const share = (a: number, b: number) => (b ? `${((100 * a) / b).toFixed(a / b < 0.01 ? 2 : 1)}%` : "0%");
const sourceColor = (name: string) => {
  const i = SOURCE_ORDER.indexOf(name);
  return `var(--flow-${i < 0 ? 8 : i + 1})`;
};

export function FlowTab({ period }: Props) {
  const cur = period.current;
  const block = cur.flow;
  const [showNone, setShowNone] = useState(false);
  const [view, setView] = useState<"diagram" | "table">("diagram");
  const [width, setWidth] = useState(960);
  const [tip, setTip] = useState<{ x: number; y: number; lines: string[] } | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => setWidth(Math.max(720, el.clientWidth));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const graph = useMemo(() => (block ? buildFlowGraph(block, showNone) : null), [block, showNone]);

  const laid = useMemo(() => {
    if (!graph || graph.links.length === 0) return null;
    const gen = sankey<FlowNode, FlowLink>()
      .nodeWidth(12)
      .nodePadding(12)
      .nodeAlign(sankeyJustify)
      .nodeSort(() => 0) // a stable no-op comparator keeps the fixed source/page order (the typings reject null)
      .extent([
        [ML, MT],
        [width - MR, HEIGHT - MB],
      ]);
    const g = gen({ nodes: graph.nodes.map((n) => ({ ...n })), links: graph.links.map((l) => ({ ...l })) });
    // Labels: dodge apart per column (14px pitch) and remember where each ended up.
    for (const col of [0, 1, 2]) {
      const ns = (g.nodes as LaidNode[]).filter((n) => n.col === col).sort((a, b) => (a.y0 ?? 0) - (b.y0 ?? 0));
      let y = -Infinity;
      for (const n of ns) {
        n.ly = Math.max(((n.y0 ?? 0) + (n.y1 ?? 0)) / 2, y + 14);
        y = n.ly;
      }
      const over = ns.length ? (ns[ns.length - 1].ly ?? 0) - (HEIGHT - MB) : 0;
      if (over > 0) {
        let yb = Infinity;
        for (const n of [...ns].reverse()) {
          n.ly = Math.min((n.ly ?? 0) - over, yb - 14);
          yb = n.ly;
        }
      }
    }
    return g;
  }, [graph, width]);

  const rows = useMemo(() => (block ? flowTableRows(block) : []), [block]);
  const stripe = {
    cognitive: cur.cog_sales?.total ?? 0,
    pdf: cur.pdf_sales?.total ?? 0,
    subs: cur.new_stripe_subs?.total ?? 0,
  };

  const showTip = (e: React.MouseEvent, lines: string[]) => {
    const r = box.current?.getBoundingClientRect();
    setTip({ x: e.clientX - (r?.left ?? 0) + 14, y: e.clientY - (r?.top ?? 0) + 14, lines });
  };

  if (!block || !graph) {
    return (
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Flow</h3>
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5 shadow-sm text-sm text-zinc-500 dark:text-zinc-400">
          Flow data arrives with the next snapshot refresh (first-touch source → landing page → outcome).
        </div>
      </div>
    );
  }

  const t = graph.totals;
  const kpis: [string, string, string][] = [
    ["Users", fmtInt(t.users), "GA4 · web sessions with a landing page"],
    ["Email Submitted", fmtInt(t.email), `${share(t.email, t.users)} of users · a tool finished`],
    ["CT+ Sign Up", fmtInt(t.plus), `GA4 plus_sign_up · Stripe: ${fmtInt(stripe.subs)} new subscriptions`],
    ["Cognitive Assessment sales", fmtInt(stripe.cognitive), "Stripe · path not trackable yet"],
    ["Personality PDF sales", fmtInt(stripe.pdf), "Stripe · path not trackable yet"],
  ];
  const linkPath = sankeyLinkHorizontal();
  const nodeFill = (n: LaidNode) =>
    n.col === 0 ? sourceColor(n.name) : n.name === NO_OUTCOME ? "var(--flow-none)" : n.col === 2 ? "var(--flow-outcome)" : "var(--flow-node)";

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-lg font-semibold">Flow</h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          How we first met each user, which page they landed on in the window, and what they did there. Band width = unique
          users. Hover any band or box for the numbers.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {kpis.map(([l, v, c]) => (
          <div key={l} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-4 py-3 shadow-sm">
            <div className="text-xs text-zinc-500 dark:text-zinc-400">{l}</div>
            <div className="text-2xl font-bold leading-tight mt-0.5">{v}</div>
            <div className="text-[11px] text-zinc-400 dark:text-zinc-500 mt-0.5">{c}</div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3 text-sm">
          <div role="tablist" className="inline-flex rounded-md border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            {(["diagram", "table"] as const).map((v) => (
              <button
                key={v}
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className={`px-3 py-1 text-sm ${view === v ? "bg-zinc-100 dark:bg-zinc-800 font-medium" : "text-zinc-600 dark:text-zinc-400"}`}
              >
                {v === "diagram" ? "Diagram" : "Table"}
              </button>
            ))}
          </div>
          <label className="inline-flex items-center gap-2 text-zinc-600 dark:text-zinc-400 cursor-pointer">
            <input type="checkbox" checked={showNone} onChange={(e) => setShowNone(e.target.checked)} />
            Show users with no tracked outcome
          </label>
        </div>

        {view === "diagram" ? (
          <div ref={box} className="relative">
            <div className="grid grid-cols-3 text-[11px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">
              <span>First-touch source</span>
              <span className="text-center">Landing page</span>
              <span className="text-right">Outcome</span>
            </div>
            {laid ? (
              <svg viewBox={`0 0 ${width} ${HEIGHT}`} className="block w-full h-auto" onMouseLeave={() => setTip(null)}>
                <g fill="none">
                  {(laid.links as LaidLink[]).map((l, i) => {
                    const s = l.source as unknown as LaidNode;
                    const d = l.target as unknown as LaidNode;
                    const stroke = l.kind === "source" ? sourceColor(l.src || "") : l.kind === "outcome" ? "var(--flow-outcome)" : "var(--flow-none)";
                    return (
                      <path
                        key={i}
                        d={linkPath(l) ?? undefined}
                        stroke={stroke}
                        strokeOpacity={l.kind === "none" ? 0.45 : 0.55}
                        strokeWidth={Math.max(1.5, l.width ?? 0)}
                        onMouseMove={(e) =>
                          showTip(e, [
                            `${s.name} → ${d.name}`,
                            `${fmtInt(l.value)} users`,
                            `${share(l.value, s.value ?? 0)} of ${s.name} · ${share(l.value, d.value ?? 0)} of ${d.name}`,
                          ])
                        }
                      />
                    );
                  })}
                </g>
                <g>
                  {(laid.nodes as LaidNode[]).map((n) => (
                    <rect
                      key={n.id}
                      x={n.x0}
                      y={n.y0}
                      width={(n.x1 ?? 0) - (n.x0 ?? 0)}
                      height={Math.max(2, (n.y1 ?? 0) - (n.y0 ?? 0))}
                      rx={2}
                      fill={nodeFill(n)}
                      onMouseMove={(e) => {
                        const lines = [`${n.name}`, `${fmtInt(n.value ?? 0)} users · ${share(n.value ?? 0, t.users)} of all`];
                        if (n.col === 1) {
                          const em = graph.pageOutcomes.get(n.name)?.get("Email Submitted") || 0;
                          const pl = graph.pageOutcomes.get(n.name)?.get("CT+ Sign Up") || 0;
                          lines.push(`Email Submitted ${fmtInt(em)} (${share(em, n.value ?? 0)}) · CT+ ${fmtInt(pl)}`);
                        }
                        showTip(e, lines);
                      }}
                    />
                  ))}
                </g>
                <g className="text-[12px]" style={{ paintOrder: "stroke", strokeLinejoin: "round" }}>
                  {(laid.nodes as LaidNode[]).map((n) => {
                    const right = n.col === 2;
                    const x = right ? (n.x1 ?? 0) + 8 : (n.x0 ?? 0) - 8;
                    const mid = ((n.y0 ?? 0) + (n.y1 ?? 0)) / 2;
                    const ly = n.ly ?? mid;
                    const moved = Math.abs(ly - mid) > 7;
                    return (
                      <g key={n.id}>
                        {moved ? (
                          <path
                            d={`M${right ? n.x1 : n.x0},${mid} H${right ? (n.x1 ?? 0) + 4 : (n.x0 ?? 0) - 4} V${ly}`}
                            fill="none"
                            stroke="var(--flow-leader)"
                            strokeWidth={1}
                          />
                        ) : null}
                        <text
                          x={x}
                          y={ly}
                          dy="0.35em"
                          textAnchor={right ? "start" : "end"}
                          className="fill-zinc-900 dark:fill-zinc-100 stroke-white dark:stroke-zinc-950"
                          strokeWidth={3}
                        >
                          {n.name}
                          <tspan className="fill-zinc-500 dark:fill-zinc-400"> {fmtInt(n.value ?? 0)}</tspan>
                        </text>
                      </g>
                    );
                  })}
                </g>
                {/* Stripe-only outcomes: counted in Stripe, no GA4 path (purchases arrive with source "(not set)"). */}
                <g className="text-[12px]">
                  {(
                    [
                      ["Cognitive Assessment", stripe.cognitive],
                      ["Personality PDF", stripe.pdf],
                    ] as [string, number][]
                  ).map(([name, n], i) => {
                    const bx = width - MR + 8;
                    const by = HEIGHT - MB + 12 + i * 34;
                    return (
                      <g key={name}>
                        <rect x={bx - 20} y={by} width={12} height={24} rx={2} fill="none" stroke="var(--flow-outcome)" strokeDasharray="3 2" />
                        <text x={bx} y={by + 9} className="fill-zinc-900 dark:fill-zinc-100">
                          {name}
                          <tspan className="fill-zinc-500 dark:fill-zinc-400"> {fmtInt(n)}</tspan>
                        </text>
                        <text x={bx} y={by + 22} className="fill-zinc-400 dark:fill-zinc-500 text-[10px]">
                          Stripe sales · path not trackable yet
                        </text>
                      </g>
                    );
                  })}
                  <text x={ML} y={HEIGHT - MB + 21} className="fill-zinc-400 dark:fill-zinc-500 text-[11px]">
                    Band width = users (1.5px minimum so rare outcomes stay visible). Dashed boxes: counted in Stripe, no GA4 path.
                  </text>
                </g>
              </svg>
            ) : (
              <p className="text-sm text-zinc-500 dark:text-zinc-400 py-8 text-center">No users in this window.</p>
            )}
            {tip ? (
              <div
                className="pointer-events-none absolute z-10 rounded-md bg-zinc-900 text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900 text-xs px-2 py-1.5 max-w-xs shadow"
                style={{ left: tip.x, top: tip.y }}
              >
                {tip.lines.map((l, i) => (
                  <div key={i} className={i === 0 ? "font-semibold" : ""}>
                    {l}
                  </div>
                ))}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400 mt-3">
              {graph.nodes
                .filter((n) => n.col === 0)
                .map((n) => (
                  <span key={n.id} className="inline-flex items-center gap-1.5">
                    <i className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: sourceColor(n.name) }} />
                    {n.name}
                  </span>
                ))}
              <span className="inline-flex items-center gap-1.5">
                <i className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: "var(--flow-outcome)" }} />
                Tracked outcome
              </span>
              <span className="inline-flex items-center gap-1.5">
                <i className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: "var(--flow-none)" }} />
                No tracked outcome
              </span>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">First-touch source</th>
                  <th className="text-left px-3 py-2 font-medium">Landing page</th>
                  <th className="text-right px-3 py-2 font-medium">Users</th>
                  <th className="text-right px-3 py-2 font-medium">Email Submitted</th>
                  <th className="text-right px-3 py-2 font-medium">Rate</th>
                  <th className="text-right px-3 py-2 font-medium">CT+ Sign Up</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.source}|${r.page}`} className="border-t border-zinc-100 dark:border-zinc-800/60">
                    <td className="px-3 py-2">{r.source}</td>
                    <td className="px-3 py-2">{r.page}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtInt(r.users)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtInt(r.email)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{share(r.email, r.users)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtInt(r.plus)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
        <p>
          <strong>Users</strong>: GA4 unique users by first-user default channel group (the channel of their first ever session) and
          the landing page of their sessions in the window. Someone who landed on two page categories is counted under both; for
          custom ranges days are summed, as on every other tab. Sessions with no landing page (the One Helpful Idea open pixel,
          server-side purchase events) are not shown.
        </p>
        <p>
          <strong>Sources</strong>: Paid Media = Paid Search, Paid Social, Paid Other, Display and Cross-network; Social = Organic Social
          + Organic Video; Other = Unassigned and the rest (sources under 0.4% of users fold in). <strong>Pages</strong>: Home = the www
          homepage; Articles = every /post/ page; Tools = programs.* tool pages, the tools gallery and the www copy of the Who Attracts
          You study; Other = coaching and CT+ pages, podcast, list pages.
        </p>
        <p>
          <strong>Outcomes</strong>: Email Submitted = GA4 &quot;Submitted Email&quot; in that session (a tool finished); CT+ Sign Up =
          GA4 plus_sign_up (the thank-you page). Stripe counts more new subscriptions (member dashboard, article paywall, untracked
          sessions). Cognitive Assessment and Personality PDF sales are Stripe counts: their GA4 purchase events arrive with source
          &quot;(not set)&quot;, so they cannot be placed on a path until checkout carries the GA client id.
        </p>
      </div>
    </div>
  );
}
