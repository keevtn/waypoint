// Suggestions: code-computed alternatives from /evaluate (`EvaluateResponse.suggestions`). "Try this"
// merges the suggestion's patch into the inputs and re-runs /evaluate; nothing here is LLM-generated.
// The applied suggestion reads as selected (accent border, "Applied"); the others stay neutral.
import type { Option, Suggestion } from "../types";
import { fmtCents, fmtDate } from "../lib/format";
import { Badge, Button } from "./ui";

const TYPE_LABEL: Record<Suggestion["type"], string> = {
  earliest_safe_date: "Wait",
  safest_financing: "Finance differently",
  wait_beyond_horizon: "Not yet",
};

export default function SuggestionsPanel({
  suggestions,
  options,
  floorCents,
  applyingId,
  appliedId,
  onApply,
}: {
  suggestions: Suggestion[];
  options: Option[];
  floorCents: number;
  applyingId: string | null;
  appliedId: string | null;
  onApply: (s: Suggestion) => void;
}) {
  if (suggestions.length === 0) return null;
  const labelFor = (optionId: string) => options.find((o) => o.id === optionId)?.label ?? optionId;
  return (
    <section>
      <header className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="text-xs font-medium text-slate-500 dark:text-slate-400">Ways to keep your floor</h2>
      </header>
      <ul className="grid gap-3 md:grid-cols-2">
        {suggestions.map((s) => {
          const actionable = Object.keys(s.patch).length > 0;
          const applied = s.id === appliedId;
          const p = s.projected;
          const ok = p.min_balance_cents >= floorCents;
          return (
            <li
              key={s.id}
              aria-current={applied ? "true" : undefined}
              className={`flex flex-col rounded-md border p-5 ${
                applied
                  ? "border-accent bg-accent-soft/50 ring-1 ring-inset ring-accent dark:border-accent-light dark:bg-slate-800 dark:ring-accent-light"
                  : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="font-medium">{s.label}</div>
                {applied ? <Badge tone="accent">Applied</Badge> : <Badge tone="neutral">{TYPE_LABEL[s.type]}</Badge>}
              </div>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{s.rationale}</p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Lowest point</div>
                  <div className={`tabular mt-0.5 text-xl font-semibold leading-none ${ok ? "text-ok dark:text-green-300" : "text-danger dark:text-red-300"}`}>
                    {fmtCents(p.min_balance_cents)}
                  </div>
                  <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{fmtDate(p.min_balance_date)}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">{typeof p.cash_gap_cents === "number" ? "Still short by" : "Total cost"}</div>
                  <div className={`tabular mt-0.5 text-xl font-semibold leading-none ${typeof p.cash_gap_cents === "number" ? "text-danger dark:text-red-300" : ""}`}>
                    {fmtCents(typeof p.cash_gap_cents === "number" ? p.cash_gap_cents : p.total_cost_cents)}
                  </div>
                  <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{labelFor(p.option_id)}</div>
                </div>
              </div>
              {actionable && !applied && (
                <div className="mt-3 flex justify-end">
                  <Button variant="secondary" className="px-2.5 py-1 text-xs" disabled={applyingId !== null} onClick={() => onApply(s)}>
                    {applyingId === s.id ? "Re-running…" : "Try this"}
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
