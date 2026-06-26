"use client";

import { Snapshot } from "@/lib/snapshot";
import { fmtInt, fmtMoney } from "@/lib/format";

interface Props {
  snapshot: Snapshot;
  /** Stripe gross for the active window. */
  stripeGrossUsd: number;
  /** Sum of all manual revenue lines (absolute, not window-scoped). */
  manualRevenueUsd: number;
}

interface GoalRow {
  goal: string;
  current: string;
  sub?: string;
  target: string;
  pct: number;
}

// Provisional MRR target — derived from the 100-active-subscriber goal at the current
// revenue-per-subscriber. Recorded in GOALS.md; adjust there and here together.
const MRR_TARGET = 5_000;

export function GoalsTable({ snapshot, stripeGrossUsd, manualRevenueUsd }: Props) {
  const activeSubs = snapshot.snapshots.active_subscribers;
  const engaged = snapshot.snapshots.engaged_readers.engaged;
  const rankPos = snapshot.snapshots.keyword_overall.position;
  const mrr = snapshot.snapshots.current_mrr;
  const totalRevenue = stripeGrossUsd + manualRevenueUsd;
  const generated = new Date(snapshot.generated_at);

  const rows: GoalRow[] = [
    {
      goal: "Total revenue",
      current: fmtMoney(totalRevenue),
      sub: `${fmtMoney(stripeGrossUsd)} Stripe + ${fmtMoney(manualRevenueUsd)} manual`,
      target: "$120,000",
      pct: (totalRevenue / 120_000) * 100,
    },
    {
      goal: "Active Stripe subscribers",
      current: fmtInt(activeSubs),
      target: "100",
      pct: (activeSubs / 100) * 100,
    },
    {
      goal: "Monthly recurring revenue (MRR)",
      current: fmtMoney(mrr),
      sub: "provisional target",
      target: fmtMoney(MRR_TARGET),
      pct: (mrr / MRR_TARGET) * 100,
    },
    {
      goal: '#1 ranking for "personality test"',
      current: rankPos ? `Position ${rankPos.toFixed(1)}` : "(no impressions)",
      target: "Position #1",
      pct: rankPos ? Math.min(100, (1 / rankPos) * 100) : 0,
    },
    {
      goal: "Engaged subscribers (>40% open rate)",
      current: fmtInt(engaged),
      target: "200,000",
      pct: (engaged / 200_000) * 100,
    },
  ];

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-zinc-50 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400">
          <tr>
            <th className="text-left px-4 py-3 font-medium">Goal</th>
            <th className="text-left px-4 py-3 font-medium">Current</th>
            <th className="text-left px-4 py-3 font-medium">Target</th>
            <th className="text-left px-4 py-3 font-medium w-[40%]">Progress</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const clamped = Math.max(0, Math.min(100, r.pct));
            return (
              <tr key={r.goal} className="border-t border-zinc-100 dark:border-zinc-800/60">
                <td className="px-4 py-3">{r.goal}</td>
                <td className="px-4 py-3 font-medium">
                  {r.current}
                  {r.sub ? (
                    <span className="block text-xs font-normal text-zinc-400 dark:text-zinc-500">{r.sub}</span>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">{r.target}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500 dark:bg-green-400 rounded-full transition-all"
                        style={{ width: `${clamped}%` }}
                      />
                    </div>
                    <span className="text-xs tabular-nums text-zinc-600 dark:text-zinc-400 w-12 text-right">
                      {clamped.toFixed(0)}%
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="px-4 py-2 text-xs text-zinc-500 dark:text-zinc-400 border-t border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/30">
        As of {generated.toLocaleString()} · revenue scoped to the active window; subscribers, MRR, ranking, and
        engaged readers are current snapshot values.
      </div>
    </div>
  );
}
