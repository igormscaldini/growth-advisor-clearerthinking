"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Props {
  data: { date: string; value: number | null }[];
  color: string;
  yLabel?: string;
  isPercent?: boolean;
  height?: number;
}

export function AreaSpark({ data, color, yLabel, isPercent, height = 220 }: Props) {
  if (!data.length || data.every((d) => d.value == null || d.value === 0)) {
    return (
      <div
        className="flex items-center justify-center text-sm text-zinc-500 dark:text-zinc-400 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-md"
        style={{ height }}
      >
        No data for this window.
      </div>
    );
  }

  const fillId = `fill-${color.replace("#", "")}`;
  const valueFormatter = (v: unknown) => {
    if (typeof v !== "number") return "—";
    return isPercent ? `${(v * 100).toFixed(2)}%` : v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 8, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "currentColor" }}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "currentColor" }}
          tickLine={false}
          axisLine={false}
          width={40}
          tickFormatter={(v: number) => (isPercent ? `${(v * 100).toFixed(0)}%` : abbreviate(v))}
        />
        <Tooltip
          contentStyle={{
            background: "var(--background)",
            border: "1px solid rgb(228 228 231)",
            borderRadius: 6,
            fontSize: 12,
          }}
          labelStyle={{ color: "var(--foreground)" }}
          formatter={(v) => [valueFormatter(v), yLabel || ""]}
        />
        <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill={`url(#${fillId})`} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function abbreviate(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return String(v);
}
