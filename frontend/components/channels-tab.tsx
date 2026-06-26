"use client";

import { HorizontalBarChart } from "./horizontal-bar-chart";
import { PeriodEntry } from "@/lib/snapshot";

interface Props {
  period: PeriodEntry;
}

export function ChannelsTab({ period }: Props) {
  const channels = period.current.modules_by_channel;
  const campaigns = period.current.modules_by_campaign;
  const chTotal = channels.reduce((s, c) => s + c.count, 0);
  const campTotal = campaigns.reduce((s, c) => s + c.count, 0);

  return (
    <div className="space-y-8">
      <section>
        <h3 className="text-lg font-semibold">
          Modules Finished by Channel <span className="font-normal text-zinc-500">· Source: GA4</span>
        </h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          Count of <code>Submitted Email</code> events grouped by <code>sessionDefaultChannelGroup</code> in{" "}
          {period.start} → {period.end}.
        </p>

        {channels.length === 0 ? (
          <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">No submissions recorded in this window.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 mt-4 mb-4 max-w-md">
              <Stat label="Total submissions" value={chTotal.toLocaleString("en-US")} />
              <Stat label="# channels w/ submissions" value={String(channels.length)} />
            </div>
            <HorizontalBarChart data={channels.map((c) => ({ label: c.channel, value: c.count }))} />

            <h4 className="text-sm font-semibold mt-6 mb-2">Detail by channel</h4>
            <SimpleTable
              headers={["Channel", "Submissions", "% of total"]}
              rows={channels.map((c) => [
                c.channel,
                c.count.toLocaleString("en-US"),
                `${((c.count / chTotal) * 100).toFixed(1)}%`,
              ])}
            />
          </>
        )}
      </section>

      <hr className="border-zinc-200 dark:border-zinc-800" />

      <section>
        <h3 className="text-lg font-semibold">
          Modules Finished by Campaign <span className="font-normal text-zinc-500">· Source: GA4</span>
        </h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          Count of <code>Submitted Email</code> events grouped by <code>sessionCampaignName</code> in {period.start}{" "}
          → {period.end}.
        </p>

        {campaigns.length === 0 ? (
          <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">
            No campaign-attributed submissions in this window.
          </p>
        ) : (
          <>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-3 mb-3">
              Total campaign-attributed submissions: <strong>{campTotal.toLocaleString("en-US")}</strong> across{" "}
              <strong>{campaigns.length}</strong> campaigns
            </p>
            <SimpleTable
              headers={["Campaign", "Submissions", "% of total"]}
              rows={campaigns.map((c) => [
                c.campaign,
                c.count.toLocaleString("en-US"),
                `${((c.count / campTotal) * 100).toFixed(1)}%`,
              ])}
            />
          </>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 px-4 py-3 bg-white dark:bg-zinc-950">
      <div className="text-xs text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  );
}

function SimpleTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 max-h-[480px] overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="bg-zinc-50 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 sticky top-0">
          <tr>
            {headers.map((h) => (
              <th key={h} className="text-left px-4 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800/60">
              {r.map((cell, j) => (
                <td key={j} className="px-4 py-2 tabular-nums">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
