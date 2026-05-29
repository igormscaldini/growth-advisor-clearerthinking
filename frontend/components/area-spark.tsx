"use client";

import { Area, AreaChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface SingleSeriesProps {
  data: { date: string; value: number | null }[];
  color: string;
  yLabel?: string;
  isPercent?: boolean;
  height?: number;
  series?: undefined;
}

export interface ExtraSeries {
  key: string;
  color: string;
  label: string;
}

interface MultiSeriesProps {
  data: ({ date: string; value: number | null } & Record<string, number | null | string>)[];
  color: string;
  yLabel?: string;
  isPercent?: boolean;
  height?: number;
  /** Primary series uses `value`; each entry here adds another stacked-style area for the named key. */
  series: ExtraSeries[];
  primaryLabel?: string;
}

type Props = SingleSeriesProps | MultiSeriesProps;

export function AreaSpark(props: Props) {
  const { data, color, yLabel, isPercent, height = 220 } = props;
  const extraSeries = "series" in props && props.series ? props.series : [];
  const primaryLabel = "primaryLabel" in props ? props.primaryLabel : undefined;

  const hasPrimary = data.some((d) => typeof d.value === "number" && d.value !== 0);
  const hasExtra = extraSeries.some((s) =>
    data.some((d) => {
      const v = (d as Record<string, unknown>)[s.key];
      return typeof v === "number" && v !== 0;
    }),
  );
  if (!data.length || (!hasPrimary && !hasExtra)) {
    return (
      <div
        className="flex items-center justify-center text-sm text-zinc-500 dark:text-zinc-400 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-md"
        style={{ height }}
      >
        No data for this window.
      </div>
    );
  }

  const valueFormatter = (v: unknown) => {
    if (typeof v !== "number") return "—";
    return isPercent ? `${(v * 100).toFixed(2)}%` : v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  };

  const safeId = (c: string) => c.replace(/[^a-zA-Z0-9]/g, "");
  const primaryFillId = `fill-${safeId(color)}`;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 8, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id={primaryFillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
          {extraSeries.map((s) => (
            <linearGradient key={s.key} id={`fill-${safeId(s.color)}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          ))}
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
          formatter={(v, name) => [valueFormatter(v), String(name)]}
        />
        {extraSeries.length > 0 && (
          <Legend verticalAlign="top" height={20} iconType="circle" wrapperStyle={{ fontSize: 11 }} />
        )}
        <Area
          type="monotone"
          dataKey="value"
          name={primaryLabel || yLabel || "Value"}
          stroke={color}
          strokeWidth={2}
          fill={`url(#${primaryFillId})`}
          dot={false}
        />
        {extraSeries.map((s) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={2}
            fill={`url(#fill-${safeId(s.color)})`}
            dot={false}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

function abbreviate(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return String(v);
}
