/**
 * Build a synthetic PeriodEntry for a user-picked [start, end] range, using:
 *   - the 90d period's daily KPI series (sliced to the range)
 *   - the daily_90d block's channel / campaign / revenue_category breakdowns
 *
 * Output matches the shape the tab components expect, so they don't need to know
 * whether the period came from a preset or a custom selection.
 */

import { PeriodEntry, RangeSlice, Snapshot } from "./snapshot";
import { daysBetween } from "./format";

type DailyRow<K extends string> = { date: string } & Record<K, number>;

function inRange(date: string, start: string, end: string): boolean {
  return date >= start && date <= end;
}

function filterDaily<T extends { date: string }>(rows: T[], start: string, end: string): T[] {
  return rows.filter((r) => inRange(r.date, start, end));
}

function sumKey<K extends string>(rows: DailyRow<K>[], key: K): number {
  return rows.reduce((acc, r) => acc + (r[key] || 0), 0);
}

function impressionWeightedAvgPosition(
  rows: { date: string; position: number; impressions: number }[],
  start: string,
  end: string,
): number | null {
  const slice = filterDaily(rows, start, end);
  const totalImps = slice.reduce((s, r) => s + (r.impressions || 0), 0);
  if (!totalImps) return null;
  return slice.reduce((s, r) => s + r.position * (r.impressions || 0), 0) / totalImps;
}

function buildSlice(snapshot: Snapshot, start: string, end: string): RangeSlice {
  const p90 = snapshot.periods["90d"].current;
  const daily90 = snapshot.daily_90d;

  // --- Daily KPI series sliced to [start, end] ---
  const ga4Daily = filterDaily(p90.ga4_daily, start, end);
  const stripeDailyAll = filterDaily(p90.stripe_m.daily, start, end);
  const stripeDailySplit = filterDaily(p90.stripe_m.daily_split, start, end);
  const mrrHistory = filterDaily(p90.mrr_history, start, end);
  const bhDailyRates = filterDaily(p90.bh_daily_rates, start, end);
  const newSubsDaily = filterDaily(p90.new_subs_daily.daily, start, end);
  const cogDaily = filterDaily(p90.cog_sales.daily, start, end);
  const pdfDaily = filterDaily(p90.pdf_sales.daily, start, end);
  const adsDaily = filterDaily(p90.ads.daily, start, end);
  const kwDaily = filterDaily(p90.kw_pos.daily, start, end);

  // --- Aggregate GA4 audience metrics from daily ---
  const usersTotal = sumKey(ga4Daily, "users");
  const modulesStartedTotal = sumKey(ga4Daily, "modules_started");
  const modulesFinishedTotal = sumKey(ga4Daily, "modules_finished");

  // --- Aggregate Stripe ---
  const grossUsd = stripeDailyAll.reduce((s, r) => s + (r.revenue || 0), 0);
  const subUsd = stripeDailySplit.reduce((s, r) => s + (r.subscription || 0), 0);
  const nonSubUsd = stripeDailySplit.reduce((s, r) => s + (r.non_subscription || 0), 0);

  // --- Aggregate beehiiv rates (weighted average — simple mean is fine here since campaigns are ~same size) ---
  const bhRatesNonZero = bhDailyRates.filter((r) => r.open_rate || r.unsubscribe_rate || r.click_rate);
  const avgOpen = bhRatesNonZero.length ? bhRatesNonZero.reduce((s, r) => s + r.open_rate, 0) / bhRatesNonZero.length : 0;
  const avgClick = bhRatesNonZero.length ? bhRatesNonZero.reduce((s, r) => s + r.click_rate, 0) / bhRatesNonZero.length : 0;
  const avgUnsub = bhRatesNonZero.length ? bhRatesNonZero.reduce((s, r) => s + r.unsubscribe_rate, 0) / bhRatesNonZero.length : 0;

  // --- Aggregate new subscribers daily ---
  const newSubsTotal = newSubsDaily.reduce((s, r) => s + (r.count || 0), 0);

  // --- Aggregate cog/pdf/ads ---
  const cogTotal = cogDaily.reduce((s, r) => s + (r.count || 0), 0);
  const pdfTotal = pdfDaily.reduce((s, r) => s + (r.count || 0), 0);
  const adsSpend = adsDaily.reduce((s, r) => s + (r.spend || 0), 0);
  const adsImps = adsDaily.reduce((s, r) => s + (r.impressions || 0), 0);
  const adsClicks = adsDaily.reduce((s, r) => s + (r.clicks || 0), 0);
  const adsConv = adsDaily.reduce((s, r) => s + (r.conversions || 0), 0);

  // --- Aggregate GSC keyword position (impression-weighted) ---
  const kwAvg = impressionWeightedAvgPosition(kwDaily, start, end);
  const kwClicks = kwDaily.reduce((s, r) => s + (r.clicks || 0), 0);
  const kwImps = kwDaily.reduce((s, r) => s + (r.impressions || 0), 0);

  // --- Aggregate channel breakdown ---
  const channelTotals: Map<string, number> = new Map();
  for (const row of daily90.channel) {
    if (!inRange(row.date, start, end)) continue;
    channelTotals.set(row.channel, (channelTotals.get(row.channel) || 0) + row.count);
  }
  const modulesByChannel = [...channelTotals.entries()]
    .map(([channel, count]) => ({ channel, count }))
    .sort((a, b) => b.count - a.count);

  // --- Aggregate campaign breakdown ---
  const campaignTotals: Map<string, number> = new Map();
  for (const row of daily90.campaign) {
    if (!inRange(row.date, start, end)) continue;
    campaignTotals.set(row.campaign, (campaignTotals.get(row.campaign) || 0) + row.count);
  }
  const modulesByCampaign = [...campaignTotals.entries()]
    .map(([campaign, count]) => ({ campaign, count }))
    .sort((a, b) => b.count - a.count);

  // --- Aggregate revenue by category ---
  const cat = { subscriptions: 0, pdf: 0, cognitive: 0, other: 0 };
  for (const row of daily90.revenue_category) {
    if (!inRange(row.date, start, end)) continue;
    cat.subscriptions += row.subscriptions;
    cat.pdf += row.pdf;
    cat.cognitive += row.cognitive;
    cat.other += row.other;
  }

  // Get current MRR snapshot — not range-dependent
  const currentMrr = snapshot.snapshots.current_mrr;

  return {
    ga4: {
      users: usersTotal,
      sessions: 0,
      pageviews: 0,
      modules_started: modulesStartedTotal,
      modules_finished: modulesFinishedTotal,
    },
    ga4_daily: ga4Daily,
    stripe_m: {
      revenue_usd: grossUsd,
      gross_usd: grossUsd,
      refunded_usd: 0,
      subscription_usd: subUsd,
      non_subscription_usd: nonSubUsd,
      daily: stripeDailyAll,
      daily_split: stripeDailySplit,
    },
    mrr_history: mrrHistory.length ? mrrHistory : [{ date: end, mrr: currentMrr }],
    bh: {
      error: null,
      total_subscribers: 0,
      new_subscribers: 0,
      campaigns_count: bhRatesNonZero.length,
      emails_sent: 0,
      email_opens: 0,
      email_clicks: 0,
      open_rate: avgOpen,
      click_rate: avgClick,
      unsubscribes: 0,
      unsubscribe_rate: avgUnsub,
      engaged_readers: 0,
      opens_per_campaign: 0,
      per_campaign: [],
      period_used_for_new_subs: "custom",
    },
    bh_daily_rates: bhDailyRates,
    new_subs_daily: {
      total: newSubsTotal,
      daily: newSubsDaily,
      error: null,
      capped: false,
    },
    cog_sales: { total: cogTotal, daily: cogDaily },
    pdf_sales: { total: pdfTotal, daily: pdfDaily },
    ads: {
      spend_usd: adsSpend,
      impressions: adsImps,
      clicks: adsClicks,
      conversions: adsConv,
      daily: adsDaily,
      error: null,
    },
    modules_by_channel: modulesByChannel,
    modules_by_campaign: modulesByCampaign,
    kw_pos: { daily: kwDaily, avg_position: kwAvg, clicks: kwClicks, impressions: kwImps, keyword: p90.kw_pos.keyword },
    revenue_cat: cat,
  };
}

