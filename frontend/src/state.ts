// Shared store: profile, baseline, decision inputs, evaluate result, chosen option, explanations.
import { create } from "zustand";
import { api } from "./api";
import { friendlyError } from "./lib/hooks";
import type { ActionCard, AutoInsuranceInputs, EvaluateResponse, Explanation, Profile, ProjectionResult, StressResponse } from "./types";

interface AppState {
  profile: Profile | null;
  baseline: ProjectionResult | null;
  decisionId: string;
  inputs: AutoInsuranceInputs | null;
  evaluation: EvaluateResponse | null;
  explanations: Explanation[] | null; // null = not loaded yet for this evaluation
  explainStatus: "idle" | "loading" | "ready" | "error";
  explainError: string | null;
  selectedOptionId: string | null;
  stress: StressResponse | null; // keyed implicitly by evaluation; cleared on setEvaluation
  actionCard: ActionCard | null; // for selectedOptionId; cleared when the option changes
  setProfile: (p: Profile | null) => void;
  setBaseline: (b: ProjectionResult | null) => void;
  setInputs: (i: AutoInsuranceInputs) => void;
  setEvaluation: (e: EvaluateResponse | null) => void;
  setExplanations: (x: Explanation[] | null) => void;
  /** Kick off /explain for the current evaluation (idempotent). Called right after /evaluate returns so Compare is instant. */
  prefetchExplanations: () => void;
  selectOption: (id: string | null) => void;
  setStress: (s: StressResponse | null) => void;
  setActionCard: (a: ActionCard | null) => void;
}

export const useAppState = create<AppState>((set, get) => ({
  profile: null,
  baseline: null,
  decisionId: "auto_insurance",
  inputs: null,
  evaluation: null,
  explanations: null,
  explainStatus: "idle",
  explainError: null,
  selectedOptionId: null,
  stress: null,
  actionCard: null,
  setProfile: (profile) => set({ profile }),
  setBaseline: (baseline) => set({ baseline }),
  setInputs: (inputs) => set({ inputs }),
  setEvaluation: (evaluation) =>
    set({
      evaluation,
      explanations: null,
      explainStatus: "idle",
      explainError: null,
      stress: null,
      actionCard: null,
      // Preselect the first option the user may actually choose.
      selectedOptionId: evaluation?.options.find((o) => o.status !== "disallowed")?.id ?? null,
    }),
  setExplanations: (explanations) => set({ explanations, explainStatus: explanations ? "ready" : "idle", explainError: null }),
  prefetchExplanations: () => {
    const { evaluation, decisionId, explainStatus } = get();
    if (!evaluation || explainStatus === "loading" || explainStatus === "ready") return;
    const evalId = evaluation.eval_id;
    set({ explainStatus: "loading", explainError: null });
    api.explain(decisionId, evalId).then(
      (r) => {
        // Ignore a late response for an evaluation the user has since replaced.
        if (get().evaluation?.eval_id !== evalId) return;
        set({ explanations: r.explanations, explainStatus: "ready", explainError: null });
      },
      (e: unknown) => {
        if (get().evaluation?.eval_id !== evalId) return;
        set({ explainStatus: "error", explainError: friendlyError(e) });
      },
    );
  },
  selectOption: (selectedOptionId) =>
    set((s) => (s.selectedOptionId === selectedOptionId ? {} : { selectedOptionId, actionCard: null })),
  setStress: (stress) => set({ stress }),
  setActionCard: (actionCard) => set({ actionCard }),
}));

export { fmtCents } from "./lib/format";
