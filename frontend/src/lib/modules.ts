// Fixed product order for the decision modules. The frontend never relies on the order GET /decisions
// returns: the Moment picker, the landing page, and any default use this list.
import type { DecisionSummary } from "../types";

export const MODULE_ORDER = ["big_purchase", "rent", "auto_insurance"] as const;
export type ModuleId = (typeof MODULE_ORDER)[number];

export const DEFAULT_MODULE: ModuleId = MODULE_ORDER[0];

export const isModuleId = (id: unknown): id is ModuleId => typeof id === "string" && (MODULE_ORDER as readonly string[]).includes(id);

/** One-line copy per module, used by the picker and the landing page in place of the API description. */
export const MODULE_COPY: Record<ModuleId, { title: string; line: string }> = {
  big_purchase: { title: "Big purchase", line: "Can I afford this, and if not, what would make it a yes?" },
  rent: { title: "Rent", line: "Which of these units fits my income, and what does a 12-month lease do to my summer?" },
  auto_insurance: { title: "Auto insurance", line: "Which coverage am I allowed to buy, and what does each one do to my year?" },
};

const rank = (id: string) => {
  const i = (MODULE_ORDER as readonly string[]).indexOf(id);
  return i === -1 ? MODULE_ORDER.length : i;
};

/** Sort API decision summaries into the fixed product order; unknown modules keep their API order at the end. */
export const orderModules = (decisions: DecisionSummary[]): DecisionSummary[] =>
  decisions
    .map((d, i) => ({ d, i }))
    .sort((a, b) => rank(a.d.id) - rank(b.d.id) || a.i - b.i)
    .map((x) => x.d);
