// Constraint badge: kind-coloured pill with the rule as a tooltip.
import type { Constraint, OptionStatus } from "../types";
import { Badge, type Tone } from "./ui";

const KIND_LABEL: Record<Constraint["kind"], string> = {
  required: "Required",
  disallowed: "Not allowed",
  flag: "Flagged",
};

const KIND_TONE: Record<Constraint["kind"], Tone> = {
  required: "accent",
  disallowed: "danger",
  flag: "warn",
};

export default function ConstraintBadge({ constraint }: { constraint: Constraint }) {
  return (
    <Badge tone={KIND_TONE[constraint.kind]} title={constraint.rule}>
      {KIND_LABEL[constraint.kind]}
      {constraint.citation_ids.length > 0 && <span className="opacity-60">· sourced</span>}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: OptionStatus }) {
  if (status === "disallowed") return <Badge tone="danger">Not allowed</Badge>;
  if (status === "flagged") return <Badge tone="warn">Flagged</Badge>;
  return <Badge tone="ok">Fits</Badge>;
}

/** Short label for a constraint that is more specific than its kind, derived from its id. */
export function constraintShortLabel(c: Constraint): string {
  if (/lender/i.test(c.id)) return "Required by lender";
  if (/minimum|state/i.test(c.id)) return "State minimum";
  if (/deductible/i.test(c.id)) return "Deductible comfort";
  if (/tort/i.test(c.id)) return "Limited tort";
  return KIND_LABEL[c.kind];
}
