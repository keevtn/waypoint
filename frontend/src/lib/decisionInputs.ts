// Frontend-side input types for each decision module. `types.ts` is the shared contract and only
// changes via a contract commit; RentInputs mirrors backend/app/decisions/rent/inputs.py here.
import type { AutoInsuranceInputs, BigPurchaseInputs, Suggestion } from "../types";

export interface RentUnit {
  label: string;
  rent_cents: number;
  deposit_cents: number;
  utilities_est_cents: number;
  lease_months: number;
  start_date: string; // ISO date
}

export interface RentInputs {
  units: RentUnit[]; // 2 to 4
  current_rent_cents: number | null; // null = use the rent detected in transactions
}

export type DecisionInputs =
  | { decisionId: "auto_insurance"; inputs: AutoInsuranceInputs }
  | { decisionId: "rent"; inputs: RentInputs }
  | { decisionId: "big_purchase"; inputs: BigPurchaseInputs };

export const isAutoInputs = (d: DecisionInputs | null): d is { decisionId: "auto_insurance"; inputs: AutoInsuranceInputs } =>
  d?.decisionId === "auto_insurance";
export const isRentInputs = (d: DecisionInputs | null): d is { decisionId: "rent"; inputs: RentInputs } => d?.decisionId === "rent";
export const isBigPurchaseInputs = (d: DecisionInputs | null): d is { decisionId: "big_purchase"; inputs: BigPurchaseInputs } =>
  d?.decisionId === "big_purchase";

/**
 * Merge a suggestion's `patch` into the current inputs (one level deep, so `{financing: {...}}` replaces the
 * whole financing object, matching how the backend computed the suggestion). Returns the same shape, tagged.
 */
export function applySuggestionPatch(d: DecisionInputs, s: Suggestion): DecisionInputs {
  const merged = { ...(d.inputs as unknown as Record<string, unknown>), ...s.patch };
  return { decisionId: d.decisionId, inputs: merged } as unknown as DecisionInputs;
}

/** Module-aware copy shared by Compare and Stress. */
export const baselineLabel = (decisionId: string): string =>
  decisionId === "rent" ? "Baseline (stay put)" : decisionId === "big_purchase" ? "Baseline (don't buy)" : "Baseline (no policy)";

export const priceFootnote = (decisionId: string): string =>
  decisionId === "rent"
    ? "Monthly figures are the rent and utilities you entered. Confirm what is included before you sign."
    : decisionId === "big_purchase"
      ? "Plans marked Estimate use an assumed APR, not a lender's offer. Enter your lender's terms to replace it."
      : "Prices marked Estimate come from a cited public source, not a carrier. Get real quotes before you decide.";

/** 2499 bps -> "24.99%". */
export const fmtApr = (bps: number): string => `${(bps / 100).toFixed(2).replace(/\.?0+$/, "")}%`;
