// Option card: label, monthly price with Estimate/Quote/Unsourced badge, key attributes,
// constraint badges, and status styling (disallowed = greyed with reason).
import type { Constraint, Option, ProjectionResult } from "../types";
import { fmtCents, fmtDate, fmtDollars } from "../lib/format";
import { Badge, Dot, type Tone } from "./ui";
import { StatusBadge, constraintShortLabel } from "./ConstraintBadge";

const KIND_TONE: Record<Constraint["kind"], Tone> = { required: "accent", disallowed: "danger", flag: "warn" };

export function PriceBadge({ price }: { price: Option["price"] }) {
  if (price.kind === "user_quote") return <Badge tone="accent">Your quote</Badge>;
  if (price.source_url || price.source_title) {
    // Short badge; the full source title (often a sentence) lives in the tooltip and the link.
    const tip = [price.source_title, price.retrieved ? `Retrieved ${price.retrieved}` : null].filter(Boolean).join(" · ");
    return price.source_url ? (
      <a href={price.source_url} target="_blank" rel="noopener noreferrer" title={tip} className="hover:opacity-80">
        <Badge tone="neutral">Estimate · source</Badge>
      </a>
    ) : (
      <Badge tone="neutral" title={tip}>
        Estimate · source
      </Badge>
    );
  }
  // Estimate with no source attached: say so loudly (design rule §3.6).
  return <Badge tone="danger">Unsourced</Badge>;
}

/** Human-readable summary of auto-insurance attributes; generic fallback for other modules. */
export function describeAttributes(a: Option["attributes"]): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = [];
  const k = (x: unknown) => (typeof x === "number" ? `${Math.round(x / 1000)}k` : String(x));
  if ("bi_per_person" in a && "bi_per_accident" in a && "pd" in a) {
    out.push({ label: "Liability", value: `${k(a.bi_per_person)} / ${k(a.bi_per_accident)} / ${k(a.pd)}` });
  }
  if ("medical" in a) out.push({ label: "Medical", value: `$${Number(a.medical).toLocaleString("en-US")}` });
  if ("tort" in a) out.push({ label: "Tort", value: a.tort === "full" ? "Full" : "Limited" });
  if ("collision" in a || "comprehensive" in a) {
    const both = a.collision && a.comprehensive;
    out.push({ label: "Physical damage", value: both ? "Collision + comprehensive" : a.collision ? "Collision only" : a.comprehensive ? "Comprehensive only" : "None" });
  }
  if ("deductible" in a) out.push({ label: "Deductible", value: Number(a.deductible) > 0 ? `$${Number(a.deductible).toLocaleString("en-US")}` : "n/a" });
  // Rent module (backend/app/decisions/rent/options.py attributes).
  if ("rent_cents" in a) {
    out.push({ label: "Rent", value: `${fmtCents(Number(a.rent_cents))}/mo` });
    if (Number(a.utilities_est_cents) > 0) out.push({ label: "Utilities (est.)", value: `${fmtCents(Number(a.utilities_est_cents))}/mo` });
    out.push({ label: "Move-in", value: fmtCents(Number(a.move_in_cents ?? 0)) }); // deposit + first month
    out.push({ label: "Lease", value: `${a.lease_months} mo from ${fmtDate(String(a.start_date))}` });
    if (Number(a.current_rent_cents) > 0) {
      const delta = Number(a.monthly_housing_cents) - Number(a.current_rent_cents);
      out.push({ label: "vs. today", value: delta === 0 ? "same monthly cost" : `${fmtCents(Math.abs(delta))}/mo ${delta > 0 ? "more" : "less"}` });
    }
  }
  if (out.length === 0) {
    for (const [key, v] of Object.entries(a)) out.push({ label: key.replace(/_/g, " "), value: String(v) });
  }
  return out;
}

export default function OptionCard({
  option,
  constraints,
  projection,
  floorCents,
  selected,
  color,
  onSelect,
}: {
  option: Option;
  constraints: Constraint[];
  projection?: ProjectionResult;
  floorCents: number;
  selected: boolean;
  color?: string;
  onSelect: () => void;
}) {
  const mine = constraints.filter((c) => option.constraint_ids.includes(c.id));
  const disallowed = option.status === "disallowed";
  // Reason an option is disallowed: prefer a required/disallowed constraint that does not apply to every option.
  const reason = disallowed
    ? (mine.find((c) => c.kind !== "flag" && !constraints.every((o) => o.applies_to.length === c.applies_to.length)) ??
        mine.find((c) => c.kind !== "flag"))?.rule
    : undefined;

  const minTone: Tone = projection
    ? projection.min_balance_cents < 0
      ? "danger"
      : projection.min_balance_cents < floorCents
        ? "warn"
        : "ok"
    : "neutral";

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={[
        "w-full rounded-lg border p-4 text-left transition",
        selected
          ? "border-accent ring-1 ring-accent dark:border-accent-light dark:ring-accent-light"
          : "border-slate-200 hover:border-slate-400 dark:border-slate-800 dark:hover:border-slate-600",
        disallowed ? "bg-slate-50 opacity-75 dark:bg-slate-900/50" : "bg-white dark:bg-slate-900",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          {color && <span aria-hidden className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color }} />}
          <div>
            <div className={`text-sm font-semibold ${disallowed ? "text-slate-500 line-through decoration-slate-400" : ""}`}>
              {option.label}
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              <StatusBadge status={option.status} />
              {mine.map((c) => (
                <Badge key={c.id} tone={KIND_TONE[c.kind]} title={c.rule}>
                  {constraintShortLabel(c)}
                </Badge>
              ))}
            </div>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className={`tabular text-lg font-semibold ${disallowed ? "text-slate-500" : ""}`}>{fmtCents(option.price.cents)}</div>
          <div className="text-xs text-slate-500">per month</div>
          <div className="mt-1 flex justify-end">
            <PriceBadge price={option.price} />
          </div>
        </div>
      </div>

      {reason && <p className="mt-3 text-xs text-danger dark:text-red-300">{reason}</p>}

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        {describeAttributes(option.attributes).map((row) => (
          <div key={row.label} className="flex justify-between gap-2 border-b border-slate-100 py-0.5 dark:border-slate-800">
            <dt className="text-slate-500">{row.label}</dt>
            <dd className="tabular font-medium">{row.value}</dd>
          </div>
        ))}
      </dl>

      {projection && (
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <Dot tone={minTone} />
          <span>
            Lowest point <span className="tabular font-medium">{fmtDollars(projection.min_balance_cents)}</span>
            {projection.months_below_floor.length > 0 && (
              <>
                {" · "}
                <span className="tabular">{projection.months_below_floor.length}</span>{" "}
                {projection.months_below_floor.length === 1 ? "month" : "months"} below floor
              </>
            )}
          </span>
        </div>
      )}
    </button>
  );
}
