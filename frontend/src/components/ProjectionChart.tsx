// Recharts LineChart: x = month, y = end-of-month balance. Baseline dashed grey; one line per option;
// floor as a ReferenceLine; months below floor tinted for the selected option; legend toggles lines.
import { useMemo, useState } from "react";
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

// Validated categorical palettes (dataviz six checks), one per mode. Baseline is a neutral dashed reference line.
const LIGHT = ["#2f52c9", "#0f8a7a", "#c2410c"];
const DARK = ["#6b8ae8", "#2aa38f", "#d66a2e"];

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

  const grid = dark ? "#1f2937" : "#e2e8f0";
  const axis = dark ? "#94a3b8" : "#64748b";
  const baselineColor = dark ? "#94a3b8" : "#64748b";
  const floorColor = dark ? "#fbbf24" : "#b45309";
  const tint = dark ? "rgba(251,191,36,0.10)" : "rgba(180,83,9,0.08)";
  const negTint = dark ? "rgba(248,113,113,0.12)" : "rgba(185,28,28,0.08)";

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
            margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
            onClick={(e) => {
              const m = monthAt((e as { activeLabel?: string | number } | null)?.activeLabel);
              if (m && onMonthClick) onMonthClick(m);
            }}
          >
            <CartesianGrid stroke={grid} vertical={false} />
            <XAxis
              dataKey="idx"
              type="number"
              domain={[-0.5, rows.length - 0.5]}
              ticks={rows.map((r) => r.idx)}
              tickFormatter={(v: number) => fmtMonthShort(monthAt(v))}
              stroke={axis}
              tick={{ fontSize: 11, fill: axis }}
              tickLine={false}
              axisLine={{ stroke: grid }}
            />
            <YAxis
              tickFormatter={(v: number) => fmtDollars(v)}
              stroke={axis}
              tick={{ fontSize: 11, fill: axis }}
              tickLine={false}
              axisLine={false}
              width={64}
            />
            {tinted.map((m) => {
              const neg = selected?.result.months_negative.includes(m);
              const i = idxOf(m);
              return <ReferenceArea key={m} x1={i - 0.5} x2={i + 0.5} fill={neg ? negTint : tint} stroke="none" />;
            })}
            <ReferenceLine y={0} stroke={axis} strokeOpacity={0.6} />
            <ReferenceLine y={floorCents} stroke={floorColor} strokeDasharray="2 4" />
            <Tooltip
              cursor={{ stroke: axis, strokeWidth: 1 }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-slate-700 dark:bg-slate-900">
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
                    {onMonthClick && <div className="mt-1 text-[10px] text-slate-400">Click for why this month</div>}
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
                  strokeWidth={isSel ? 2.5 : 2}
                  strokeDasharray={isBase ? "6 4" : undefined}
                  strokeOpacity={selectedId && !isSel && !isBase ? 0.55 : 1}
                  dot={{ r: 3, strokeWidth: 0, fill: colorOf(s.id) }}
                  activeDot={{ r: 5, stroke: dark ? "#0f172a" : "#ffffff", strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive={false}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
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
                className="inline-block h-0.5 w-4"
                style={{
                  background: isBase ? "transparent" : colorOf(s.id),
                  borderTop: isBase ? `2px dashed ${colorOf(s.id)}` : undefined,
                }}
              />
              {s.label}
            </button>
          );
        })}
        <span className="ml-auto flex items-center gap-1.5 text-slate-500">
          <span aria-hidden className="inline-block w-4" style={{ borderTop: `2px dotted ${floorColor}` }} />
          Floor {fmtDollars(floorCents)}
        </span>
        <span className="flex items-center gap-1.5 text-slate-500">
          <span aria-hidden className="inline-block h-3 w-3 rounded-sm" style={{ background: tint, border: `1px solid ${floorColor}` }} />
          Below floor
        </span>
      </div>
    </div>
  );
}
