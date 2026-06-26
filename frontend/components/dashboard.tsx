"use client";

import { useMemo, useState } from "react";
import { OverviewTab } from "./overview-tab";
import { ChannelsTab } from "./channels-tab";
import { MonetizationTab } from "./monetization-tab";
import { FunnelTab } from "./funnel-tab";
import { presetLabel } from "@/lib/format";
import { buildCustomPeriod } from "@/lib/aggregate";
import { PeriodEntry, PresetKey, Snapshot } from "@/lib/snapshot";

interface Props {
  snapshot: Snapshot;
}

type TabKey = "overview" | "funnel" | "channels" | "monetization";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "funnel", label: "Funnel" },
  { key: "channels", label: "Modules by Channel" },
  { key: "monetization", label: "Monetization" },
];

const PRESETS: PresetKey[] = ["7d", "30d", "90d", "thisMonth", "custom"];

export function Dashboard({ snapshot }: Props) {
  const [preset, setPreset] = useState<PresetKey>("30d");

  // Custom range state — default to the last 14 days (something different from any preset)
  const [customStart, setCustomStart] = useState<string>(() => {
    const d = new Date(snapshot.today);
    d.setDate(d.getDate() - 13);
    return d.toISOString().slice(0, 10);
  });
  const [customEnd, setCustomEnd] = useState<string>(snapshot.today);

  const [tab, setTab] = useState<TabKey>("overview");

  // Derive the active period
  const period: PeriodEntry = useMemo(() => {
    if (preset === "custom") {
      // Clamp the custom range to the available 90d daily window
      const min = snapshot.daily_window.start;
      const max = snapshot.daily_window.end;
      const start = customStart < min ? min : customStart > max ? max : customStart;
      const end = customEnd < min ? min : customEnd > max ? max : customEnd;
      const finalStart = start > end ? end : start;
      return buildCustomPeriod(snapshot, finalStart, end);
    }
    if (preset === "thisMonth") {
      // First-of-month → today (clamped to the 90d daily window).
      const min = snapshot.daily_window.start;
      const max = snapshot.daily_window.end;
      const todayStr = snapshot.today;
      const monthStart = `${todayStr.slice(0, 7)}-01`;
      const start = monthStart < min ? min : monthStart;
      const end = todayStr > max ? max : todayStr;
      return buildCustomPeriod(snapshot, start, end);
    }
    return snapshot.periods[preset];
  }, [preset, customStart, customEnd, snapshot]);

  const generated = useMemo(() => new Date(snapshot.generated_at), [snapshot.generated_at]);
  const generatedLocal = generated.toLocaleString();

  const dailyMin = snapshot.daily_window.start;
  const dailyMax = snapshot.daily_window.end;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h1 className="text-xl md:text-2xl font-bold">ClearerThinking Growth Dashboard</h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              {period.start} → {period.end} · {period.days} days · Last refreshed: {generatedLocal}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div role="tablist" className="inline-flex rounded-lg border border-zinc-200 dark:border-zinc-800 p-0.5 bg-zinc-100 dark:bg-zinc-900">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  role="tab"
                  aria-selected={preset === p}
                  onClick={() => setPreset(p)}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    preset === p
                      ? "bg-white dark:bg-zinc-800 shadow-sm font-medium"
                      : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200"
                  }`}
                >
                  {presetLabel(p)}
                </button>
              ))}
            </div>
            {preset === "custom" && (
              <div className="flex items-center gap-2 text-sm">
                <label className="text-zinc-500 dark:text-zinc-400">From</label>
                <input
                  type="date"
                  value={customStart}
                  min={dailyMin}
                  max={dailyMax}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="border border-zinc-200 dark:border-zinc-800 rounded-md px-2 py-1 bg-white dark:bg-zinc-900"
                />
                <label className="text-zinc-500 dark:text-zinc-400">to</label>
                <input
                  type="date"
                  value={customEnd}
                  min={dailyMin}
                  max={dailyMax}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="border border-zinc-200 dark:border-zinc-800 rounded-md px-2 py-1 bg-white dark:bg-zinc-900"
                />
              </div>
            )}
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 -mb-px">
          <nav role="tablist" className="flex gap-1 overflow-x-auto">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={tab === t.key}
                onClick={() => setTab(t.key)}
                className={`px-4 py-2.5 text-sm border-b-2 transition-colors ${
                  tab === t.key
                    ? "border-green-600 dark:border-green-400 font-medium text-zinc-900 dark:text-zinc-100"
                    : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {preset === "custom" && (
          <p className="mb-4 text-xs text-zinc-500 dark:text-zinc-400 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-md px-3 py-2">
            Custom ranges are limited to the snapshot window: {dailyMin} → {dailyMax}. Prior-period
            comparison only shown when the prior window also fits inside this range.
          </p>
        )}
        {tab === "overview" && <OverviewTab snapshot={snapshot} period={period} />}
        {tab === "funnel" && <FunnelTab period={period} snapshot={snapshot} />}
        {tab === "channels" && <ChannelsTab period={period} />}
        {tab === "monetization" && <MonetizationTab snapshot={snapshot} period={period} />}
      </main>

      <footer className="max-w-7xl mx-auto px-6 pt-2 pb-10 text-xs text-zinc-500 dark:text-zinc-400">
        Sources: GA4 · Stripe · beehiiv · Search Console · Google Ads. Snapshot regenerated every 30 minutes by a
        GitHub Actions cron. All times in UTC.
      </footer>
    </div>
  );
}
