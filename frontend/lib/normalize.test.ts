import { test } from "node:test";
import assert from "node:assert/strict";
import { describeErrors, isErrorBlock, normalizeSlice, normalizeSnapshot } from "./normalize.ts";
import type { RangeSlice, Snapshot } from "./snapshot.ts";

// A slice the way fetch_snapshot._safe writes it when GA4 is down: four GA4 blocks are {"error": ...}.
const broken = {
  ga4: { error: "504 Deadline Exceeded" },
  ga4_daily: { error: "504 Deadline Exceeded" },
  stripe_m: { revenue_usd: 5, gross_usd: 5, refunded_usd: 0, subscription_usd: 5, non_subscription_usd: 0, daily: [{ date: "2026-11-12", revenue: 5 }], daily_split: [] },
  mrr_history: [],
  bh: { error: null, total_subscribers: 1, new_subscribers: 0, campaigns_count: 0, emails_sent: 0, email_opens: 0, email_clicks: 0, open_rate: 0, click_rate: 0, unsubscribes: 0, unsubscribe_rate: 0, engaged_readers: 0, opens_per_campaign: 0, per_campaign: [], period_used_for_new_subs: "x" },
  bh_daily_rates: [],
  new_subs_daily: { total: 3, daily: [], error: null, capped: false },
  cog_sales: { total: 1, daily: [] },
  pdf_sales: { total: 2, daily: [] },
  new_stripe_subs: { total: 0, daily: [], error: null },
  ads: { spend_usd: 0, impressions: 0, clicks: 0, conversions: 0, daily: [], error: null },
  modules_by_channel: { error: "504 Deadline Exceeded" },
  modules_by_campaign: { error: "429 Resource has been exhausted" },
  kw_pos: { daily: [], avg_position: 3, clicks: 1, impressions: 2, keyword: "personality test" },
  revenue_cat: { subscriptions: 5, pdf: 0, cognitive: 0, other: 0 },
} as unknown as RangeSlice;

test("isErrorBlock only matches the {error} shape _safe writes", () => {
  assert.equal(isErrorBlock({ error: "x" }), true);
  assert.equal(isErrorBlock({ error: null, total_subscribers: 1 }), false); // bh carries an error slot but data too
  assert.equal(isErrorBlock([]), false);
  assert.equal(isErrorBlock(null), false);
});

test("normalizeSlice replaces error blocks with empty values of the right shape and records them", () => {
  const errors: Record<string, string> = {};
  const s = normalizeSlice(broken, "30d.current", errors);
  assert.deepEqual(s.ga4, { users: 0, sessions: 0, pageviews: 0, modules_started: 0, modules_finished: 0 });
  assert.deepEqual(s.ga4_daily, []);
  assert.deepEqual(s.modules_by_channel, []);
  assert.deepEqual(s.modules_by_campaign, []);
  assert.equal(s.stripe_m.gross_usd, 5); // healthy blocks pass through untouched
  assert.equal(s.cog_sales.total, 1);
  assert.deepEqual(errors, {
    "30d.current.ga4": "504 Deadline Exceeded",
    "30d.current.ga4_daily": "504 Deadline Exceeded",
    "30d.current.modules_by_channel": "504 Deadline Exceeded",
    "30d.current.modules_by_campaign": "429 Resource has been exhausted",
  });
  // the tabs can now iterate every list
  assert.doesNotThrow(() => s.ga4_daily.forEach(() => {}));
  assert.doesNotThrow(() => s.modules_by_channel.map((r) => r.channel));
});

test("normalizeSlice leaves a clean slice unchanged", () => {
  const errors: Record<string, string> = {};
  const clean = { ...broken, ga4: { users: 9, sessions: 9, pageviews: 9, modules_started: 1, modules_finished: 1 }, ga4_daily: [], modules_by_channel: [], modules_by_campaign: [] } as RangeSlice;
  assert.deepEqual(normalizeSlice(clean, "7d.current", errors), clean);
  assert.deepEqual(errors, {});
});

test("normalizeSnapshot walks every period and the daily window", () => {
  const snap = {
    generated_at: "2026-11-13T12:33:29Z",
    today: "2026-11-13",
    snapshots: { current_mrr: 1, active_subscribers: 1, total_subscribers: 1, engaged_readers: { error: null }, keyword_overall: { error: "boom" }, new_subscribers_monthly_alltime: { error: "x" } },
    periods: { "7d": { start: "a", end: "b", prior_start: "c", prior_end: "d", days: 7, current: broken, prior: broken } },
    daily_window: { start: "a", end: "b", kpi: broken, channel: { error: "x" }, campaign: [], revenue_category: [], funnel_by_page: { error: "x" } },
    manual_revenue: { last_updated: "", lines: {} },
  } as unknown as Snapshot;
  const out = normalizeSnapshot(snap);
  assert.deepEqual(out.periods["7d"].current.ga4_daily, []);
  assert.deepEqual(out.periods["7d"].prior.modules_by_channel, []);
  assert.deepEqual(out.daily_window.kpi.ga4_daily, []);
  assert.deepEqual(out.daily_window.channel, []);
  assert.deepEqual(out.daily_window.funnel_by_page, []);
  assert.deepEqual(out.snapshots.keyword_overall, { position: null, clicks: 0, impressions: 0, keyword: "" });
  assert.deepEqual(out.snapshots.new_subscribers_monthly_alltime, []);
  assert.equal(Object.keys(out.errors || {}).length, 4 * 3 + 1); // 4 blocks x (current, prior, daily window) + keyword
  assert.equal(snap.periods["7d"].current.ga4_daily && "error" in snap.periods["7d"].current.ga4_daily, true); // input untouched
});

test("describeErrors groups the failed blocks per scope", () => {
  const lines = describeErrors({
    "30d.current.ga4": "504 Deadline Exceeded",
    "30d.current.ga4_daily": "504 Deadline Exceeded",
    "daily_window.ga4": "504 Deadline Exceeded",
  });
  assert.deepEqual(lines, ["30d: ga4, ga4_daily (504 Deadline Exceeded)", "daily window: ga4 (504 Deadline Exceeded)"]);
});
