"use client";

import { KpiCard } from "./kpi-card";
import { GoalsTable } from "./goals-table";
import { DailyBars } from "./daily-bars";
import { fmtInt, fmtMoney, fmtPct, variance } from "@/lib/format";
import { PeriodEntry, Snapshot } from "@/lib/snapshot";

interface Props {
  snapshot: Snapshot;
  period: PeriodEntry;
}

export function OverviewTab({ snapshot, period }: Props) {
  const cur = period.current;
  const pri = period.prior;

  const fillRange = (
    rows: { date: string; [k: string]: string | number | null }[],
    key: string,
  ): { date: string; value: number | null }[] => {
    const map = new Map<string, number | null>();
    rows.forEach((r) => {
      const v = r[key];
      map.set(r.date, typeof v === "number" ? v : null);
    });
    const out: { date: string; value: number | null }[] = [];
    const start = new Date(period.start);
    const end = new Date(period.end);
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const iso = d.toISOString().slice(0, 10);
      out.push({ date: iso, value: map.has(iso) ? (map.get(iso) ?? 0) : 0 });
    }
    return out;
  };

  // 1. Modules Finished
  const modulesFinishedDaily = fillRange(cur.ga4_daily || [], "modules_finished");
  const modulesFinished = cur.ga4.modules_finished;

  // 2. New Subscribers (beehiiv daily) + Unsubscribers (derived from per_campaign by date)
  const unsubsByDate = new Map<string, number>();
  for (const c of cur.bh.per_campaign || []) {
    unsubsByDate.set(c.date, (unsubsByDate.get(c.date) || 0) + (c.unsubs || 0));
  }
  const newSubsDaily = (cur.new_subs_daily.daily || []).map((d) => ({
    date: d.date,
    value: d.count,
    unsubs: unsubsByDate.get(d.date) || 0,
  }));
  const newSubsTotal = cur.new_subs_daily.total;
  const newSubsCapped = cur.new_subs_daily.capped;
  const unsubsTotal = [...unsubsByDate.values()].reduce((s, v) => s + v, 0);

  // 2b. Total Subscribers — derived. Anchor at current beehiiv total (snapshot only — same value
  // across all periods), walk backward day-by-day using (new − unsubs) deltas.
  const totalSubsAnchor = snapshot.snapshots.total_subscribers || cur.bh.total_subscribers || 0;
  const totalSubsDaily = (() => {
    const days = (cur.new_subs_daily.daily || []).map((d) => d.date);
    if (!days.length || !totalSubsAnchor) return [];
    const newByDate = new Map<string, number>();
    for (const d of cur.new_subs_daily.daily || []) newByDate.set(d.date, d.count || 0);
    // Walk forward from the earliest day. Start so that the last day equals the anchor.
    const sorted = [...days].sort();
    const netChanges = sorted.map((d) => (newByDate.get(d) || 0) - (unsubsByDate.get(d) || 0));
    const totalNet = netChanges.reduce((s, v) => s + v, 0);
    let running = totalSubsAnchor - totalNet;
    const out: { date: string; value: number }[] = [];
    for (let i = 0; i < sorted.length; i++) {
      running += netChanges[i];
      out.push({ date: sorted[i], value: running });
    }
    return out;
  })();
  const priorTotalSubs = totalSubsDaily.length ? totalSubsDaily[0].value : null;

  // 3. New (paid) Stripe subscribers — window-scoped
  const newStripeSubsDaily = (cur.new_stripe_subs?.daily || []).map((d) => ({ date: d.date, value: d.count }));
  const newStripeSubsTotal = cur.new_stripe_subs?.total ?? 0;

  // 4. Unsubscribe Rate
  const unsubDaily = (cur.bh_daily_rates || []).map((d) => ({ date: d.date, value: d.unsubscribe_rate }));

  // 5. Total Revenue
  const revDaily = (cur.stripe_m.daily || []).map((d) => ({ date: d.date, value: d.revenue }));
  const grossRev = cur.stripe_m.gross_usd;
  const manualRevenueTotal = Object.values(snapshot.manual_revenue.lines)
    .flat()
    .reduce((s, i) => s + i.amount, 0);

  // 6. MRR
  const mrrDaily = (cur.mrr_history || []).map((d) => ({ date: d.date, value: d.mrr }));
  const currentMrr = snapshot.snapshots.current_mrr;
  const priorMrrEnd = pri.mrr_history?.length ? pri.mrr_history[pri.mrr_history.length - 1].mrr : null;

  // 8. Cognitive Sales
  const cogDaily = (cur.cog_sales.daily || []).map((d) => ({ date: d.date, value: d.count }));

  // 9. PDF Sales
  const pdfDaily = (cur.pdf_sales.daily || []).map((d) => ({ date: d.date, value: d.count }));

  // 11. GSC keyword position (do NOT fill gaps — missing = no impressions)
  const kwDailyRaw = (cur.kw_pos.daily || []).map((d) => ({ date: d.date, value: d.position }));

  return (
    <div className="space-y-5">
      <KpiCard
        label="Modules Finished"
        value={fmtInt(modulesFinished)}
        helpText={'GA4 • count of "Submitted Email" event in window.'}
        data={modulesFinishedDaily}
        color="#16A34A"
        yLabel="Submissions / day"
        delta={variance(modulesFinished, pri.ga4.modules_finished)}
        comparisonNote={`vs prior ${period.days}d`}
      />

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5 shadow-sm">
        <div className="flex items-baseline justify-between mb-3">
          <h3
            className="text-sm font-semibold text-zinc-700 dark:text-zinc-300"
            title="beehiiv • new subscriptions created in window vs unsubscribers (sum of campaign unsubs by send date)."
          >
            New Subscribers
          </h3>
          <span
            className="text-[10px] text-zinc-400 dark:text-zinc-500 cursor-help"
            title={
              newSubsCapped
                ? "beehiiv • capped at pagination limit; actual may be higher. Unsubscribers = sum of campaign unsubs by send date."
                : "beehiiv • subscriptions created in window, deduped by id. Unsubscribers = sum of campaign unsubs by send date."
            }
          >
            ⓘ
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_3fr] gap-4 items-center">
          <div>
            <div className="text-3xl font-bold leading-none">
              {fmtInt(newSubsTotal)}
              {newSubsCapped ? "+" : ""}
            </div>
            <div className="mt-1 text-sm font-medium text-red-600 dark:text-red-400">
              −{fmtInt(unsubsTotal)} unsubscribers
            </div>
            {(() => {
              const delta = variance(newSubsTotal, pri.new_subs_daily.total);
              if (delta == null) {
                return (
                  <div className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                    vs prior {period.days}d
                  </div>
                );
              }
              const sign = delta > 0 ? "▲" : "▼";
              const isFlat = Math.abs(delta) < 0.05;
              const color = isFlat
                ? "text-zinc-500 dark:text-zinc-400"
                : delta > 0
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400";
              return (
                <div className={`mt-2 text-sm font-medium ${color}`}>
                  {sign} {Math.abs(delta).toFixed(1)}%{" "}
                  <span className="font-normal text-zinc-500 dark:text-zinc-400">vs prior {period.days}d</span>
                </div>
              );
            })()}
          </div>
          <DailyBars data={newSubsDaily.map((d) => ({ date: d.date, new: d.value, unsubs: d.unsubs }))} />
        </div>
      </div>

      <KpiCard
        label="Total Subscribers"
        value={fmtInt(totalSubsAnchor)}
        helpText="beehiiv • current active subscribers (snapshot). Daily curve reconstructed from (new − unsubscribers) deltas, anchored at the latest snapshot value."
        data={totalSubsDaily.map((d) => ({ date: d.date, value: d.value }))}
        color="#0EA5E9"
        yLabel="Total subscribers"
        delta={variance(totalSubsAnchor, priorTotalSubs)}
        comparisonNote={`vs start of window`}
      />

      <KpiCard
        label="Unsubscribe Rate"
        value={fmtPct(cur.bh.unsubscribe_rate)}
        helpText="beehiiv • total unsubscribes / total recipients in window."
        data={unsubDaily}
        color="#DC2626"
        yLabel="Rate"
        isPercent
        delta={variance(cur.bh.unsubscribe_rate, pri.bh.unsubscribe_rate)}
        deltaInverse
        comparisonNote={`vs prior ${period.days}d`}
      />

      <KpiCard
        label="Total Revenue (Gross)"
        value={fmtMoney(grossRev)}
        helpText="Stripe • gross volume = sum of all successful charge amounts (pre-refund) in window."
        data={revDaily}
        color="#16A34A"
        yLabel="Revenue ($)"
        delta={variance(grossRev, pri.stripe_m.gross_usd)}
        comparisonNote={`vs prior ${period.days}d`}
        footer={<span>Note: Stripe revenue only — excludes manual lines (MLA, sponsorships, affiliates).</span>}
      />

      <KpiCard
        label="MRR"
        value={fmtMoney(currentMrr)}
        helpText="Stripe • current MRR snapshot. Curve reconstructs daily MRR from active+canceled subscription history."
        data={mrrDaily}
        color="#4F8BF9"
        yLabel="MRR ($)"
        delta={variance(currentMrr, priorMrrEnd)}
        comparisonNote="vs MRR at end of prior window"
      />

      <KpiCard
        label="New Subscribers"
        value={fmtInt(newStripeSubsTotal)}
        helpText="Stripe • new paid subscriptions created in the selected window (by subscription created date). Excludes churn/cancellations."
        data={newStripeSubsDaily}
        color="#0EA5E9"
        yLabel="New subs / day"
        delta={variance(newStripeSubsTotal, pri.new_stripe_subs?.total ?? null)}
        comparisonNote={`vs prior ${period.days}d`}
      />

      <KpiCard
        label="Cognitive Assessment Sales"
        value={fmtInt(cur.cog_sales.total)}
        helpText="Stripe • count of successful charges with amount $35.00 or $17.50 in window."
        data={cogDaily}
        color="#F5A524"
        yLabel="Sales / day"
        delta={variance(cur.cog_sales.total, pri.cog_sales.total)}
        comparisonNote={`vs prior ${period.days}d`}
      />

      <KpiCard
        label="Personality Test PDF Sales"
        value={fmtInt(cur.pdf_sales.total)}
        helpText="Stripe • count of $9.00 charges, excluding subscriptions."
        data={pdfDaily}
        color="#A855F7"
        yLabel="Sales / day"
        delta={variance(cur.pdf_sales.total, pri.pdf_sales.total)}
        comparisonNote={`vs prior ${period.days}d`}
      />

      <KpiCard
        label='GSC Ranking — "personality test"'
        value={cur.kw_pos.avg_position ? `#${cur.kw_pos.avg_position.toFixed(1)}` : "—"}
        helpText='Search Console • impression-weighted avg position. Lower = better. GSC has a 3-day data lag.'
        data={kwDailyRaw}
        color="#8B5CF6"
        yLabel="Avg position (lower = better)"
        delta={variance(cur.kw_pos.avg_position, pri.kw_pos.avg_position)}
        deltaInverse
        comparisonNote={`vs prior ${period.days}d`}
      />

      <section className="pt-4">
        <h2 className="text-lg font-semibold mb-2">Progress against goals</h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">
          Goals defined in{" "}
          <a
            href="https://github.com/igormscaldini/growth-advisor-clearerthinking/blob/main/GOALS.md"
            className="underline hover:text-zinc-700 dark:hover:text-zinc-200"
          >
            GOALS.md
          </a>
          . Update that file to change targets.
        </p>
        <GoalsTable snapshot={snapshot} stripeGrossUsd={grossRev} manualRevenueUsd={manualRevenueTotal} />
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
          Ranking % uses the formula <code>1 / current_position × 100</code> (position 1 → 100%, position 2 →
          50%). Other metrics use <code>current / target × 100</code>.
        </p>
      </section>
    </div>
  );
}
