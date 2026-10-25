// "Look ahead" selector. Changing it updates the shared horizon, refetches the baseline, and re-runs the
// current evaluation (if any) so Compare never shows a chart from a different horizon than the store.
import { useState } from "react";
import { api } from "../api";
import { useAppState } from "../state";
import { HORIZONS, HORIZON_ASSUMPTION, backendAssumption } from "../lib/horizon";
import { errorMessage } from "../lib/hooks";
import type { EvaluateResponse, ProjectionResult } from "../types";

export default function HorizonSelect({ id = "horizon" }: { id?: string }) {
  const horizonMonths = useAppState((s) => s.horizonMonths);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const change = async (months: number) => {
    const st = useAppState.getState();
    if (months === st.horizonMonths) return;
    st.setHorizonMonths(months);
    setBusy(true);
    setError(null);
    try {
      const jobs: Promise<unknown>[] = [];
      if (st.profile) jobs.push(api.baseline(months).then((b) => useAppState.getState().setBaseline(b)));
      if (st.inputs && st.evaluation) {
        const { decisionId, inputs } = st;
        jobs.push(
          api.evaluate(decisionId, inputs.inputs, months).then((r) => {
            const now = useAppState.getState();
            if (now.horizonMonths !== months) return; // changed again meanwhile
            now.setEvaluation(r);
            now.prefetchExplanations();
          }),
        );
      }
      await Promise.all(jobs);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
      <label htmlFor={id}>Look ahead</label>
      <select
        id={id}
        value={horizonMonths}
        disabled={busy}
        onChange={(e) => void change(Number(e.target.value))}
        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-800 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-accent-light dark:focus:ring-accent-light"
      >
        {HORIZONS.map((h) => (
          <option key={h.months} value={h.months}>
            {h.label}
          </option>
        ))}
      </select>
      {error && <span className="text-danger">{error}</span>}
    </span>
  );
}

/** One quiet line under a chart when looking past the first year. */
export function HorizonNote({ source }: { source: ProjectionResult | EvaluateResponse | null | undefined }) {
  const horizonMonths = useAppState((s) => s.horizonMonths);
  if (horizonMonths <= 12) return null;
  return <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">{backendAssumption(source) ?? HORIZON_ASSUMPTION}</p>;
}
