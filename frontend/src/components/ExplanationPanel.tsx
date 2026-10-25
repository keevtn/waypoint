// Explanation for the selected option: verdict, pros, cons, citation chips. Skeleton while the LLM call runs.
import type { Constraint, Explanation, Flag } from "../types";
import { fmtCents, fmtDate, fmtMonth } from "../lib/format";
import CitationChip, { CitedText } from "./CitationChip";
import { Card, Skeleton, SkeletonLines } from "./ui";

export function ExplanationSkeleton() {
  return (
    <Card title="Why this option" aside={<span className="text-xs text-slate-400">Writing explanation…</span>}>
      <Skeleton className="mb-3 h-4 w-11/12" />
      <div className="grid gap-4 sm:grid-cols-2">
        <SkeletonLines n={3} />
        <SkeletonLines n={3} />
      </div>
    </Card>
  );
}

export default function ExplanationPanel({
  explanation,
  constraints,
  optionLabel,
}: {
  explanation: Explanation | null;
  constraints: Constraint[];
  optionLabel: string;
}) {
  if (!explanation) {
    return (
      <Card title="Why this option">
        <p className="text-sm text-slate-500 dark:text-slate-400">No explanation for {optionLabel}.</p>
      </Card>
    );
  }
  const cites = explanation.citations;
  return (
    <Card title="Why this option">
      <p className="text-sm leading-6">
        <CitedText text={explanation.verdict} citations={cites} constraints={constraints} />
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-medium text-ok">For</h3>
          <ul className="space-y-1.5 text-sm">
            {explanation.pros.map((p, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ok" />
                <span>
                  <CitedText text={p} citations={cites} constraints={constraints} />
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium text-warn">Against</h3>
          <ul className="space-y-1.5 text-sm">
            {explanation.cons.map((p, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" />
                <span>
                  <CitedText text={p} citations={cites} constraints={constraints} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      {cites.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-3 dark:border-slate-800">
          <h3 className="mb-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">Sources</h3>
          <ol className="space-y-1 text-xs">
            {cites.map((c, i) => (
              <li key={c.chunk_id} className="flex items-start gap-2">
                <CitationChip citation={c} index={i + 1} />
                <span className="text-slate-600 dark:text-slate-300">
                  {c.title}
                  {c.year ? ` (${c.year})` : ""}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Card>
  );
}

/** "Why this month is tight": explanation's tight_months.why, falling back to the flag's contributors. */
export function TightMonthPanel({
  month,
  explanation,
  flag,
  loading,
  onClose,
}: {
  month: string;
  explanation: Explanation | null;
  flag: Flag | null;
  loading: boolean;
  onClose: () => void;
}) {
  const why = explanation?.tight_months.find((t) => t.month === month)?.why ?? null;
  const contributors = (flag?.detail.contributors as { id: string; label: string; amount_cents: number; date: string }[] | undefined) ?? [];
  return (
    <Card
      title={`Why ${fmtMonth(month)} is tight`}
      aside={
        <button type="button" onClick={onClose} className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200">
          Close
        </button>
      }
    >
      {loading && !why ? (
        <SkeletonLines n={2} />
      ) : why ? (
        <p className="text-sm leading-6">{why}</p>
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {contributors.length > 0 ? "One-time costs this month:" : "No narrative for this month yet."}
        </p>
      )}
      {contributors.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 text-sm dark:divide-slate-800">
          {contributors.map((c) => (
            <li key={c.id} className="flex items-baseline justify-between py-1.5">
              <span>
                {c.label} <span className="text-xs text-slate-500 dark:text-slate-400">{fmtDate(c.date)}</span>
              </span>
              <span className="tabular font-medium">{fmtCents(c.amount_cents)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
