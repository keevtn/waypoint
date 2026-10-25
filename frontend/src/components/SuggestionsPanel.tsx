// Suggestions: code-computed alternatives from /evaluate (`EvaluateResponse.suggestions`). "Try this"
// merges the suggestion's patch into the inputs and re-runs /evaluate; nothing here is LLM-generated.
import type { Option, Suggestion } from "../types";
import { fmtCents, fmtDate } from "../lib/format";
import { Badge, Button, Card } from "./ui";

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
  onApply,
}: {
  suggestions: Suggestion[];
  options: Option[];
  floorCents: number;
  applyingId: string | null;
  onApply: (s: Suggestion) => void;
}) {
  if (suggestions.length === 0) return null;
  const labelFor = (optionId: string) => options.find((o) => o.id === optionId)?.label ?? optionId;
  return (
    <Card title="Ways to keep your floor" aside={<span className="text-xs text-slate-500">Computed from your projection</span>}>
      <ul className="grid gap-3 md:grid-cols-2">
        {suggestions.map((s) => {
          const actionable = Object.keys(s.patch).length > 0;
          const p = s.projected;
          const ok = p.min_balance_cents >= floorCents;
          return (
            <li key={s.id} className="flex flex-col rounded-md border border-slate-200 p-3 dark:border-slate-800">
              <div className="flex items-start justify-between gap-2">
                <div className="font-medium">{s.label}</div>
                <Badge tone={actionable ? "accent" : "warn"}>{TYPE_LABEL[s.type]}</Badge>
              </div>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{s.rationale}</p>
              <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                <dt className="text-slate-500">Lowest point</dt>
                <dd className={`tabular text-right font-medium ${ok ? "text-ok" : "text-danger"}`}>
                  {fmtCents(p.min_balance_cents)} <span className="font-normal text-slate-500">({fmtDate(p.min_balance_date)})</span>
                </dd>
                <dt className="text-slate-500">Total cost</dt>
                <dd className="tabular text-right font-medium">{fmtCents(p.total_cost_cents)}</dd>
                {typeof p.cash_gap_cents === "number" && (
                  <>
                    <dt className="text-slate-500">Still short by</dt>
                    <dd className="tabular text-right font-medium text-danger">{fmtCents(p.cash_gap_cents)}</dd>
                  </>
                )}
                <dt className="text-slate-500">Lands on</dt>
                <dd className="text-right">{labelFor(p.option_id)}</dd>
              </dl>
              {actionable && (
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
    </Card>
  );
}