/**
 * Build a PeriodEntry for a custom [start, end] range.
 * Prior period = same length, immediately before start, if it fits inside the 90d daily window.
 */
export function buildCustomPeriod(snapshot: Snapshot, start: string, end: string): PeriodEntry {
  const days = daysBetween(start, end);
  const startD = new Date(start);
  const priorEnd = new Date(startD);
  priorEnd.setDate(priorEnd.getDate() - 1);
  const priorStart = new Date(priorEnd);
  priorStart.setDate(priorStart.getDate() - days + 1);

  const priorStartIso = priorStart.toISOString().slice(0, 10);
  const priorEndIso = priorEnd.toISOString().slice(0, 10);
  const dailyMin = snapshot.daily_90d.start;

  const priorFits = priorStartIso >= dailyMin;
  const priorSlice = priorFits
    ? buildSlice(snapshot, priorStartIso, priorEndIso)
    : buildSlice(snapshot, start, end); // fallback: no real prior — pass current so variance() returns null naturally

  return {
    start,
    end,
    prior_start: priorStartIso,
    prior_end: priorEndIso,
    days,
    current: buildSlice(snapshot, start, end),
    prior: priorFits ? priorSlice : zeroOutForNoComparison(priorSlice),
  };
}

/** Return a slice with everything zeroed so variance() returns null (prev=0). Used when prior is out of range. */
function zeroOutForNoComparison(slice: RangeSlice): RangeSlice {
  return {
    ...slice,
    ga4: { users: 0, sessions: 0, pageviews: 0, modules_started: 0, modules_finished: 0 },
    stripe_m: { ...slice.stripe_m, gross_usd: 0, revenue_usd: 0, subscription_usd: 0, non_subscription_usd: 0, daily: [], daily_split: [] },
    mrr_history: [],
    bh: { ...slice.bh, open_rate: 0, click_rate: 0, unsubscribe_rate: 0 },
    new_subs_daily: { total: 0, daily: [], error: null, capped: false },
    cog_sales: { total: 0, daily: [] },
    pdf_sales: { total: 0, daily: [] },
    ads: { ...slice.ads, spend_usd: 0, impressions: 0, clicks: 0, conversions: 0, daily: [] },
    kw_pos: { ...slice.kw_pos, avg_position: null, clicks: 0, impressions: 0, daily: [] },
    revenue_cat: { subscriptions: 0, pdf: 0, cognitive: 0, other: 0 },
  };
}
