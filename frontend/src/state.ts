// Tiny shared store: profile, decision inputs, evaluate result, chosen option.
import { create } from "zustand";
import type { AutoInsuranceInputs, EvaluateResponse, Profile } from "./types";

interface AppState {
  profile: Profile | null;
  decisionId: string;
  inputs: AutoInsuranceInputs | null;
  evaluation: EvaluateResponse | null;
  selectedOptionId: string | null;
  setProfile: (p: Profile | null) => void;
  setInputs: (i: AutoInsuranceInputs) => void;
  setEvaluation: (e: EvaluateResponse | null) => void;
  selectOption: (id: string | null) => void;
}

export const useAppState = create<AppState>((set) => ({
  profile: null,
  decisionId: "auto_insurance",
  inputs: null,
  evaluation: null,
  selectedOptionId: null,
  setProfile: (profile) => set({ profile }),
  setInputs: (inputs) => set({ inputs }),
  setEvaluation: (evaluation) => set({ evaluation, selectedOptionId: null }),
  selectOption: (selectedOptionId) => set({ selectedOptionId }),
}));

export const fmtCents = (cents: number): string =>
  (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
