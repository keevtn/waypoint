// Recharts LineChart: x = month, y = end-of-month balance. Thin lines: baseline dashed in ink, options in
// accent/ink shades, floor as a hairline, below-floor months as a flat tint. Animates only on data change.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ProjectionResult } from "../types";
import { fmtCents, fmtDollars, fmtMonth, fmtMonthShort } from "../lib/format";
import { useDarkMode } from "../lib/hooks";

export const BASELINE_KEY = "baseline";

// Option series: accent first, then ink shades. Baseline is dashed ink. Semantic colors stay on flags.
const LIGHT = ["#0e5a57", "#393631", "#8a8478", "#5aa09b"];
const DARK = ["#3fa39d", "#dcd8cf", "#8a8478", "#1f7a76"];

export function seriesColor(index: number, dark: boolean): string {
  const p = dark ? DARK : LIGHT;
  return p[index % p.length];
}

export interface ChartSeries {
  id: string; // option id or "baseline"
  label: string;
  result: ProjectionResult;
}

interface Row {
  idx: number;
  month: string;
  [seriesId: string]: number | string | null;
}

export default function ProjectionChart({
  series,
  selectedId,
  floorCents,
  height = 300,
  onMonthClick,
}: {
  series: ChartSeries[];
  selectedId?: string | null;
  floorCents: number;
  height?: number;
  onMonthClick?: (month: string) => void;
}) {
  const dark = useDarkMode();
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  // Motion only on data change: the first paint (and container resizes) draw instantly; when the series
  // themselves change after mount (new evaluation, scenario, suggestion tap) the lines animate once.
  const signature = series.map((s) => `${s.id}:${s.result.series.length}:${s.result.min_balance_cents}:${s.result.series[s.result.series.length - 1]?.end_balance_cents ?? ""}`).join("|");
  const prevSignature = useRef(signature);
  const [animate, setAnimate] = useState(false);
  useEffect(() => {
    if (prevSignature.current === signature) return;
    prevSignature.current = signature;
    setAnimate(true);
    const t = setTimeout(() => setAnimate(false), 600);
    return () => clearTimeout(t);
  }, [signature]);

  const rows = useMemo<Row[]>(() => {
    const months = new Set<string>();
    for (const s of series) for (const p of s.result.series) months.add(p.month);
    const sorted = [...months].sort();
    return sorted.map((month, idx) => {
      const row: Row = { idx, month };
      for (const s of series) {
        const p = s.result.series.find((x) => x.month === month);
        row[s.id] = p ? p.end_balance_cents : null;
      }
      return row;
    });
  }, [series]);

  const selected = series.find((s) => s.id === selectedId) ?? null;
  const idxOf = (month: string) => rows.findIndex((r) => r.month === month);
  const tinted = selected ? selected.result.months_below_floor.filter((m) => idxOf(m) >= 0) : [];
  const monthAt = (v: unknown) => rows[Number(v)]?.month ?? "";
  // Past 12 months: one tick per January, labelled by year, and thinner lines; the 12-month layout is unchanged.
  const long = rows.length > 12;
  const ticks = long ? rows.filter((r) => r.month.endsWith("-01")).map((r) => r.idx) : rows.map((r) => r.idx);
  const tickLabel = (v: number) => (long ? monthAt(v).slice(0, 4) : fmtMonthShort(monthAt(v)));

  const grid = dark ? "#252320" : "#ebe8e1";
  const axis = dark ? "#918b80" : "#787369";
  const ink = dark ? "#ebe8e1" : "#171614";
  const baselineColor = ink;
  const floorColor = dark ? "#c3beb2" : "#4d4942";
  const tint = dark ? "rgba(252,211,77,0.10)" : "rgba(154,90,0,0.08)";
  const negTint = dark ? "rgba(252,165,165,0.12)" : "rgba(180,35,24,0.08)";

  const colorOf = (id: string): string => {
    if (id === BASELINE_KEY) return baselineColor;
    const idx = series.filter((s) => s.id !== BASELINE_KEY).findIndex((s) => s.id === id);
    return seriesColor(Math.max(0, idx), dark);
  };

  const toggle = (id: string) =>
    setHidden((h) => {
      const n = new Set(h);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  if (rows.length === 0) return null;

  return (
    <div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={rows}
            margin={{ top: 16, right: 16, bottom: 8, left: 4 }}
            onClick={(e) => {
              const m = monthAt((e as { activeLabel?: string | number } | null)?.activeLabel);
              if (m && onMonthClick) onMonthClick(m);
            }}
          >
            <CartesianGrid stroke={grid} strokeOpacity={0.8} vertical={false} />
            <XAxis
              dataKey="idx"
              type="number"
              domain={[-0.5, rows.length - 0.5]}
              ticks={ticks}
              tickFormatter={tickLabel}
              stroke={axis}
              tick={{ fontSize: 12, fill: axis }}
              tickLine={false}
              axisLine={{ stroke: grid }}
            />
            <YAxis
              tickFormatter={(v: number) => fmtDollars(v)}
              stroke={axis}
              tick={{ fontSize: 12, fill: axis }}
              tickLine={false}
              axisLine={false}
              width={64}
            />
            {tinted.map((m) => {
              const neg = selected?.result.months_negative.includes(m);
              const i = idxOf(m);
              return <ReferenceArea key={m} x1={i - 0.5} x2={i + 0.5} fill={neg ? negTint : tint} stroke="none" />;
            })}
            <ReferenceLine y={0} stroke={axis} strokeOpacity={0.5} />
            <ReferenceLine y={floorCents} stroke={floorColor} strokeWidth={1} />
            <Tooltip
              cursor={{ stroke: axis, strokeWidth: 1 }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="rounded border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-1 font-medium">{fmtMonth(monthAt(label))}</div>
                    {payload
                      .filter((p) => p.value !== null && p.value !== undefined)
                      .map((p) => (
                        <div key={String(p.dataKey)} className="flex items-center justify-between gap-4">
                          <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                            <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
                            {series.find((s) => s.id === p.dataKey)?.label ?? String(p.dataKey)}
                          </span>
                          <span className="tabular font-medium">{fmtCents(Number(p.value))}</span>
                        </div>
                      ))}
                    {onMonthClick && <div className="mt-1 text-xs text-slate-400">Click for why this month</div>}
                  </div>
                );
              }}
            />
            {series.map((s) => {
              const isBase = s.id === BASELINE_KEY;
              const isSel = s.id === selectedId;
              return (
                <Line
                  key={s.id}
                  type="monotone"
                  dataKey={s.id}
                  name={s.label}
                  hide={hidden.has(s.id)}
                  stroke={colorOf(s.id)}
                  strokeWidth={long ? (isSel ? 1.5 : isBase ? 0.75 : 1) : isSel ? 2 : isBase ? 1 : 1.25}
                  strokeDasharray={isBase ? "4 4" : undefined}
                  strokeOpacity={selectedId && !isSel && !isBase ? 0.6 : 1}
                  dot={false}
                  activeDot={{ r: 3.5, stroke: dark ? "#171614" : "#fbfaf7", strokeWidth: 1.5 }}
                  connectNulls
                  isAnimationActive={animate}
                  animationDuration={450}
                  animationEasing="ease-out"
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {series.map((s) => {
          const off = hidden.has(s.id);
          const isBase = s.id === BASELINE_KEY;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => toggle(s.id)}
              aria-pressed={!off}
              className={`flex items-center gap-1.5 rounded px-1 py-0.5 hover:bg-slate-100 dark:hover:bg-slate-800 ${off ? "text-slate-400 line-through" : "text-slate-700 dark:text-slate-200"}`}
            >
              <span
                aria-hidden
                className="inline-block w-4"
                style={{ borderTop: isBase ? `1px dashed ${colorOf(s.id)}` : `2px solid ${colorOf(s.id)}` }}
              />
              {s.label}
            </button>
          );
        })}
        <span className="ml-auto flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
          <span aria-hidden className="inline-block w-4" style={{ borderTop: `1px solid ${floorColor}` }} />
          Floor {fmtDollars(floorCents)}
        </span>
        <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
          <span aria-hidden className="inline-block h-3 w-3 rounded-sm" style={{ background: dark ? "rgba(252,211,77,0.25)" : "rgba(154,90,0,0.18)" }} />
          Below floor
        </span>
      </div>
    </div>
  );
}
