// Citation chip: opens the source URL; hover shows publisher + excerpt.
// Also exports CitedText, which renders [s:chunk] and [c:constraint] markers inline.
import type { ReactNode } from "react";
import type { Citation, Constraint } from "../types";

export default function CitationChip({ citation, index }: { citation: Citation; index?: number }) {
  const tip = `${citation.publisher}${citation.year ? ` (${citation.year})` : ""}: ${citation.excerpt}`;
  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noopener noreferrer"
      title={tip}
      className="inline-flex max-w-full items-center gap-1 rounded-sm border border-slate-300 bg-slate-50 px-1.5 py-0.5 align-baseline text-[11px] font-medium leading-4 text-slate-700 hover:border-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
    >
      {index !== undefined && <span className="tabular">[{index}]</span>}
      <span className="truncate">{citation.publisher}</span>
    </a>
  );
}

/** Missing chunk → explicit "Unsourced" badge (should never happen in the demo). */
export function UnsourcedChip({ id }: { id: string }) {
  return (
    <span
      title={`No citation found for ${id}`}
      className="inline-flex items-center rounded border border-danger/40 bg-red-50 px-1.5 py-0.5 text-[11px] font-medium leading-4 text-danger dark:bg-red-950/40 dark:text-red-300"
    >
      Unsourced
    </span>
  );
}

const MARKER = /\[(s|c):([^\]\s]+)\]/g;

/**
 * Renders text containing [s:chunk_id] (source) and [c:constraint_id] (constraint) markers.
 * Sources become CitationChips; constraints become small tags with the rule as tooltip.
 */
export function CitedText({
  text,
  citations,
  constraints = [],
}: {
  text: string;
  citations: Citation[];
  constraints?: Constraint[];
}) {
  const parts: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(MARKER)) {
    const start = m.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    const [, kind, id] = m;
    // No trailing gap when punctuation follows the marker.
    const after = text[start + m[0].length] ?? "";
    const gap = /[.,;:)]/.test(after) ? "ml-0.5" : "mx-0.5";
    if (kind === "s") {
      const c = citations.find((x) => x.chunk_id === id);
      parts.push(
        <span key={key++} className={gap}>
          {c ? <CitationChip citation={c} index={citations.indexOf(c) + 1} /> : <UnsourcedChip id={id} />}
        </span>,
      );
    } else {
      const rule = constraints.find((x) => x.id === id)?.rule;
      parts.push(
        <span
          key={key++}
          title={rule ?? id}
          className={`${gap} inline-flex items-center rounded border border-slate-300 bg-slate-50 px-1 py-0.5 align-baseline text-[11px] leading-4 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300`}
        >
          rule
        </span>,
      );
    }
    last = start + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}
