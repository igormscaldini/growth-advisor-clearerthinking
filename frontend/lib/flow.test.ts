import { test } from "node:test";
import assert from "node:assert/strict";
import { buildFlowGraph, flowTableRows, sliceFlowDaily, NO_OUTCOME, type FlowBlock, type FlowDailyRow } from "./flow.ts";

const block: FlowBlock = {
  landing: [
    { source: "Direct", page: "Tools", users: 100 },
    { source: "Organic Search", page: "Tools", users: 40 },
    { source: "Organic Search", page: "Home", users: 10 },
    { source: "Email", page: "Home", users: 0 }, // a zero row never becomes a link
  ],
  outcomes: [
    { source: "Direct", page: "Tools", outcome: "Email Submitted", users: 30 },
    { source: "Organic Search", page: "Tools", outcome: "Email Submitted", users: 12 },
    { source: "Direct", page: "Tools", outcome: "CT+ Sign Up", users: 1 },
  ],
};

test("buildFlowGraph: nodes in fixed order, links and totals worked by hand", () => {
  const g = buildFlowGraph(block, false, 0);
  assert.deepEqual(
    g.nodes.map((n) => n.id),
    ["s:Organic Search", "s:Direct", "s:Email", "p:Home", "p:Tools", "o:Email Submitted", "o:CT+ Sign Up"],
  );
  // Email only has a zero row: it is a node (present in the block) but owns no link
  assert.equal(g.links.filter((l) => l.src === "Email").length, 0);
  const id = (i: number) => g.nodes[i].id;
  const sourceLinks = g.links.filter((l) => l.kind === "source").map((l) => [id(l.source), id(l.target), l.value]);
  assert.deepEqual(sourceLinks, [
    ["s:Organic Search", "p:Home", 10],
    ["s:Organic Search", "p:Tools", 40],
    ["s:Direct", "p:Tools", 100],
  ]);
  const outcomeLinks = g.links.filter((l) => l.kind === "outcome").map((l) => [id(l.source), id(l.target), l.value]);
  assert.deepEqual(outcomeLinks, [
    ["p:Tools", "o:Email Submitted", 42], // 30 + 12
    ["p:Tools", "o:CT+ Sign Up", 1],
  ]);
  assert.deepEqual(g.totals, { users: 150, email: 42, plus: 1 });
  assert.equal(g.pageUsers.get("Tools"), 140);
});

test("buildFlowGraph: the no-outcome band is the remainder per page", () => {
  const g = buildFlowGraph(block, true, 0);
  const none = g.links.filter((l) => l.kind === "none").map((l) => [g.nodes[l.source].id, l.value]);
  assert.deepEqual(none, [
    ["p:Home", 10], // nothing tracked on Home
    ["p:Tools", 97], // 140 - 42 - 1
  ]);
  assert.ok(g.nodes.some((n) => n.id === "o:" + NO_OUTCOME));
});

test("buildFlowGraph: sources under the fold threshold merge into Other", () => {
  const g = buildFlowGraph(block, false, 0.1); // Organic Search is 50 of 150 (33%): kept
  assert.ok(g.nodes.some((n) => n.id === "s:Organic Search"));
  const g2 = buildFlowGraph(block, false, 0.5); // 33% < 50%: folds into Other, Direct (67%) stays
  assert.deepEqual(g2.nodes.filter((n) => n.col === 0).map((n) => n.name), ["Direct", "Other"]);
  const other = g2.links.find((l) => l.src === "Other" && g2.nodes[l.target].id === "p:Tools");
  assert.equal(other?.value, 40);
});

test("sliceFlowDaily sums only the days inside the range", () => {
  const rows: FlowDailyRow[] = [
    { date: "2026-11-01", source: "Direct", page: "Tools", users: 5, email_submitted: 2, plus_sign_up: 0 },
    { date: "2026-11-02", source: "Direct", page: "Tools", users: 7, email_submitted: 3, plus_sign_up: 1 },
    { date: "2026-11-03", source: "Direct", page: "Tools", users: 9, email_submitted: 0, plus_sign_up: 0 }, // outside
    { date: "2026-11-02", source: "Email", page: "Home", users: 4, email_submitted: 0, plus_sign_up: 0 },
  ];
  const b = sliceFlowDaily(rows, "2026-11-01", "2026-11-02");
  assert.deepEqual(b.landing, [
    { source: "Direct", page: "Tools", users: 12 },
    { source: "Email", page: "Home", users: 4 },
  ]);
  assert.deepEqual(b.outcomes, [
    { source: "Direct", page: "Tools", outcome: "Email Submitted", users: 5 },
    { source: "Direct", page: "Tools", outcome: "CT+ Sign Up", users: 1 },
  ]);
});

test("flowTableRows: one row per source and page, largest first, with both outcomes", () => {
  const rows = flowTableRows(block);
  assert.deepEqual(rows[0], { source: "Direct", page: "Tools", users: 100, email: 30, plus: 1 });
  assert.deepEqual(rows[1], { source: "Organic Search", page: "Tools", users: 40, email: 12, plus: 0 });
  assert.equal(rows.length, 4);
});
