// Typed fetch wrappers mirroring SPEC.md §7.
// VITE_USE_FIXTURES=1 serves backend/fixtures/*.json instead of fetching /api.
import type {
  ActionCard,
  ConnectResponse,
  DecisionSummary,
  ErrorResponse,
  EvaluateResponse,
  ExplainResponse,
  HealthResponse,
  Profile,
  ProjectionResult,
  RagAskResponse,
  StressResponse,
  Transaction,
} from "./types";

export const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === "1";

const fixtureFiles = import.meta.glob("../../backend/fixtures/*.json", { eager: true, import: "default" }) as Record<
  string,
  unknown
>;

// Fixture mode: LLM-backed calls take 5–15s live, so add a short delay to exercise loading states.
const slow = <T,>(v: T, ms = 900): Promise<T> => new Promise((r) => setTimeout(() => r(v), ms));

function fixture<T>(name: string, fallback?: string): T {
  const key = `../../backend/fixtures/${name}.json`;
  const data = fixtureFiles[key] ?? (fallback ? fixtureFiles[`../../backend/fixtures/${fallback}.json`] : undefined);
  if (data === undefined) throw new Error(`Missing fixture ${name}`);
  return data as T;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let code = "http_error";
    let message = res.statusText;
    try {
      const body = (await res.json()) as ErrorResponse;
      code = body.error.code;
      message = body.error.message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () =>
    USE_FIXTURES
      ? Promise.resolve<HealthResponse>({ ok: true, data_mode: "local", index_chunks: 0 })
      : request<HealthResponse>("/health"),

  connect: () =>
    USE_FIXTURES ? Promise.resolve(fixture<ConnectResponse>("connect")) : post<ConnectResponse>("/bank/connect", {}),

  profile: () => (USE_FIXTURES ? Promise.resolve(fixture<Profile>("profile")) : request<Profile>("/profile")),

  updateProfile: (patch: Partial<Pick<Profile, "safety_floor_cents" | "one_offs" | "recurring">>) =>
    USE_FIXTURES
      ? Promise.resolve({ ...fixture<Profile>("profile"), ...patch })
      : request<Profile>("/profile", { method: "PUT", body: JSON.stringify(patch) }),

  transactions: (limit = 50) =>
    USE_FIXTURES
      ? Promise.resolve(fixture<Transaction[]>("transactions").slice(0, limit))
      : request<Transaction[]>(`/profile/transactions?limit=${limit}`),

  baseline: () =>
    USE_FIXTURES ? Promise.resolve(fixture<ProjectionResult>("baseline")) : request<ProjectionResult>("/projection/baseline"),

  decisions: () =>
    USE_FIXTURES ? Promise.resolve(fixture<DecisionSummary[]>("decisions")) : request<DecisionSummary[]>("/decisions"),

  evaluate: (decisionId: string, inputs: unknown) =>
    USE_FIXTURES
      ? Promise.resolve(fixture<EvaluateResponse>(`evaluate_${shortId(decisionId)}`))
      : post<EvaluateResponse>(`/decisions/${decisionId}/evaluate`, { inputs }),

  explain: (decisionId: string, evalId: string) =>
    USE_FIXTURES
      ? slow(fixture<ExplainResponse>(`explain_${shortId(decisionId)}`, "explain_auto"))
      : post<ExplainResponse>(`/decisions/${decisionId}/explain`, { eval_id: evalId }),

  stress: (decisionId: string, evalId: string, preferredOptionId: string) =>
    USE_FIXTURES
      ? slow(fixture<StressResponse>(`stress_${shortId(decisionId)}`, "stress_auto"))
      : post<StressResponse>(`/decisions/${decisionId}/stress`, {
          eval_id: evalId,
          preferred_option_id: preferredOptionId,
        }),

  action: (decisionId: string, evalId: string, optionId: string) =>
    USE_FIXTURES
      ? slow({ ...fixture<ActionCard>(`action_${shortId(decisionId)}`, "action_auto"), option_id: optionId })
      : post<ActionCard>(`/decisions/${decisionId}/action`, { eval_id: evalId, option_id: optionId }),

  ask: (question: string, module: string | null) =>
    USE_FIXTURES
      ? slow(fixture<RagAskResponse>(/tort/i.test(question) ? "rag_ask_ok" : "rag_ask_refusal"), 700)
      : post<RagAskResponse>("/rag/ask", { question, module }),
};

// "auto_insurance" → "auto" so fixture names stay short (evaluate_auto.json etc.); other modules use
// their full id (evaluate_big_purchase.json). Explain/stress/action fall back to the auto fixtures.
function shortId(decisionId: string): string {
  return decisionId === "auto_insurance" ? "auto" : decisionId;
}
