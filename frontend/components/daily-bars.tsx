"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Props {
  data: { date: string; new: number; unsubs: number }[];
  height?: number;
}

export function DailyBars({ data, height = 260 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(127,127,127,0.15)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "currentColor" }}
          tickLine={false}
          axisLine={false}
          minTickGap={20}
          tickFormatter={(v) => (typeof v === "string" ? v.slice(5) : v)}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "currentColor" }}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip
          contentStyle={{
            background: "var(--background)",
            border: "1px solid rgb(228 228 231)",
            borderRadius: 6,
            fontSize: 12,
          }}
          formatter={(v, name) => [`${typeof v === "number" ? v : 0}`, name === "new" ? "New" : "Unsubscribers"]}
        />
        <Legend
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          iconType="circle"
          formatter={(value) => (value === "new" ? "New" : "Unsubscribers")}
        />
        <Bar dataKey="new" fill="#4F8BF9" radius={[3, 3, 0, 0]} />
        <Bar dataKey="unsubs" fill="#DC2626" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
