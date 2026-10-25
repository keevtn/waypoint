// Projection horizon ("Look ahead"). One shared value in the store, sent as `horizon_months` to
// /projection/baseline and every /evaluate. 12 keeps the original layout; longer horizons tick by year.
import type { EvaluateResponse, ProjectionResult } from "../types";

export const DEFAULT_HORIZON_MONTHS = 12;

export const HORIZONS: { months: number; label: string }[] = [
  { months: 12, label: "1 year" },
  { months: 60, label: "5 years" },
  { months: 120, label: "10 years" },
];

export const horizonLabel = (months: number): string => HORIZONS.find((h) => h.months === months)?.label ?? `${months} months`;

/** Shown under a chart when the horizon is over 12 months and the backend has not sent its own sentence yet. */
export const HORIZON_ASSUMPTION =
  "Beyond the first year, income, bills and typical spending are assumed to continue unchanged, with no raises, rent increases, or new one-time costs.";

/** The backend's assumption string for a long horizon, when present on a baseline or evaluation. */
export function backendAssumption(source: ProjectionResult | EvaluateResponse | null | undefined): string | null {
  if (!source) return null;
  const r = source as unknown as Record<string, unknown>;
  for (const key of ["assumption", "horizon_assumption", "horizon_note", "assumptions"]) {
    const v = r[key];
    if (typeof v === "string" && v.trim()) return v;
    if (Array.isArray(v) && v.every((x) => typeof x === "string") && v.length > 0) return (v as string[]).join(" ");
  }
  return null;
}
