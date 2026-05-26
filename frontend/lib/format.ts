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

export function presetLabel(key: "7d" | "30d" | "90d"): string {
  return key === "7d" ? "Last 7 days" : key === "30d" ? "Last 30 days" : "Last 90 days";
}

export function presetDays(key: "7d" | "30d" | "90d"): number {
  return key === "7d" ? 7 : key === "30d" ? 30 : 90;
}
