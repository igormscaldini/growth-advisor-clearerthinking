"use client";

import { useMemo, useState } from "react";
import { OverviewTab } from "./overview-tab";
import { ChannelsTab } from "./channels-tab";
import { MonetizationTab } from "./monetization-tab";
import { presetLabel } from "@/lib/format";
import { PresetKey, Snapshot } from "@/lib/snapshot";

interface Props {
  snapshot: Snapshot;
}

type TabKey = "overview" | "channels" | "monetization";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "📊 Overview" },
  { key: "channels", label: "🎯 Modules by Channel" },
  { key: "monetization", label: "💰 Monetization" },
];

const PRESETS: PresetKey[] = ["7d", "30d", "90d"];

export function Dashboard({ snapshot }: Props) {
  const [preset, setPreset] = useState<PresetKey>("30d");
  const [tab, setTab] = useState<TabKey>("overview");

  const period = snapshot.periods[preset];
  const generated = useMemo(() => new Date(snapshot.generated_at), [snapshot.generated_at]);
  const generatedLocal = generated.toLocaleString();

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl md:text-2xl font-bold">📊 ClearerThinking Growth Dashboard</h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              {period.start} → {period.end} · {period.days} days · Last refreshed: {generatedLocal}
            </p>
          </div>
          <div className="flex items-center gap-2">
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
        {tab === "overview" && <OverviewTab snapshot={snapshot} period={period} />}
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
