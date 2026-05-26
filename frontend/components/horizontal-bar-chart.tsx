"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Props {
  data: { label: string; value: number }[];
  unit?: string;
  color?: string;
}

const SHADES = ["#15803d", "#16a34a", "#22c55e", "#4ade80", "#86efac", "#bbf7d0"];

export function HorizontalBarChart({ data, unit = "" }: Props) {
  if (!data.length) {
    return <div className="text-sm text-zinc-500 dark:text-zinc-400">No data.</div>;
  }
  const total = data.reduce((s, d) => s + d.value, 0);
  const height = Math.max(280, 44 * data.length);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 80, left: 8, bottom: 8 }}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ fontSize: 12, fill: "currentColor" }}
          tickLine={false}
          axisLine={false}
          width={140}
        />
        <Tooltip
          contentStyle={{
            background: "var(--background)",
            border: "1px solid rgb(228 228 231)",
            borderRadius: 6,
            fontSize: 12,
          }}
          formatter={(v) => {
            const n = typeof v === "number" ? v : 0;
            return [
              `${n.toLocaleString("en-US")} (${((n / total) * 100).toFixed(1)}%) ${unit}`.trim(),
              "",
            ];
          }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={SHADES[Math.min(i, SHADES.length - 1)]} />
          ))}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: unknown) => {
              const n = typeof v === "number" ? v : 0;
              return `${n.toLocaleString("en-US")} (${((n / total) * 100).toFixed(1)}%)`;
            }}
            style={{ fill: "currentColor", fontSize: 12 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
