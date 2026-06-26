"use client";

import { fmtInt, fmtPct } from "@/lib/format";
import { PeriodEntry } from "@/lib/snapshot";

interface Props {
  period: PeriodEntry;
}

interface Step {
  label: string;
  event: string;
  count: number;
}

export function FunnelTab({ period }: Props) {
  const daily = period.current.ga4_daily || [];
  const sum = (key: string) => daily.reduce((s, r) => s + ((r[key as keyof typeof r] as number) || 0), 0);

  const steps: Step[] = [
    { label: "First Visit", event: "first_visit", count: sum("first_visit") },
    { label: "Viewed Privacy Policy", event: "Viewed Privacy Policy", count: sum("modules_started") },
    { label: "Accepted Privacy Policy", event: "Accepted Privacy Policy", count: sum("accepted_privacy") },
    { label: "Submitted Email", event: "Submitted Email", count: sum("modules_finished") },
  ];

  const top = steps[0].count || 0;
  const maxBar = Math.max(...steps.map((s) => s.count), 1);

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">Funnel</h3>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        GA4 event funnel scoped to <strong>{period.start} &rarr; {period.end}</strong> ({period.days} days). Step-to-step
        rate is conversion from the previous step; overall is the share of First Visit.
      </p>

      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Step</th>
              <th className="text-right px-4 py-3 font-medium">Count</th>
              <th className="text-right px-4 py-3 font-medium">Step rate</th>
              <th className="text-right px-4 py-3 font-medium">Of First Visit</th>
              <th className="text-left px-4 py-3 font-medium w-[40%]">Volume</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((s, i) => {
              const prev = i === 0 ? null : steps[i - 1].count;
              const stepRate = prev ? s.count / prev : null;
              const overall = top ? s.count / top : null;
              const widthPct = (s.count / maxBar) * 100;
              return (
                <tr key={s.label} className="border-t border-zinc-100 dark:border-zinc-800/60">
                  <td className="px-4 py-3">
                    <span className="text-zinc-400 dark:text-zinc-500 tabular-nums mr-2">{i + 1}.</span>
                    {s.label}
                    <span className="block text-xs text-zinc-400 dark:text-zinc-500 ml-6">{s.event}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium tabular-nums">{fmtInt(s.count)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-zinc-600 dark:text-zinc-400">
                    {stepRate == null ? "—" : fmtPct(stepRate)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-zinc-600 dark:text-zinc-400">
                    {overall == null ? "—" : fmtPct(overall)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="h-5 bg-zinc-100 dark:bg-zinc-800 rounded-md overflow-hidden">
                      <div
                        className="h-full bg-blue-500 dark:bg-blue-400 rounded-md transition-all"
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        First Visit is the GA4 <code>first_visit</code> event (site-wide). The other three are tool-funnel events:
        Viewed Privacy Policy = tool landings, Accepted Privacy Policy = tool starts, Submitted Email = functional
        completion. Counts are summed from the daily GA4 series, so they follow the date filter above.
      </p>
    </div>
  );
}
