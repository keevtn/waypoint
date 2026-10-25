// Frontend-side input types for each decision module. `types.ts` is the shared contract and only
// changes via a contract commit; RentInputs mirrors backend/app/decisions/rent/inputs.py here.
import type { AutoInsuranceInputs } from "../types";

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

export type DecisionInputs = { decisionId: "auto_insurance"; inputs: AutoInsuranceInputs } | { decisionId: "rent"; inputs: RentInputs };

export const isAutoInputs = (d: DecisionInputs | null): d is { decisionId: "auto_insurance"; inputs: AutoInsuranceInputs } =>
  d?.decisionId === "auto_insurance";
export const isRentInputs = (d: DecisionInputs | null): d is { decisionId: "rent"; inputs: RentInputs } => d?.decisionId === "rent";

/** Module-aware copy shared by Compare and Stress. */
export const baselineLabel = (decisionId: string): string => (decisionId === "rent" ? "Baseline (stay put)" : "Baseline (no policy)");
export const priceFootnote = (decisionId: string): string =>
  decisionId === "rent"
    ? "Monthly figures are the rent and utilities you entered. Confirm what is included before you sign."
    : "Prices marked Estimate come from a cited public source, not a carrier. Get real quotes before you decide.";
