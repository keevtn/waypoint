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

/** Multipart POST (no JSON content-type; the browser sets the boundary). */
async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api${path}`, { method: "POST", body: form });
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

// Shapes read tolerantly until the contract commit lands in types.ts; unknown fields are ignored.
export interface ImportCsvResponse {
  institution: string | null;
  transactions: number | null;
  warnings: string[];
}

export interface ProductLookupResponse {
  confidence: "high" | "low" | "none";
  name: string | null;
  price_cents: number | null;
  image_url: string | null;
  source_domain: string | null;
  note: string | null;
}

const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);
const int = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? Math.round(v) : null);

export const api = {
  health: () =>
    USE_FIXTURES
      ? Promise.resolve<HealthResponse>({ ok: true, data_mode: "local", index_chunks: 0 })
      : request<HealthResponse>("/health"),

  connect: () =>
    USE_FIXTURES ? Promise.resolve(fixture<ConnectResponse>("connect")) : post<ConnectResponse>("/bank/connect", {}),

  profile: () => (USE_FIXTURES ? Promise.resolve(fixture<Profile>("profile")) : request<Profile>("/profile")),

  /** POST /bank/import_csv (multipart: `file`, optional `balance_cents`). The file is read once, never stored. */
  importCsv: async (file: File, balanceCents: number | null): Promise<ImportCsvResponse> => {
    if (USE_FIXTURES) return { institution: "CSV import", transactions: null, warnings: [] };
    const form = new FormData();
    form.append("file", file, file.name);
    if (balanceCents !== null) form.append("balance_cents", String(balanceCents));
    const r = (await postForm<Record<string, unknown>>("/bank/import_csv", form)) ?? {};
    const warnings = Array.isArray(r.warnings) ? (r.warnings as unknown[]).map((w) => (typeof w === "string" ? w : (w as { message?: string })?.message ?? String(w))) : [];
    return { institution: str(r.institution), transactions: int(r.transactions), warnings };
  },

  /** POST /products/lookup { url }. Confidence high/low prefill the form; none leaves it alone. */
  productLookup: async (url: string): Promise<ProductLookupResponse> => {
    if (USE_FIXTURES) return { confidence: "none", name: null, price_cents: null, image_url: null, source_domain: null, note: "Lookup is unavailable in fixture mode." };
    const r = (await post<Record<string, unknown>>("/products/lookup", { url })) ?? {};
    const c = r.confidence;
    const confidence: ProductLookupResponse["confidence"] = c === "high" || c === "low" ? c : "none";
    return {
      confidence,
      name: str(r.name) ?? str(r.title),
      price_cents: int(r.price_cents) ?? int(r.amount_cents),
      image_url: str(r.image_url) ?? str(r.image),
      source_domain: str(r.source_domain) ?? str(r.domain) ?? str(r.source),
      note: str(r.note) ?? str(r.message),
    };
  },

  updateProfile: (patch: Partial<Pick<Profile, "safety_floor_cents" | "one_offs" | "recurring">>) =>
    USE_FIXTURES
      ? Promise.resolve({ ...fixture<Profile>("profile"), ...patch })
      : request<Profile>("/profile", { method: "PUT", body: JSON.stringify(patch) }),

  transactions: (limit = 50) =>
    USE_FIXTURES
      ? Promise.resolve(fixture<Transaction[]>("transactions").slice(0, limit))
      : request<Transaction[]>(`/profile/transactions?limit=${limit}`),

  baseline: (horizonMonths = 12) =>
    USE_FIXTURES
      ? Promise.resolve(fixture<ProjectionResult>("baseline"))
      : request<ProjectionResult>(`/projection/baseline?horizon_months=${horizonMonths}`),

  decisions: () =>
    USE_FIXTURES ? Promise.resolve(fixture<DecisionSummary[]>("decisions")) : request<DecisionSummary[]>("/decisions"),

  evaluate: (decisionId: string, inputs: unknown, horizonMonths = 12) =>
    USE_FIXTURES
      ? Promise.resolve(fixture<EvaluateResponse>(`evaluate_${shortId(decisionId)}`))
      : post<EvaluateResponse>(`/decisions/${decisionId}/evaluate`, { inputs, horizon_months: horizonMonths }),

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
