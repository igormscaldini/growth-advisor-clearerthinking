/**
 * One definition of "total revenue" shared by the Monetization table and the Overview card:
 * the window's Stripe revenue by category (net of refunds, sponsorship charges excluded) plus
 * every manual line (absolute totals, not window-scoped).
 */

import { PeriodEntry, Snapshot } from "./snapshot";

export function manualRevenueTotal(snapshot: Snapshot): number {
  return Object.values(snapshot.manual_revenue.lines)
    .flat()
    .reduce((s, i) => s + i.amount, 0);
}

export function monetizationTotals(snapshot: Snapshot, period: PeriodEntry): { stripe: number; manual: number; total: number } {
  const cat = period.current.revenue_cat;
  const stripe = (cat?.subscriptions || 0) + (cat?.pdf || 0) + (cat?.cognitive || 0) + (cat?.other || 0);
  const manual = manualRevenueTotal(snapshot);
  return { stripe, manual, total: stripe + manual };
}
