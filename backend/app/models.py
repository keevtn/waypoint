"""ALL shared Pydantic models. This file is the contract (SPEC.md §5).

Changing a field name here requires updating backend/fixtures/*.json and
frontend/src/types.ts in the same standalone contract commit to main.

Money is integer cents (positive = inflow, negative = outflow). Dates are ISO.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

Cadence = Literal["weekly", "biweekly", "semimonthly", "monthly", "once"]


class Transaction(BaseModel):
    id: str
    date: date
    amount_cents: int  # + inflow, − outflow (normalized from Plaid)
    raw_name: str
    merchant: str  # normalized
    category: str | None = None


class IncomeStream(BaseModel):
    id: str
    label: str
    amount_cents: int  # positive
    cadence: Cadence
    next_date: date
    confidence: float  # 0–1 from detector


class RecurringItem(BaseModel):
    id: str
    label: str
    amount_cents: int  # negative
    cadence: Cadence
    next_date: date
    confidence: float
    category: str | None = None


class OneOff(BaseModel):
    id: str
    label: str
    amount_cents: int  # negative (or positive for expected inflow)
    date: date
    source: Literal["detected", "user", "module"]


class VariableSpend(BaseModel):
    mean_monthly_cents: int
    std_monthly_cents: int
    months_observed: int


class Profile(BaseModel):
    as_of: date
    balance_cents: int
    income: list[IncomeStream]
    recurring: list[RecurringItem]
    one_offs: list[OneOff]
    variable: VariableSpend
    safety_floor_cents: int = 20000
    monthly_slack_cents: int  # computed: monthly income − recurring − variable mean


class Commitment(BaseModel):
    """A thing being decided on, as the projection engine sees it."""

    id: str
    label: str
    upfront_cents: int = 0
    recurring_cents: int = 0  # negative
    cadence: Cadence = "monthly"
    start_date: date
    term_months: int | None = None
    risk_exposure_cents: int = 0  # e.g., deductible — used by stress tests


class Constraint(BaseModel):
    id: str
    kind: Literal["required", "disallowed", "flag"]
    applies_to: list[str]  # option ids
    rule: str  # human-readable
    citation_ids: list[str]  # chunk ids from corpus


class PriceEstimate(BaseModel):
    cents: int
    kind: Literal["estimate", "user_quote"]
    source_url: str | None
    source_title: str | None
    retrieved: date | None


class Option(BaseModel):
    id: str
    label: str
    attributes: dict[str, str | int | bool]  # module-specific
    commitment: Commitment
    price: PriceEstimate
    status: Literal["allowed", "disallowed", "flagged"] = "allowed"
    constraint_ids: list[str] = []


class MonthPoint(BaseModel):
    month: str  # "2026-11"
    end_balance_cents: int
    min_balance_cents: int
    min_balance_date: date
    inflow_cents: int
    outflow_cents: int


class Flag(BaseModel):
    id: str
    severity: Literal["info", "warn", "danger"]
    month: str | None
    code: Literal[
        "below_floor",
        "negative",
        "low_slack",
        "deductible_unaffordable",
        "deductible_ok",
        "target_reached",
    ]
    detail: dict  # machine-readable: amounts, dates, contributing item ids


class ProjectionResult(BaseModel):
    option_id: str | None  # None = baseline
    series: list[MonthPoint]
    min_balance_cents: int
    min_balance_date: date
    monthly_slack_cents: int
    months_below_floor: list[str]
    months_negative: list[str]
    flags: list[Flag]
    band: dict | None = None  # stretch: {"p10": [...], "p50": [...], "p90": [...], "p_breach_floor": float}


class Citation(BaseModel):
    chunk_id: str
    title: str
    url: str
    publisher: str
    year: int | None
    excerpt: str  # ≤ 240 chars


class Explanation(BaseModel):
    option_id: str
    verdict: str  # one sentence, cites constraints as [c:...] and chunks as [s:...]
    pros: list[str]
    cons: list[str]
    tight_months: list[dict]  # {"month": "2027-01", "why": "..."}
    citations: list[Citation]


class ScenarioTemplate(BaseModel):
    id: str  # "income_gap" | "shock_expense" | "deductible_claim" | "rent_increase" | "hours_cut"
    label: str
    params_schema: dict  # JSON schema for params


class Scenario(BaseModel):
    template_id: str
    params: dict
    rationale: str  # LLM: why this scenario, referencing profile facts


class StressResult(BaseModel):
    scenario: Scenario
    results: dict[str, ProjectionResult]  # option_id → result (includes "baseline")


class Critique(BaseModel):
    preferred_option_id: str
    case_against: list[str]
    case_for: list[str]
    recommendation_shift: Literal["stay", "reconsider", "switch"]
    citations: list[Citation]


class ActionCard(BaseModel):
    option_id: str
    headline: str
    steps: list[str]
    questions_to_ask: list[str]
    deadline: date | None
    deadline_reason: str | None
    talk_to_human_url: str | None
    citations: list[Citation]


# ---------------------------------------------------------------------------
# API request / response envelopes (SPEC.md §7)
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    ok: bool
    data_mode: Literal["plaid", "local"]
    index_chunks: int


class ConnectResponse(BaseModel):
    item_id: str
    institution: str
    transactions: int


class CsvImportResponse(BaseModel):
    """POST /bank/import_csv: the store's transactions replaced by the upload, profile rebuilt."""

    imported: int
    skipped: int
    profile: Profile
    warnings: list[str]


class ProductLookupRequest(BaseModel):
    url: str


class ProductLookupResponse(BaseModel):
    """POST /products/lookup: server-side read of a product page. `price_cents` is null when no
    price was parsed or the currency is not USD; `confidence` says how it was found."""

    name: str | None
    price_cents: int | None
    currency: str | None
    source_url: str
    image_url: str | None
    confidence: Literal["high", "low", "none"]
    note: str | None


class DecisionSummary(BaseModel):
    id: str
    title: str
    description: str
    input_schema: dict


HORIZON_CHOICES: tuple[int, ...] = (12, 60, 120)


class EvaluateRequest(BaseModel):
    inputs: dict
    horizon_months: int = 12  # 12, 60 or 120; routes reject anything else with 422 invalid_horizon


class Suggestion(BaseModel):
    """A code-generated alternative the client can apply by merging `patch` into its inputs
    and re-submitting /evaluate. `rationale` is templated by code, never by the LLM."""

    id: str
    type: Literal["earliest_safe_date", "safest_financing", "wait_beyond_horizon"]
    label: str
    rationale: str
    patch: dict  # partial inputs; never changes `name` or raises `amount_cents`
    projected: dict  # option_id, min_balance_cents, min_balance_date, months_below_floor, monthly_slack_cents, total_cost_cents (+ cash_gap_cents for wait_beyond_horizon)


class EvaluateResponse(BaseModel):
    options: list[Option]
    constraints: list[Constraint]
    projections: dict[str, ProjectionResult]  # "baseline" + one per option id
    eval_id: str
    suggestions: list[Suggestion] = []


class ExplainRequest(BaseModel):
    eval_id: str


class ExplainResponse(BaseModel):
    explanations: list[Explanation]


class StressRequest(BaseModel):
    eval_id: str
    preferred_option_id: str


class StressResponse(BaseModel):
    scenarios: list[StressResult]
    critique: Critique


class ActionRequest(BaseModel):
    eval_id: str
    option_id: str


class RagAskRequest(BaseModel):
    question: str
    module: str | None = None


class RagAskResponse(BaseModel):
    answer: str | None
    refusal: str | None
    citations: list[Citation]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
