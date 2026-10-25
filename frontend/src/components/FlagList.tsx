// Flag list for one projection. Each flag is clickable → parent shows "why this month is tight".
import { useState } from "react";
import type { Flag, FlagSeverity } from "../types";
import { fmtCents, fmtDate, fmtMonth } from "../lib/format";
import { Dot, Empty, type Tone } from "./ui";

const SEV_TONE: Record<FlagSeverity, Tone> = { info: "ok", warn: "warn", danger: "danger" };

export function flagTitle(f: Flag): string {
  switch (f.code) {
    case "below_floor":
      return "Below your safety floor";
    case "negative":
      return "Balance goes negative";
    case "low_slack":
      return "Little monthly slack";
    case "deductible_unaffordable":
      return "Deductible stress test: fails";
    case "deductible_ok":
      return "Deductible stress test: passes";
    case "target_reached":
      return "Stays above floor";
  }
}

const num = (d: Record<string, unknown>, k: string): number | null => (typeof d[k] === "number" ? (d[k] as number) : null);

/** Deductible flag details: fixtures use claim_month/resulting_min_balance_cents, the engine uses claim_date/min_balance_cents. */
function deductibleBits(d: Record<string, unknown>): { ded: string; when: string; res: string | null } {
  const dedC = num(d, "deductible_cents");
  const resC = num(d, "resulting_min_balance_cents") ?? num(d, "min_balance_cents");
  const claim = typeof d.claim_month === "string" ? fmtMonth(d.claim_month) : typeof d.claim_date === "string" ? fmtDate(d.claim_date) : null;
  return { ded: dedC !== null ? fmtCents(dedC) : "deductible", when: claim ? ` on ${claim}` : "", res: resC !== null ? fmtCents(resC) : null };
}

export function flagSummary(f: Flag): string {
  const d = f.detail;
  const min = num(d, "min_balance_cents");
  const floor = num(d, "floor_cents");
  switch (f.code) {
    case "below_floor":
      return min !== null && floor !== null ? `Lowest point ${fmtCents(min)}, floor ${fmtCents(floor)}.` : "Projected balance dips under the floor.";
    case "negative":
      return min !== null ? `Lowest point ${fmtCents(min)}.` : "Projected balance goes below zero.";
    case "deductible_unaffordable": {
      const { ded, when, res } = deductibleBits(d);
      return `A ${ded} claim${when} would leave you at ${res ?? "below the floor"}${floor !== null ? ` against a ${fmtCents(floor)} floor` : ""}.`;
    }
    case "deductible_ok": {
      const { ded, when, res } = deductibleBits(d);
      return `A ${ded} claim${when} would still leave ${res ?? "you above the floor"}${floor !== null ? ` against a ${fmtCents(floor)} floor` : ""}.`;
    }
    case "low_slack":
      return "Recurring costs leave little room for variable spending.";
    case "target_reached": {
      const end = num(d, "end_balance_cents");
      return end !== null ? `Ends the month at ${fmtCents(end)}.` : "Balance stays above the floor.";
    }
  }
}

/** Drop below_floor flags for months that also go negative: the negative flag already says it. */
export function dedupeFlags(flags: Flag[]): Flag[] {
  const negativeMonths = new Set(flags.filter((f) => f.code === "negative" && f.month).map((f) => f.month));
  return flags.filter((f) => !(f.code === "below_floor" && f.month && negativeMonths.has(f.month)));
}

const INITIAL = 6;

export default function FlagList({
  flags,
  activeMonth,
  onSelect,
  collapse = true,
}: {
  flags: Flag[];
  activeMonth?: string | null;
  onSelect?: (flag: Flag) => void;
  /** Show the first few and a "show all" toggle when a projection has many flags (stress scenarios). */
  collapse?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  if (flags.length === 0) return <Empty>No flags for this option. Every month stays above your floor.</Empty>;
  const order: FlagSeverity[] = ["danger", "warn", "info"];
  const sorted = [...flags].sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity) || (a.month ?? "").localeCompare(b.month ?? ""));
  const shown = collapse && !expanded && sorted.length > INITIAL + 1 ? sorted.slice(0, INITIAL) : sorted;
  const hidden = sorted.length - shown.length;
  return (
    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
      {shown.map((f) => {
        const active = !!f.month && f.month === activeMonth;
        return (
          <li key={f.id}>
            <button
              type="button"
              onClick={() => onSelect?.(f)}
              className={`flex w-full items-start gap-3 px-2 py-2.5 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800/60 ${active ? "bg-accent-soft/60 dark:bg-slate-800" : ""}`}
            >
              <Dot tone={SEV_TONE[f.severity]} className="mt-1.5" />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium">{flagTitle(f)}</span>
                  {f.month && <span className="tabular shrink-0 text-xs text-slate-500">{fmtMonth(f.month)}</span>}
                </div>
                <div className="tabular text-xs text-slate-600 dark:text-slate-300">{flagSummary(f)}</div>
              </div>
            </button>
          </li>
        );
      })}
      {hidden > 0 && (
        <li>
          <button type="button" onClick={() => setExpanded(true)} className="w-full px-2 py-2 text-left text-xs font-medium text-accent hover:underline dark:text-accent-light">
            Show <span className="tabular">{hidden}</span> more {hidden === 1 ? "flag" : "flags"}
          </button>
        </li>
      )}
    </ul>
  );
}
