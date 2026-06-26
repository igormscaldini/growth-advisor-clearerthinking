export type PresetKey = "7d" | "30d" | "90d" | "thisMonth" | "custom";

export interface DailyPoint {
  date: string;
  [key: string]: string | number | null;
}

export interface Ga4Aggregates {
  users: number;
  sessions: number;
  pageviews: number;
  modules_started: number;
  modules_finished: number;
}

export interface StripeMetrics {
  revenue_usd: number;
  gross_usd: number;
  refunded_usd: number;
  subscription_usd: number;
  non_subscription_usd: number;
  daily: { date: string; revenue: number }[];
  daily_split: { date: string; subscription: number; non_subscription: number; total: number }[];
}

export interface BeehiivCampaign {
  title: string;
  date: string;
  sent: number;
  opens: number;
  clicks: number;
  open_rate: number;
  click_rate: number;
  unsubs: number;
}

export interface BeehiivMetrics {
  error: string | null;
  total_subscribers: number;
  new_subscribers: number;
  campaigns_count: number;
  emails_sent: number;
  email_opens: number;
  email_clicks: number;
  open_rate: number;
  click_rate: number;
  unsubscribes: number;
  unsubscribe_rate: number;
  engaged_readers: number;
  opens_per_campaign: number;
  per_campaign: BeehiivCampaign[];
  period_used_for_new_subs: string;
}

export interface NewSubsDaily {
  total: number;
  daily: { date: string; count: number }[];
  error: string | null;
  capped: boolean;
}

export interface AdsMetrics {
  spend_usd: number;
  impressions: number;
  clicks: number;
  conversions: number;
  daily: { date: string; spend: number; impressions: number; clicks: number; conversions: number }[];
  error: string | null;
}

export interface KwPosDaily {
  daily: { date: string; position: number; clicks: number; impressions: number }[];
  avg_position: number | null;
  clicks: number;
  impressions: number;
  keyword: string;
}

export interface RevenueByCategory {
  subscriptions: number;
  pdf: number;
  cognitive: number;
  other: number;
}

export interface RangeSlice {
  ga4: Ga4Aggregates;
  ga4_daily: {
    date: string;
    users: number;
    first_visit?: number;
    modules_started: number;
    accepted_privacy?: number;
    modules_finished: number;
  }[];
  stripe_m: StripeMetrics;
  mrr_history: { date: string; mrr: number }[];
  bh: BeehiivMetrics;
  bh_daily_rates: { date: string; open_rate: number; click_rate: number; unsubscribe_rate: number }[];
  new_subs_daily: NewSubsDaily;
  cog_sales: { total: number; daily: { date: string; count: number }[] };
  pdf_sales: { total: number; daily: { date: string; count: number }[] };
  ads: AdsMetrics;
  modules_by_channel: { channel: string; count: number }[];
  modules_by_campaign: { campaign: string; count: number }[];
  kw_pos: KwPosDaily;
  revenue_cat: RevenueByCategory;
}

export interface PeriodEntry {
  start: string;
  end: string;
  prior_start: string;
  prior_end: string;
  days: number;
  current: RangeSlice;
  prior: RangeSlice;
}

export interface Snapshot {
  generated_at: string;
  today: string;
  snapshots: {
    current_mrr: number;
    active_subscribers: number;
    engaged_readers: {
      engaged: number;
      segment_name: string | null;
      last_calculated?: number;
      error: string | null;
    };
    keyword_overall: {
      position: number | null;
      clicks: number;
      impressions: number;
      keyword: string;
    };
    new_subscribers_monthly_alltime: { month: string; new: number; cancelled: number }[];
  };
  periods: Record<"7d" | "30d" | "90d", PeriodEntry>;
  // "thisMonth" and "custom" are built client-side in dashboard.tsx; only the three fixed presets are pre-baked.

  daily_90d: {
    start: string;
    end: string;
    channel: { date: string; channel: string; count: number }[];
    campaign: { date: string; campaign: string; count: number }[];
    revenue_category: { date: string; subscriptions: number; pdf: number; cognitive: number; other: number }[];
  };
  manual_revenue: {
    last_updated: string;
    lines: Record<string, { source: string; amount: number }[]>;
  };
}
