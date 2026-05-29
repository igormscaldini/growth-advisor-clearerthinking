export function fmtMoney(v: number): string {
  if (v == null || isNaN(v)) return "—";
  if (Math.abs(v) < 1000) return `$${v.toFixed(2)}`;
  return `$${Math.round(v).toLocaleString("en-US")}`;
}

export function fmtInt(v: number | null | undefined): string {
  if (v == null || isNaN(v as number)) return "0";
  return Math.round(v).toLocaleString("en-US");
}

export function fmtPct(v: number | null | undefined): string {
  if (v == null || isNaN(v as number)) return "0.0%";
  return `${(v * 100).toFixed(1)}%`;
}

export function variance(curr: number | null | undefined, prev: number | null | undefined): number | null {
  if (curr == null || prev == null) return null;
  const c = Number(curr);
  const p = Number(prev);
  if (isNaN(c) || isNaN(p) || p === 0) return null;
  return ((c - p) / p) * 100;
}

export function presetLabel(key: "7d" | "30d" | "90d" | "thisMonth" | "custom"): string {
  if (key === "7d") return "Last 7 days";
  if (key === "30d") return "Last 30 days";
  if (key === "90d") return "Last 90 days";
  if (key === "thisMonth") return "This Month";
  return "Custom";
}

export function presetDays(key: "7d" | "30d" | "90d"): number {
  return key === "7d" ? 7 : key === "30d" ? 30 : 90;
}

export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function daysBetween(start: string, end: string): number {
  const s = new Date(start);
  const e = new Date(end);
  return Math.round((e.getTime() - s.getTime()) / (1000 * 60 * 60 * 24)) + 1;
}
