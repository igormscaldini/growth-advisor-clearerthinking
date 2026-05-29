"use client";

import { AreaSpark, ExtraSeries } from "./area-spark";

interface Props {
  label: string;
  value: string;
  helpText?: string;
  delta: number | null;
  deltaInverse?: boolean;
  comparisonNote?: string;
  data: ({ date: string; value: number | null } & Record<string, number | null | string>)[];
  color: string;
  yLabel?: string;
  isPercent?: boolean;
  footer?: React.ReactNode;
  series?: ExtraSeries[];
  primaryLabel?: string;
}

export function KpiCard({
  label,
  value,
  helpText,
  delta,
  deltaInverse = false,
  comparisonNote,
  data,
  color,
  yLabel,
  isPercent,
  footer,
  series,
  primaryLabel,
}: Props) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5 shadow-sm">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300" title={helpText}>
          {label}
        </h3>
        {helpText ? (
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 cursor-help" title={helpText}>
            ⓘ
          </span>
        ) : null}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_3fr] gap-4 items-center">
        <div>
          <div className="text-3xl font-bold leading-none">{value}</div>
          {delta == null ? (
            <div className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
              {comparisonNote || "(no comparison available)"}
            </div>
          ) : (
            <DeltaBadge delta={delta} inverse={deltaInverse} note={comparisonNote} />
          )}
          {footer ? <div className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{footer}</div> : null}
        </div>
        <div>
          {series && series.length > 0 ? (
            <AreaSpark
              data={data}
              color={color}
              yLabel={yLabel}
              isPercent={isPercent}
              series={series}
              primaryLabel={primaryLabel}
            />
          ) : (
            <AreaSpark data={data} color={color} yLabel={yLabel} isPercent={isPercent} />
          )}
        </div>
      </div>
    </div>
  );
}

function DeltaBadge({ delta, inverse, note }: { delta: number; inverse: boolean; note?: string }) {
  const isGood = inverse ? delta < 0 : delta > 0;
  const isFlat = Math.abs(delta) < 0.05;
  const sign = delta > 0 ? "▲" : "▼";
  const color = isFlat
    ? "text-zinc-500 dark:text-zinc-400"
    : isGood
      ? "text-green-600 dark:text-green-400"
      : "text-red-600 dark:text-red-400";
  return (
    <div className={`mt-2 text-sm font-medium ${color}`}>
      {sign} {Math.abs(delta).toFixed(1)}%{" "}
      <span className="font-normal text-zinc-500 dark:text-zinc-400">{note || "vs prior period"}</span>
    </div>
  );
}
