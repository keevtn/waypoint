// Shared store: profile, baseline, decision inputs, evaluate result, chosen option, explanations.
import { create } from "zustand";
import { ApiError, api } from "./api";
import { friendlyError } from "./lib/hooks";
import type { DecisionInputs } from "./lib/decisionInputs";
import type { ActionCard, EvaluateResponse, Explanation, Profile, ProjectionResult, StressResponse } from "./types";

interface AppState {
  profile: Profile | null;
  baseline: ProjectionResult | null;
  decisionId: string;
  /** The inputs behind `evaluation`, tagged with their module. */
  inputs: DecisionInputs | null;
  evaluation: EvaluateResponse | null;
  /** Bumps when the user runs a new evaluation (not on a transparent eval_id refresh). */
  evalGen: number;
  explanations: Explanation[] | null; // null = not loaded yet for this evaluation
  explainStatus: "idle" | "loading" | "ready" | "error";
  explainError: string | null;
  selectedOptionId: string | null;
  stress: StressResponse | null; // keyed implicitly by evaluation; cleared on setEvaluation
  actionCard: ActionCard | null; // for selectedOptionId; cleared when the option changes
  setProfile: (p: Profile | null) => void;
  setBaseline: (b: ProjectionResult | null) => void;
  /** Record the module + inputs about to be evaluated. */
  setInputs: (i: DecisionInputs) => void;
  setEvaluation: (e: EvaluateResponse | null) => void;
  setExplanations: (x: Explanation[] | null) => void;
  /** Kick off /explain for the current evaluation (idempotent). Called right after /evaluate returns so Compare is instant. */
  prefetchExplanations: () => void;
  /**
   * Run an eval-scoped call. If the server has forgotten the eval_id (404 unknown_eval, e.g. after a restart or the
   * 1h cache TTL), re-run /evaluate with the stored inputs, swap in the new eval_id, and retry once.
   */
  withFreshEval: <T>(call: (evalId: string) => Promise<T>) => Promise<T>;
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
  evalGen: 0,
  explanations: null,
  explainStatus: "idle",
  explainError: null,
  selectedOptionId: null,
  stress: null,
  actionCard: null,
  setProfile: (profile) => set({ profile }),
  setBaseline: (baseline) => set({ baseline }),
  setInputs: (inputs) => set({ inputs, decisionId: inputs.decisionId }),
  setEvaluation: (evaluation) =>
    set((s) => ({
      evaluation,
      evalGen: s.evalGen + 1,
      explanations: null,
      explainStatus: "idle",
      explainError: null,
      stress: null,
      actionCard: null,
      // Preselect the first option the user may actually choose.
      selectedOptionId: evaluation?.options.find((o) => o.status !== "disallowed")?.id ?? null,
    })),
  setExplanations: (explanations) => set({ explanations, explainStatus: explanations ? "ready" : "idle", explainError: null }),
  prefetchExplanations: () => {
    const { evaluation, decisionId, explainStatus, evalGen } = get();
    if (!evaluation || explainStatus === "loading" || explainStatus === "ready") return;
    set({ explainStatus: "loading", explainError: null });
    get()
      .withFreshEval((evalId) => api.explain(decisionId, evalId))
      .then(
        (r) => {
          // Ignore a late response for an evaluation the user has since replaced.
          if (get().evalGen !== evalGen) return;
          set({ explanations: r.explanations, explainStatus: "ready", explainError: null });
        },
        (e: unknown) => {
          if (get().evalGen !== evalGen) return;
          set({ explainStatus: "error", explainError: friendlyError(e) });
        },
      );
  },
  withFreshEval: async (call) => {
    const first = get().evaluation;
    if (!first) throw new Error("No evaluation to work from.");
    try {
      return await call(first.eval_id);
    } catch (e) {
      if (!isUnknownEval(e)) throw e;
      const { inputs, decisionId, evalGen } = get();
      if (!inputs) throw e;
      // Re-evaluate silently with the inputs the user already entered; deterministic, so the options are the same.
      const fresh = await (refreshing ??= api.evaluate(decisionId, inputs.inputs).finally(() => (refreshing = null)));
      if (get().evalGen !== evalGen) throw e; // user started a new evaluation meanwhile
      set((s) => ({
        evaluation: fresh,
        selectedOptionId: fresh.options.some((o) => o.id === s.selectedOptionId)
          ? s.selectedOptionId
          : (fresh.options.find((o) => o.status !== "disallowed")?.id ?? null),
      }));
      return await call(fresh.eval_id);
    }
  },
  selectOption: (selectedOptionId) =>
    set((s) => (s.selectedOptionId === selectedOptionId ? {} : { selectedOptionId, actionCard: null })),
  setStress: (stress) => set({ stress }),
  setActionCard: (actionCard) => set({ actionCard }),
}));

export const isUnknownEval = (e: unknown): boolean => e instanceof ApiError && e.status === 404 && e.code === "unknown_eval";

// One in-flight re-evaluate shared by concurrent callers (explain prefetch + action can both hit a stale id).
let refreshing: Promise<EvaluateResponse> | null = null;

export { fmtCents } from "./lib/format";
