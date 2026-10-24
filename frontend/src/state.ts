// Shared store: profile, baseline, decision inputs, evaluate result, chosen option, explanations.
import { create } from "zustand";
import type { AutoInsuranceInputs, EvaluateResponse, Explanation, Profile, ProjectionResult } from "./types";

interface AppState {
  profile: Profile | null;
  baseline: ProjectionResult | null;
  decisionId: string;
  inputs: AutoInsuranceInputs | null;
  evaluation: EvaluateResponse | null;
  explanations: Explanation[] | null; // null = not loaded yet for this evaluation
  selectedOptionId: string | null;
  setProfile: (p: Profile | null) => void;
  setBaseline: (b: ProjectionResult | null) => void;
  setInputs: (i: AutoInsuranceInputs) => void;
  setEvaluation: (e: EvaluateResponse | null) => void;
  setExplanations: (x: Explanation[] | null) => void;
  selectOption: (id: string | null) => void;
}

export const useAppState = create<AppState>((set) => ({
  profile: null,
  baseline: null,
  decisionId: "auto_insurance",
  inputs: null,
  evaluation: null,
  explanations: null,
  selectedOptionId: null,
  setProfile: (profile) => set({ profile }),
  setBaseline: (baseline) => set({ baseline }),
  setInputs: (inputs) => set({ inputs }),
  setEvaluation: (evaluation) =>
    set({
      evaluation,
      explanations: null,
      // Preselect the first option the user may actually choose.
      selectedOptionId: evaluation?.options.find((o) => o.status !== "disallowed")?.id ?? null,
    }),
  setExplanations: (explanations) => set({ explanations }),
  selectOption: (selectedOptionId) => set({ selectedOptionId }),
}));

export { fmtCents } from "./lib/format";
