"use client";

import { fmtMoney } from "@/lib/format";
import { PeriodEntry, Snapshot } from "@/lib/snapshot";

interface Props {
  snapshot: Snapshot;
  period: PeriodEntry;
}

export function MonetizationTab({ snapshot, period }: Props) {
  const cat = period.current.revenue_cat;

  const stripeRows = [
    {
      source: "Revenue from Subscriptions",
      detail: "Stripe — invoice-attached charges + descriptions starting with 'Subscription'",
      revenue: cat.subscriptions,
    },
    {
      source: "Revenue from Personality Test PDF",
      detail: "Stripe — $9.00 charges (excl. subscriptions)",
      revenue: cat.pdf,
    },
    {
      source: "Revenue from Cognitive Assessment",
      detail: "Stripe — $35.00 or $17.50 charges (excl. subscriptions)",
      revenue: cat.cognitive,
    },
  ];

  const manualRows = Object.entries(snapshot.manual_revenue.lines).map(([label, items]) => ({
    source: label,
    detail: `Manual — ${items.map((i) => `${i.source}: ${fmtMoney(i.amount)}`).join("; ")}`,
    revenue: items.reduce((s, i) => s + i.amount, 0),
  }));

  const all = [...stripeRows, ...manualRows];
  const total = all.reduce((s, r) => s + r.revenue, 0);
  const sources = Object.keys(snapshot.manual_revenue.lines).join(", ");

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">Monetization Breakdown</h3>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Stripe lines scoped to <strong>{period.start} → {period.end}</strong>. Manual lines are absolute totals (not
        window-scoped).
      </p>

      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Source</th>
              <th className="text-left px-4 py-3 font-medium">Detail</th>
              <th className="text-right px-4 py-3 font-medium">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {all.map((r) => (
              <tr key={r.source} className="border-t border-zinc-100 dark:border-zinc-800/60">
                <td className="px-4 py-2 font-medium">{r.source}</td>
                <td className="px-4 py-2 text-zinc-600 dark:text-zinc-400">{r.detail}</td>
                <td className="px-4 py-2 text-right tabular-nums">{fmtMoney(r.revenue)}</td>
              </tr>
            ))}
            <tr className="border-t border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/40 font-semibold">
              <td className="px-4 py-3">Total revenue</td>
              <td className="px-4 py-3" />
              <td className="px-4 py-3 text-right tabular-nums">{fmtMoney(total)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Manual values (<strong>{sources}</strong>) last updated by Igor:{" "}
        <strong>{snapshot.manual_revenue.last_updated}</strong>. Update via the <code>MANUAL_REVENUE</code> constant in{" "}
        <code>fetch_snapshot.py</code>.
      </p>
    </div>
  );
}
