// Flag list for one projection. Each flag is clickable → parent shows "why this month is tight".
import type { Flag, FlagSeverity } from "../types";
import { fmtCents, fmtMonth } from "../lib/format";
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
      const ded = num(d, "deductible_cents");
      const res = num(d, "resulting_min_balance_cents");
      return `A ${ded !== null ? fmtCents(ded) : ""} claim${d.claim_month ? ` in ${fmtMonth(String(d.claim_month))}` : ""} would leave you at ${res !== null ? fmtCents(res) : "below the floor"}.`;
    }
    case "deductible_ok": {
      const ded = num(d, "deductible_cents");
      const res = num(d, "resulting_min_balance_cents");
      return `A ${ded !== null ? fmtCents(ded) : ""} claim${d.claim_month ? ` in ${fmtMonth(String(d.claim_month))}` : ""} would still leave ${res !== null ? fmtCents(res) : "you above the floor"}.`;
    }
    case "low_slack":
      return "Recurring costs leave little room for variable spending.";
    case "target_reached": {
      const end = num(d, "end_balance_cents");
      return end !== null ? `Ends the month at ${fmtCents(end)}.` : "Balance stays above the floor.";
    }
  }
}

export default function FlagList({
  flags,
  activeMonth,
  onSelect,
}: {
  flags: Flag[];
  activeMonth?: string | null;
  onSelect?: (flag: Flag) => void;
}) {
  if (flags.length === 0) return <Empty>No flags for this option. Every month stays above your floor.</Empty>;
  const order: FlagSeverity[] = ["danger", "warn", "info"];
  const sorted = [...flags].sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity) || (a.month ?? "").localeCompare(b.month ?? ""));
  return (
    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
      {sorted.map((f) => {
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
    </ul>
  );
}
