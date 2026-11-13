/**
 * Make a snapshot safe to render whatever failed while it was fetched.
 *
 * fetch_snapshot.py wraps every source in _safe(): a failed call lands in the JSON as {"error": "..."} in
 * place of the list or object the tabs expect. On 2026-11-13 a GA4 outage put eight such blocks in a
 * snapshot and the Next prerender died on `.forEach is not a function`, which failed every Vercel deploy
 * for hours. normalizeSnapshot() swaps each error block for an empty value of the right shape and keeps
 * the messages in `snapshot.errors` (path -> message) for the banner on the dashboard.
 */

import type { BeehiivMetrics, RangeSlice, Snapshot } from "./snapshot";

type ErrorBlock = { error: string };

export function isErrorBlock(v: unknown): v is ErrorBlock {
  return !!v && typeof v === "object" && !Array.isArray(v) && "error" in v && Object.keys(v as object).length === 1;
}

const emptyBh = (error: string | null): BeehiivMetrics => ({
  error,
  total_subscribers: 0,
  new_subscribers: 0,
  campaigns_count: 0,
  emails_sent: 0,
  email_opens: 0,
  email_clicks: 0,
  open_rate: 0,
  click_rate: 0,
  unsubscribes: 0,
  unsubscribe_rate: 0,
  engaged_readers: 0,
  opens_per_campaign: 0,
  per_campaign: [],
  period_used_for_new_subs: "",
});

/** Empty value of the right shape for each RangeSlice key (the error message is kept where the type has a slot). */
function emptyFor(key: keyof RangeSlice, error: string): unknown {
  switch (key) {
    case "ga4":
      return { users: 0, sessions: 0, pageviews: 0, modules_started: 0, modules_finished: 0 };
    case "stripe_m":
      return { revenue_usd: 0, gross_usd: 0, refunded_usd: 0, subscription_usd: 0, non_subscription_usd: 0, daily: [], daily_split: [] };
    case "bh":
      return emptyBh(error);
    case "new_subs_daily":
      return { total: 0, daily: [], error, capped: false };
    case "cog_sales":
    case "pdf_sales":
      return { total: 0, daily: [] };
    case "new_stripe_subs":
      return { total: 0, daily: [], error };
    case "ads":
      return { spend_usd: 0, impressions: 0, clicks: 0, conversions: 0, daily: [], error };
    case "kw_pos":
      return { daily: [], avg_position: null, clicks: 0, impressions: 0, keyword: "" };
    case "revenue_cat":
      return { subscriptions: 0, pdf: 0, cognitive: 0, other: 0 };
    case "flow":
      return undefined;
    default:
      return []; // ga4_daily, mrr_history, bh_daily_rates, modules_by_channel, modules_by_campaign
  }
}

const SLICE_KEYS: (keyof RangeSlice)[] = [
  "ga4", "ga4_daily", "stripe_m", "mrr_history", "bh", "bh_daily_rates", "new_subs_daily", "cog_sales", "pdf_sales",
  "new_stripe_subs", "ads", "modules_by_channel", "modules_by_campaign", "kw_pos", "revenue_cat", "flow",
];

/** A copy of `slice` with every error block (or missing required block) replaced; errors recorded under `label`. */
export function normalizeSlice(slice: RangeSlice, label: string, errors: Record<string, string>): RangeSlice {
  const out = { ...slice } as Record<string, unknown>;
  for (const key of SLICE_KEYS) {
    const v = out[key];
    if (isErrorBlock(v)) {
      errors[`${label}.${key}`] = v.error;
      out[key] = emptyFor(key, v.error);
    } else if (v === undefined && key !== "flow" && key !== "new_stripe_subs") {
      out[key] = emptyFor(key, "missing");
    }
  }
  return out as unknown as RangeSlice;
}

export function normalizeSnapshot(snapshot: Snapshot): Snapshot {
  const errors: Record<string, string> = { ...(snapshot.errors || {}) };
  const periods = Object.fromEntries(
    Object.entries(snapshot.periods).map(([k, p]) => [
      k,
      { ...p, current: normalizeSlice(p.current, `${k}.current`, errors), prior: normalizeSlice(p.prior, `${k}.prior`, errors) },
    ]),
  ) as Snapshot["periods"];
  const dw = snapshot.daily_window;
  const daily_window = {
    ...dw,
    kpi: normalizeSlice(dw.kpi, "daily_window", errors),
    channel: Array.isArray(dw.channel) ? dw.channel : [],
    campaign: Array.isArray(dw.campaign) ? dw.campaign : [],
    revenue_category: Array.isArray(dw.revenue_category) ? dw.revenue_category : [],
    funnel_by_page: Array.isArray(dw.funnel_by_page) ? dw.funnel_by_page : [],
    flow: Array.isArray(dw.flow) ? dw.flow : undefined,
  };
  const snaps = { ...snapshot.snapshots };
  if (isErrorBlock(snaps.keyword_overall)) {
    errors["snapshots.keyword_overall"] = snaps.keyword_overall.error;
    snaps.keyword_overall = { position: null, clicks: 0, impressions: 0, keyword: "" };
  }
  if (isErrorBlock(snaps.avg_unique_opens_per_campaign)) {
    errors["snapshots.avg_unique_opens_per_campaign"] = snaps.avg_unique_opens_per_campaign.error;
    snaps.avg_unique_opens_per_campaign = undefined;
  }
  if (!Array.isArray(snaps.new_subscribers_monthly_alltime)) snaps.new_subscribers_monthly_alltime = [];
  return { ...snapshot, periods, daily_window, snapshots: snaps, errors };
}

/** One line per failed source for the banner: "30d: ga4, ga4_daily (504 Deadline Exceeded)". */
export function describeErrors(errors: Record<string, string>): string[] {
  const byScope = new Map<string, { keys: string[]; msg: string }>();
  for (const [path, msg] of Object.entries(errors)) {
    const [scope, ...rest] = path.split(".");
    const label = path.startsWith("daily_window") ? "daily window" : path.includes(".prior") ? `${scope} prior` : scope;
    const key = rest[rest.length - 1];
    const e = byScope.get(label) || { keys: [], msg };
    e.keys.push(key);
    byScope.set(label, e);
  }
  return [...byScope.entries()].map(([scope, e]) => `${scope}: ${e.keys.join(", ")} (${e.msg})`);
}
