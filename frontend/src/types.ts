// TS mirror of backend/app/models.py (SPEC.md §5). Field names are the contract.
// Changing a name here requires changing models.py and backend/fixtures/ in the same commit.
// Money is integer cents (positive = inflow). Dates are ISO "YYYY-MM-DD" strings.

export type Cadence = "weekly" | "biweekly" | "semimonthly" | "monthly" | "once";

export interface Transaction {
  id: string;
  date: string;
  amount_cents: number;
  raw_name: string;
  merchant: string;
  category: string | null;
}

export interface IncomeStream {
  id: string;
  label: string;
  amount_cents: number;
  cadence: Cadence;
  next_date: string;
  confidence: number;
}

export interface RecurringItem {
  id: string;
  label: string;
  amount_cents: number;
  cadence: Cadence;
  next_date: string;
  confidence: number;
  category: string | null;
}

export interface OneOff {
  id: string;
  label: string;
  amount_cents: number;
  date: string;
  source: "detected" | "user" | "module";
}

export interface VariableSpend {
  mean_monthly_cents: number;
  std_monthly_cents: number;
  months_observed: number;
}

export interface Profile {
  as_of: string;
  balance_cents: number;
  income: IncomeStream[];
  recurring: RecurringItem[];
  one_offs: OneOff[];
  variable: VariableSpend;
  safety_floor_cents: number;
  monthly_slack_cents: number;
}

export interface Commitment {
  id: string;
  label: string;
  upfront_cents: number;
  recurring_cents: number;
  cadence: Cadence;
  start_date: string;
  term_months: number | null;
  risk_exposure_cents: number;
}

export type ConstraintKind = "required" | "disallowed" | "flag";

export interface Constraint {
  id: string;
  kind: ConstraintKind;
  applies_to: string[];
  rule: string;
  citation_ids: string[];
}

export interface PriceEstimate {
  cents: number;
  kind: "estimate" | "user_quote";
  source_url: string | null;
  source_title: string | null;
  retrieved: string | null;
}

export type OptionStatus = "allowed" | "disallowed" | "flagged";

export interface Option {
  id: string;
  label: string;
  attributes: Record<string, string | number | boolean>;
  commitment: Commitment;
  price: PriceEstimate;
  status: OptionStatus;
  constraint_ids: string[];
}

export interface MonthPoint {
  month: string;
  end_balance_cents: number;
  min_balance_cents: number;
  min_balance_date: string;
  inflow_cents: number;
  outflow_cents: number;
}

export type FlagSeverity = "info" | "warn" | "danger";
export type FlagCode =
  | "below_floor"
  | "negative"
  | "low_slack"
  | "deductible_unaffordable"
  | "deductible_ok"
  | "target_reached";

export interface Flag {
  id: string;
  severity: FlagSeverity;
  month: string | null;
  code: FlagCode;
  detail: Record<string, unknown>;
}

export interface ProjectionBand {
  p10: number[];
  p50: number[];
  p90: number[];
  p_breach_floor: number;
}

export interface ProjectionResult {
  option_id: string | null;
  series: MonthPoint[];
  min_balance_cents: number;
  min_balance_date: string;
  monthly_slack_cents: number;
  months_below_floor: string[];
  months_negative: string[];
  flags: Flag[];
  band: ProjectionBand | null;
}

export interface Citation {
  chunk_id: string;
  title: string;
  url: string;
  publisher: string;
  year: number | null;
  excerpt: string;
}

export interface TightMonth {
  month: string;
  why: string;
}

export interface Explanation {
  option_id: string;
  verdict: string;
  pros: string[];
  cons: string[];
  tight_months: TightMonth[];
  citations: Citation[];
}

export interface ScenarioTemplate {
  id: string;
  label: string;
  params_schema: Record<string, unknown>;
}

export interface Scenario {
  template_id: string;
  params: Record<string, unknown>;
  rationale: string;
}

export interface StressResult {
  scenario: Scenario;
  results: Record<string, ProjectionResult>;
}

export type RecommendationShift = "stay" | "reconsider" | "switch";

export interface Critique {
  preferred_option_id: string;
  case_against: string[];
  case_for: string[];
  recommendation_shift: RecommendationShift;
  citations: Citation[];
}

export interface ActionCard {
  option_id: string;
  headline: string;
  steps: string[];
  questions_to_ask: string[];
  deadline: string | null;
  deadline_reason: string | null;
  talk_to_human_url: string | null;
  citations: Citation[];
}

// ---- API envelopes (SPEC.md §7) ----

export interface HealthResponse {
  ok: boolean;
  data_mode: "plaid" | "local";
  index_chunks: number;
}

export interface ConnectResponse {
  item_id: string;
  institution: string;
  transactions: number;
}

export interface DecisionSummary {
  id: string;
  title: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export type SuggestionType = "earliest_safe_date" | "safest_financing" | "wait_beyond_horizon";

// A code-generated alternative: merge `patch` into the module inputs and re-submit /evaluate.
export interface Suggestion {
  id: string;
  type: SuggestionType;
  label: string;
  rationale: string; // templated by code, not the LLM
  patch: Record<string, unknown>; // partial inputs; never changes `name` or raises `amount_cents`
  projected: {
    option_id: string;
    min_balance_cents: number;
    min_balance_date: string;
    months_below_floor: string[];
    monthly_slack_cents: number;
    total_cost_cents: number;
    cash_gap_cents?: number; // wait_beyond_horizon only
    [key: string]: unknown;
  };
}

export interface EvaluateResponse {
  options: Option[];
  constraints: Constraint[];
  projections: Record<string, ProjectionResult>; // "baseline" + one per option id
  eval_id: string;
  suggestions: Suggestion[];
}

export interface ExplainResponse {
  explanations: Explanation[];
}

export interface StressResponse {
  scenarios: StressResult[];
  critique: Critique;
}

export interface RagAskResponse {
  answer: string | null;
  refusal: string | null;
  citations: Citation[];
}

export interface ErrorResponse {
  error: { code: string; message: string };
}

// Auto insurance module inputs (SPEC.md §6.4).
export interface UserQuote {
  label: string;
  monthly_cents: number;
  attributes: Record<string, string | number | boolean>;
}

export interface AutoInsuranceInputs {
  state: "PA";
  vehicle_value_cents: number;
  financed: boolean;
  loan_payment_cents: number | null;
  loan_term_months: number | null;
  driver_age: number;
  deductible_comfort_cents: number;
  registration_deadline: string | null;
  user_quotes: UserQuote[];
}

// Big purchase module inputs (SPEC.md §6.4 pattern; module `big_purchase`).
export interface Financing {
  apr_bps: number; // 2499 = 24.99% APR; 0 allowed
  term_months: number;
  down_payment_cents: number;
}

export interface BigPurchaseInputs {
  name: string;
  amount_cents: number;
  date: string; // ISO; the purchase or financing start date
  financing: Financing | null;
}
