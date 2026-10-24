# Waypoint — Handoff Spec for Claude Code

> Working name. Rename freely; nothing in the code should depend on it.
> HackPSU Fall 2026 · FNB Challenge: Trust, Decisions & Financial Confidence · 19-hour build.

---

## 0. How to use this document

You (Claude Code) are building this from an empty repo. Read sections 1–3 fully before writing any code; they contain the rules that make this project defensible to a bank's judges. Sections 4–9 are the technical contract. Section 10 is the ordered build plan with hour budgets and explicit cut lines. Section 11 is what "done" looks like.

Operating rules for this build:

- **Contract first.** The Pydantic models in §5 and the API shapes in §7 are the contract between backend and frontend. Write them in Phase 0, do not change field names after Phase 1 without updating fixtures and frontend together.
- **Fixtures before features.** Every endpoint gets a hand-written JSON fixture in `backend/fixtures/` matching its response shape before the real implementation exists, so the frontend can be built in parallel.
- **Tests on the arithmetic.** The projection engine and recurring detection get pytest tests with golden values. The LLM layer gets tests that mock the API. Nothing else needs tests under this time budget.
- **Verify external APIs against current docs**, not memory: Plaid custom-user schema, Anthropic SDK structured output, fastembed model names. Each is marked `[VERIFY]` below.
- **When behind schedule, follow the cut lines in §10.** Do not invent new scope.
- **Never let the LLM produce a number the user acts on.** See §3. This is the single most important rule in the project.
- **You are one of several parallel sessions.** Your kickoff prompt names your session, branch, and the directories you own. Stay inside them; follow the branching and CI rules in §15. `main` is always demoable.

---

## 1. What we're building and why

**One sentence:** A cash-flow-aware decision engine that takes a real financial moment (you just bought a car and need insurance; you're picking an apartment), runs the options against the user's actual bank data, has an AI try to break the plan before reality does, and ends in one concrete, sourced next action.

**The track prompt (FNB):** help people turn information → understanding → confidence → action at the moments that matter most. Suggested tools in their words: AI, personalized insights, predictive planning, automation, trusted-source validation, behavioral science.

**How we map to it:**

| Track step | Our feature |
|---|---|
| Information → understanding | Constraint engine narrows options to the ones that apply; plain-language explanation with citations |
| Understanding → confidence | Projection chart per option, flagged tight months, deductible stress test, AI stress-tester that argues *against* your pick |
| Confidence → action | Action card: exact next steps, questions to ask, deadline, reminder |
| Trust | Every number computed deterministically; every fact retrieved from a cited corpus; the model refuses off-corpus questions |

**Positioning:** a standalone, bank-agnostic app for people making their first real financial commitments (the demo persona is a college student). We do **not** brand it as a sponsor product or pitch it as a feature of their app. The sponsor alignment is implicit and lives in the design: trust-first (computed numbers, cited facts), carrier-neutral recommendations that end with "talk to a human," and a focus on the exact customer segment a bank wants to win early. If a judge asks why a bank would care, the answer is primacy: the bank that helps you decide is the bank you keep your paycheck in, and a bank already holds the transaction data this app has to fetch through Plaid. That stays in Q&A, never in the UI or the pitch.

**Decision types are "commitment purchases":** things with an upfront cost, a recurring cost, a term, and long-term value — insurance, rent/lease, loans, plans. The engine is generic over a `Commitment`; decision modules are plug-ins. We ship **auto insurance** fully and **rent** as a stretch second module to prove the pattern.

---

## 2. User flow (what the demo shows)

Single demo user, no auth.

1. **Overview** — "Connect your bank" button → Plaid sandbox → shows current balance, income cadence, detected recurring payments, average variable spend, monthly slack, and a 12-month baseline projection line.
2. **Moment** — pick a decision module (Auto insurance · Rent). Fill a short form (car value, financed?, loan payment, deductible comfort, etc.).
3. **Compare** — option cards with constraint badges (*Required by lender*, *Not allowed*, *Flagged*). Multi-line projection chart (baseline + one line per option, toggleable). Flag list under the chart. Click an option → explanation panel: why it fits/doesn't, pros, cons, each fact with a citation chip. Click a flagged month → "why this month is tight" in one paragraph. An "Ask with sources" box answers corpus questions with citations and *refuses* off-corpus ones.
4. **Stress test** — "Try to break my plan" → AI picks 3 scenarios tailored to this user, backend runs them through the projection, chart shows the impact, critique panel makes the case against the user's preferred option.
5. **Action card** — chosen option → next steps, questions to ask an agent, deadline, "talk to a human" (configurable link; an independent agent or the user's own bank, no sponsor branding), download reminder (.ics, stretch).

---

## 3. Non-negotiable design rules

1. **Numbers come from code.** Balances, projections, flags, slack, deductible math, premium estimates — all computed in `projection/` and `decisions/` from structured data. The LLM receives a compact JSON of results and may *reference* those numbers but never *generate* new ones.
2. **Numeric guardrail is enforced, not just prompted.** `llm/guardrail.py` extracts every number from LLM output and checks it against the set of numbers in the input payload (±1% tolerance, plus whitelisted small integers 0–12 for counting). Violations are stripped and logged; in dev mode they raise. Demo this in the pitch.
3. **Facts come from retrieval.** Any statement about insurance law, coverage definitions, lender requirements, or pricing must cite a chunk ID from the corpus. The explainer prompt forbids uncited factual claims. The RAG endpoint refuses when retrieval returns nothing above threshold.
4. **Carrier-agnostic and bank-agnostic.** We recommend a coverage *configuration* (limits, deductible, tort election), never a carrier. Action card says "get quotes for this config from at least 3 sources, including an independent agency." No bank or sponsor names appear anywhere in the product.
5. **No investment advice.** Scope is cash-flow commitments only. If a user asks about investing, the RAG layer refuses with "out of scope."
6. **Estimates are labeled.** Any premium or price that isn't a user-entered quote shows an "Estimate · source" badge. Unsourced values show a red "Unsourced" badge (should never happen in the demo).
7. **Single language for money:** integer cents internally, formatted at the edge. Dates are ISO strings. Plaid sign convention (positive = outflow) is normalized at ingestion to our convention: `amount_cents` positive = inflow, negative = outflow.

---

## 4. Architecture

**Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLite (via `sqlite3`, no ORM) · numpy · fastembed (ONNX embeddings, CPU) · Anthropic Python SDK · Plaid Python SDK · React 18 + TypeScript + Vite · Tailwind · Recharts.

**Deployment shape:** one process. FastAPI serves the built frontend from `frontend/dist` as static files. Deployed to Render (or Railway) as a single web service. Local dev runs two terminals (uvicorn + vite with proxy).

```
waypoint/
├── CLAUDE.md
├── SPEC.md
├── render.yaml
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI app, static mount, CORS (dev only)
│   │   ├── config.py            # env: ANTHROPIC_API_KEY, PLAID_*, DATA_MODE, DEV_MODE
│   │   ├── models.py            # ALL shared Pydantic models (§5) — the contract
│   │   ├── db.py                # sqlite helpers: items, transactions, profile cache
│   │   ├── bank/
│   │   │   ├── plaid_client.py  # sandbox connect, transactions/sync
│   │   │   ├── persona.py       # persona → Plaid custom-user JSON AND local txn list
│   │   │   └── local_loader.py  # DATA_MODE=local fallback
│   │   ├── profile/
│   │   │   ├── normalize.py     # merchant name normalization (+ optional Haiku pass)
│   │   │   └── detect.py        # recurring, income, one-offs, variable spend
│   │   ├── projection/
│   │   │   ├── engine.py        # deterministic event-walk projection
│   │   │   ├── flags.py         # derived flags
│   │   │   └── montecarlo.py    # stretch
│   │   ├── decisions/
│   │   │   ├── base.py          # DecisionModule protocol, Option, Constraint
│   │   │   ├── registry.py
│   │   │   ├── auto_insurance/
│   │   │   │   ├── module.py
│   │   │   │   ├── rules.py
│   │   │   │   ├── pricing.json # estimates with source URLs + retrieved date
│   │   │   │   └── scenarios.py # scenario menu for this module
│   │   │   └── rent/            # stretch
│   │   ├── rag/
│   │   │   ├── ingest.py        # corpus/*.md → chunks
│   │   │   ├── index.py         # fastembed + numpy; build/load index.npz
│   │   │   └── retrieve.py      # top-k, threshold, citation objects
│   │   ├── llm/
│   │   │   ├── client.py        # Anthropic wrapper, forced-JSON via tool_use
│   │   │   ├── guardrail.py     # numeric guardrail (§3.2)
│   │   │   ├── explainer.py
│   │   │   ├── stress.py
│   │   │   ├── action.py
│   │   │   └── prompts/*.txt
│   │   └── api/
│   │       ├── routes_bank.py
│   │       ├── routes_profile.py
│   │       ├── routes_decisions.py
│   │       └── routes_rag.py
│   ├── corpus/
│   │   ├── auto_insurance/*.md  # YAML frontmatter: title, url, publisher, year, tags
│   │   ├── rent/*.md
│   │   └── general/*.md
│   ├── data/persona_student.json
│   ├── fixtures/*.json          # one per endpoint response
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── api.ts               # typed fetch wrappers mirroring §7
│   │   ├── types.ts             # TS mirror of §5 (generate from models.py or hand-write)
│   │   ├── pages/Overview.tsx | Moment.tsx | Compare.tsx | StressTest.tsx | Action.tsx
│   │   ├── components/ProjectionChart.tsx | OptionCard.tsx | FlagList.tsx | CitationChip.tsx | AskWithSources.tsx | ConstraintBadge.tsx
│   │   └── state.ts             # tiny store (zustand or React context): profile, inputs, evaluate result, chosen option
│   └── vite.config.ts           # proxy /api → localhost:8000
└── scripts/
    ├── make_persona.py          # writes data/persona_student.json + plaid_custom_user.json
    └── build_index.py           # builds backend/rag/index.npz
```

---

## 5. Data model (`backend/app/models.py`)

All models Pydantic v2. Money is `int` cents. Dates are `date`. Field names are the contract; the frontend `types.ts` mirrors them exactly.

```python
Cadence = Literal["weekly", "biweekly", "semimonthly", "monthly", "once"]

class Transaction(BaseModel):
    id: str
    date: date
    amount_cents: int            # + inflow, − outflow (normalized from Plaid)
    raw_name: str
    merchant: str                # normalized
    category: str | None = None

class IncomeStream(BaseModel):
    id: str
    label: str
    amount_cents: int            # positive
    cadence: Cadence
    next_date: date
    confidence: float            # 0–1 from detector

class RecurringItem(BaseModel):
    id: str
    label: str
    amount_cents: int            # negative
    cadence: Cadence
    next_date: date
    confidence: float
    category: str | None = None

class OneOff(BaseModel):
    id: str
    label: str
    amount_cents: int            # negative (or positive for expected inflow)
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
    monthly_slack_cents: int     # computed: monthly income − recurring − variable mean

class Commitment(BaseModel):
    """A thing being decided on, as the projection engine sees it."""
    id: str
    label: str
    upfront_cents: int = 0
    recurring_cents: int = 0     # negative
    cadence: Cadence = "monthly"
    start_date: date
    term_months: int | None = None
    risk_exposure_cents: int = 0 # e.g., deductible — used by stress tests

class Constraint(BaseModel):
    id: str
    kind: Literal["required", "disallowed", "flag"]
    applies_to: list[str]        # option ids
    rule: str                    # human-readable, e.g. "Lender requires collision + comprehensive on financed vehicles"
    citation_ids: list[str]      # chunk ids from corpus

class PriceEstimate(BaseModel):
    cents: int
    kind: Literal["estimate", "user_quote"]
    source_url: str | None
    source_title: str | None
    retrieved: date | None

class Option(BaseModel):
    id: str
    label: str
    attributes: dict[str, str | int | bool]   # module-specific, e.g. tort, limits, deductible
    commitment: Commitment
    price: PriceEstimate
    status: Literal["allowed", "disallowed", "flagged"] = "allowed"
    constraint_ids: list[str] = []

class MonthPoint(BaseModel):
    month: str                   # "2026-11"
    end_balance_cents: int
    min_balance_cents: int
    min_balance_date: date
    inflow_cents: int
    outflow_cents: int

class Flag(BaseModel):
    id: str
    severity: Literal["info", "warn", "danger"]
    month: str | None
    code: Literal["below_floor", "negative", "low_slack", "deductible_unaffordable", "deductible_ok", "target_reached"]
    detail: dict                 # machine-readable: amounts, dates, contributing item ids

class ProjectionResult(BaseModel):
    option_id: str | None        # None = baseline
    series: list[MonthPoint]
    min_balance_cents: int
    min_balance_date: date
    monthly_slack_cents: int
    months_below_floor: list[str]
    months_negative: list[str]
    flags: list[Flag]
    band: dict | None = None     # stretch: {"p10": [...], "p50": [...], "p90": [...], "p_breach_floor": float}

class Citation(BaseModel):
    chunk_id: str
    title: str
    url: str
    publisher: str
    year: int | None
    excerpt: str                 # ≤ 240 chars

class Explanation(BaseModel):
    option_id: str
    verdict: str                 # one sentence, cites constraint ids in [c:...] and chunks in [s:...]
    pros: list[str]
    cons: list[str]
    tight_months: list[dict]     # {"month": "2027-01", "why": "..."} referencing item labels present in input
    citations: list[Citation]

class ScenarioTemplate(BaseModel):
    id: str                      # "income_gap" | "shock_expense" | "deductible_claim" | "rent_increase" | "hours_cut"
    label: str
    params_schema: dict          # JSON schema for params

class Scenario(BaseModel):
    template_id: str
    params: dict
    rationale: str               # LLM: why this scenario, referencing profile facts

class StressResult(BaseModel):
    scenario: Scenario
    results: dict[str, ProjectionResult]   # option_id → result (includes baseline key "baseline")

class Critique(BaseModel):
    preferred_option_id: str
    case_against: list[str]      # each bullet references a scenario id and a flag
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
```

---

## 6. Module specifications

### 6.1 Bank ingestion (`bank/`)

**Modes** (env `DATA_MODE`): `plaid` (default when keys present) or `local`.

**Plaid sandbox, no Link UI (Phase 8):**
- Use `/sandbox/public_token/create` with `institution_id="ins_109508"`, `initial_products=["transactions"]`, `options.override_username="user_custom"`, `options.override_password=<JSON string of persona custom-user config>`. This creates an Item with *our* persona's transactions through real Plaid, bypassing Link. `[VERIFY]` the custom-user config schema at https://plaid.com/docs/sandbox/user-custom/ (fields: `override_accounts[].type/subtype/starting_balance/meta/transactions[]`; transaction fields `date_transacted`, `date_posted`, `amount`, `description`, `currency`). Note Plaid's sign convention: positive amount = money leaving the account.
- Exchange public token → access token; store in sqlite `items`.
- Pull with `/transactions/sync`, looping on `has_more`. In sandbox the first sync may return nothing while the product initializes; retry up to 5× with 2s backoff. Store transactions in sqlite.
- Balance: from `/accounts/balance/get` (or the account object returned alongside sync).
- Link UI via `react-plaid-link` is a **stretch** for the recording only; the sandbox-create path is the default and demos identically ("Connect bank" → data appears in ~3s).

**Local mode:** load `data/persona_student.json` directly. Same downstream path. This is the fallback if Plaid misbehaves on stage; keep it working end to end at all times.

**Persona generator (`scripts/make_persona.py`)** writes both the local JSON and the Plaid custom-user JSON from one definition (§8). Dates are generated relative to `as_of` (today) so the history is always "last 4 months."

### 6.2 Profile detection (`profile/detect.py`)

Input: transactions (last ~120 days), current balance. Output: `Profile`.

**Merchant normalization:** uppercase, strip digits/`#`/`*`/trailing codes, collapse whitespace, take first 2–3 tokens; map a small alias table (`PAYROLL`→`Payroll`). Optional Haiku pass for leftovers (stretch; not needed for the persona).

**Recurring outflows:** group debits by normalized merchant. A group is recurring if ≥3 occurrences, amount consistency (max abs deviation ≤ max($5, 15% of median)), and interval regularity: median gap within ±3 days of 7/14/15/30. Cadence from the gap. `next_date` = last date + cadence. `confidence` = fraction of gaps within tolerance.

**Income:** same algorithm over credits with amount ≥ $100. Label from merchant.

**One-offs (detected):** debits ≥ $400 that are not recurring → surface as `source="detected"` for the user to confirm as future one-offs (UI: "Will this recur? e.g., tuition installment on Jan 15"). For the demo, the persona's known future one-offs are pre-seeded with `source="user"`.

**Variable spend:** all debits not assigned to recurring or one-offs, summed per full calendar month → mean, std. Exclude the current partial month.

**Slack:** monthly income (normalize cadence: biweekly×26/12, weekly×52/12, semimonthly×2) − monthly recurring − variable mean.

**Fallback:** if `DATA_MODE=plaid` and detection finds <2 recurring items (sandbox weirdness), merge in the persona's declared recurring items so the demo never shows an empty profile.

### 6.3 Projection engine (`projection/engine.py`)

Pure function. No I/O, no randomness in deterministic mode.

```python
def project(profile: Profile, commitments: list[Commitment], horizon_months: int = 12,
            start: date | None = None, one_off_overrides: list[OneOff] | None = None,
            income_multiplier: list[float] | None = None) -> ProjectionResult
```

Algorithm:
1. Expand every income stream, recurring item, one-off, and commitment into dated events across the horizon (respect `term_months`; commitments start at `start_date`; `upfront_cents` is a single event on `start_date`).
2. Variable spend: deterministic daily drip of `mean_monthly_cents / days_in_month`.
3. Walk day by day from `start` (default: profile.as_of): apply events for that day (outflows first, then inflows, so "paid same day as paycheck" is conservative), then the drip. Track daily balance.
4. Roll up to `MonthPoint` per calendar month: end balance, min balance within month and its date, inflow/outflow sums.
5. Derive `ProjectionResult` fields and call `flags.derive(...)`.

`income_multiplier` (per-month list) and `one_off_overrides` exist so stress scenarios can perturb inputs without special-casing the engine.

**Flags (`projection/flags.py`):**
- `below_floor` (warn) per month where `min_balance < safety_floor`; detail lists the events in the 7 days before the min that contributed (by label and amount) — this is what the "why is this month tight" explanation uses.
- `negative` (danger) per month where `min_balance < 0`.
- `low_slack` (warn) if monthly slack after the commitment < $150.
- Deductible stress (only when the commitment has `risk_exposure_cents > 0`): re-run with a one-off of `−risk_exposure_cents` on the first of month 3; emit `deductible_ok` (info) or `deductible_unaffordable` (danger, with the resulting min balance).
- `target_reached` (info): first month end balance ≥ $1,000 above the floor (a crude "emergency fund" marker). Optional.

**Monte Carlo (`montecarlo.py`, stretch):** sample monthly variable spend from `Normal(mean, std)` clipped at 0, 300 runs, return p10/p50/p90 end-balance series and `p_breach_floor`. Hook into `ProjectionResult.band`.

**Tests (`tests/test_projection.py`):** a 3-month hand-computed case (one biweekly income, one monthly rent, one one-off, zero variable) with exact expected end balances and min dates; a case where a one-off lands the day before a paycheck to check min-date logic; a deductible-stress case.

### 6.4 Decision modules (`decisions/`)

```python
class DecisionModule(Protocol):
    id: str
    title: str
    description: str
    corpus_tags: list[str]
    InputModel: type[BaseModel]
    def candidate_options(self, inputs, profile) -> list[Option]: ...
    def constraints(self, inputs, profile, options) -> list[Constraint]: ...
    def extra_commitments(self, inputs) -> list[Commitment]: ...   # e.g. the car loan, applied to every option
    def scenario_menu(self, inputs, profile) -> list[ScenarioTemplate]: ...
    def action_template(self, inputs, option) -> dict: ...          # steps/questions seeds for the LLM
```

`registry.py` maps id → instance. `GET /api/decisions` lists them.

**Evaluation pipeline (`routes_decisions.evaluate`):**
1. `options = module.candidate_options(...)`; `constraints = module.constraints(...)`; apply constraint status to options (`disallowed` wins over `flagged`).
2. `extra = module.extra_commitments(inputs)`.
3. `baseline = project(profile, extra)`; for each allowed/flagged option: `project(profile, extra + [option.commitment])`. (Disallowed options are still projected so the chart can show them greyed; UI decides.)
4. Retrieve corpus chunks for the module (query built from constraint rules + option attributes, top-8).
5. LLM explainer per option (one call for all options to save latency; see §6.6).
6. Return `EvaluateResponse` (§7).

#### Auto insurance module

**Inputs:**
```python
class AutoInsuranceInputs(BaseModel):
    state: Literal["PA"] = "PA"
    vehicle_value_cents: int
    financed: bool
    loan_payment_cents: int | None      # monthly; becomes an extra Commitment for all options
    loan_term_months: int | None
    driver_age: int
    deductible_comfort_cents: int        # max they could pay on short notice
    registration_deadline: date | None
    user_quotes: list[UserQuote] = []    # optional real quotes: {label, monthly_cents, attributes}
```

**Options (ids fixed; prices from `pricing.json`):**
- `pa_min_limited`: liability 15/30/5, $5k first-party medical, limited tort, no comp/collision.
- `std_limited_1000`: liability 50/100/25, comp+collision $1,000 deductible, limited tort.
- `std_full_500`: liability 100/300/50, comp+collision $500 deductible, full tort.
- `quote_<n>`: each user-entered quote, `price.kind="user_quote"`.

`attributes` keys: `bi_per_person`, `bi_per_accident`, `pd`, `medical`, `tort` ("full"|"limited"), `collision` (bool), `comprehensive` (bool), `deductible`. `commitment.risk_exposure_cents = deductible`.

**Constraints (`rules.py`), each with `citation_ids` pointing at corpus chunks:**
- `required` → options with comp+collision, when `financed=True`: "Lenders generally require collision and comprehensive on a financed vehicle." Marks `pa_min_limited` as `disallowed`.
- `flag` → comp+collision options, when `vehicle_value_cents < 400000`: "Collision coverage may cost more than it returns on a low-value car."
- `flag` → any option with `deductible > deductible_comfort_cents`: "Deductible exceeds what you said you could pay on short notice."
- `required` (info-level, applies to all): "Pennsylvania requires 15/30/5 liability plus $5,000 first-party medical; a lapse can suspend registration."
- `flag` → limited-tort options: "Limited tort lowers premium but waives most pain-and-suffering claims unless an exception applies." (Both tort facts must come from the PA Insurance Department chunk.)

**`pricing.json`:** monthly premium estimates per option id for a young PA driver, each with `source_url`, `source_title`, `retrieved`. Populate from public averages (Bankrate / NerdWallet / Insurance.com PA pages, or the PA Insurance Department if it publishes rate comparisons). Placeholders to replace, marked so the UI shows "Unsourced" until replaced: `pa_min_limited: 6000`, `std_limited_1000: 15000`, `std_full_500: 18500` (cents). `[VERIFY]` and record the URL + date. Young-driver surcharge is real; if the sourced averages are for all ages, note that in `source_title` ("…state average, all ages") and the UI shows it.

**Scenario menu:** `deductible_claim` (uses option's deductible; params: month 1–6), `shock_expense` (amount 200–1500, month), `income_gap` (months 1–3, start month), `hours_cut` (pct 10–50, from month), `rent_increase` (pct 3–15, from month). Templates carry min/max in `params_schema` so the LLM can't pick absurd values.

**Action template:** steps seeded with: get ≥3 quotes for the chosen configuration (limits, deductible, tort) including at least one independent agency; ask lender for written coverage requirements; confirm tort election in writing; set up autopay from checking on a date after payday; keep proof of insurance for registration. Questions seeded with: "Is the quoted premium six-month or annual?", "What's the surcharge if I drop limited tort later?", "Is there a student/good-grade discount?", "Does the policy satisfy my lender's requirements?" Deadline = `registration_deadline` or `as_of + 30 days`.

#### Rent module (stretch)

Inputs: list of 2–4 candidate units `{label, rent_cents, deposit_cents, utilities_est_cents, lease_months, start_date}`. Options = units. Constraints: `flag` when rent > 30% of monthly income; `disallowed` when rent + utilities > 45% of income; `flag` when deposit + first month > current balance − floor. No pricing source needed (user-entered). Corpus: a couple of CFPB/HUD renting guides. Scenario menu: `income_gap`, `shock_expense`, `rent_increase`. This module exists to prove the pattern; build it last.

### 6.5 RAG (`rag/`)

**Corpus format:** `backend/corpus/<module>/<slug>.md` with YAML frontmatter:
```yaml
---
title: Automobile Insurance Guide
url: https://insurance.pa.gov/Coverage/Auto/Pages/Auto-Insurance-Guide.aspx
publisher: Pennsylvania Insurance Department
year: 2025
tags: [auto_insurance, pa, tort, requirements]
---
```
Body is the page content converted to markdown by hand or via WebFetch, trimmed to the relevant sections. Keep each file under ~2,000 words.

**Ingest:** split on headings, then paragraphs, into chunks of ~350 tokens with ~60 token overlap. `chunk_id = f"{slug}#{n}"`. Store text + metadata.

**Embed:** `fastembed.TextEmbedding(model_name="BAAI/bge-small-en-v1.5")` `[VERIFY model name in current fastembed]`. Build once via `scripts/build_index.py` → `backend/rag/index.npz` (vectors) + `index_meta.json`. Load at startup; if missing, build at startup (first run ~30s incl. model download).

**Retrieve:** cosine top-k (default 6) with `min_score=0.45` `[TUNE on real queries; bge-small relevant hits typically 0.6+]`. Filter by `tags ∩ module.corpus_tags` when a module is specified. Return `Citation` objects (excerpt = first 240 chars of chunk).

**`/api/rag/ask`:** retrieve → if no chunks above threshold → `{"answer": null, "refusal": "I don't have a trusted source for that, so I won't guess.", "citations": []}`. Else → LLM answers with the rule "only use the provided chunks; cite every sentence; if the chunks don't answer it, say so." Out-of-scope guard: a tiny classifier prompt (or keyword list: invest, stock, crypto, fund) returns `refusal: "Investing is outside what this tool covers."` before retrieval.

**User documents (stretch):** `POST /api/docs/upload` accepts pasted text (PDF via `pypdf` if time), chunks into a second collection `user_docs`, and `ask` searches both. Enables "which of my three quotes meets my lender's requirement?"

**Corpus to collect (auto insurance; aim for 10–15 files total):**
- PA Insurance Department — Automobile Insurance Guide: https://insurance.pa.gov/Coverage/Auto/Pages/Auto-Insurance-Guide.aspx
- PA Insurance Department — Learn About Insurance: Auto: https://www.pa.gov/agencies/insurance/consumer-help-center/learn-about-insurance/auto-insurance
- PennDOT — insurance law FAQ / proof-of-insurance requirements (find the current page on pa.gov/penndot)
- NAIC consumer guide to auto insurance (coverage definitions)
- CFPB or state consumer-protection page on auto loans and lender insurance requirements (gap insurance, forced-placed insurance)
- One neutral explainer on deductibles and how to choose them (NAIC / Insurance Information Institute)
- General: 2–3 pages on emergency funds and the 30% rent rule (CFPB) for the rent module and the `target_reached` flag.

Do not include law-firm marketing pages even though they rank well for "full tort vs limited tort"; publisher quality is part of the trust story. Government, regulator, and non-profit sources only. No bank or sponsor content.

### 6.6 LLM layer (`llm/`)

**Client:** Anthropic Python SDK. Models: `claude-sonnet-5-5` for explainer/stress/critique/action, `claude-haiku-5-5` for merchant normalization and the out-of-scope classifier `[VERIFY current model IDs at docs.claude.com]`. Force JSON by defining a single tool whose `input_schema` is the Pydantic model's JSON schema and setting `tool_choice={"type": "tool", "name": ...}`; parse `tool_use.input` and validate with Pydantic. Retry once on validation failure with the error appended. Timeout 30s. All calls go through `client.py` so the guardrail and logging are applied uniformly.

**Guardrail (`guardrail.py`):**
```python
def allowed_numbers(payload: dict) -> set[float]   # walk the JSON, collect every int/float, plus cents→dollars conversions
def check(text: str, allowed: set[float]) -> list[str]   # returns offending number strings
```
Regex numbers (handle `$1,250`, `1250`, `12.5%`, `1.2k`). Allow small integers 0–12 and years 2026–2027. Tolerance ±1%. Applied to every string field in every LLM response. `DEV_MODE=1` → raise; else strip the sentence containing the violation and log.

**Explainer** (`explainer.py`, one call per evaluate):
- Input payload: inputs summary, each option (attributes, price with source, status, constraint ids + rules), each projection result's compact view (monthly slack, min balance + date, months below floor, flags with detail), the retrieved chunks (id, title, text).
- System prompt rules (put in `prompts/explainer.txt`): you are explaining a decision the code already evaluated; never introduce numbers not in the payload; every factual claim about insurance/law/lenders must end with `[s:<chunk_id>]`; every reference to a constraint uses `[c:<constraint_id>]`; pros/cons are about *this user's* numbers and constraints, not generic; tight-month explanations must name the contributing items from the flag detail; plain language, no hedging filler, no financial advice disclaimers (the UI has one).
- Output: `list[Explanation]`.

**Stress-tester** (`stress.py`, two calls):
1. *Select:* input = profile summary, options, scenario menu with param bounds, user's preferred option. Output = `list[Scenario]` (exactly 3), each with a rationale that references a concrete profile fact ("tuition installment in January", "biweekly income with no second stream"). Prompt: prefer scenarios that *differentiate* the options, at least one must be a `deductible_claim` when any option has a deductible.
2. Backend runs each scenario against baseline + every non-disallowed option via `project(...)` with perturbed inputs (`one_off_overrides`, `income_multiplier`).
3. *Critique:* input = stress results compact view + preferred option. Output = `Critique`. Prompt: make the strongest honest case *against* the preferred option using only the results; then the case for; then say whether the user should stay/reconsider/switch and why in one sentence. No new numbers.

**Action card** (`action.py`): input = chosen option, constraints, flags, module action template, deadline. Output = `ActionCard`. The LLM orders and phrases the template steps for this user and adds at most two user-specific steps derived from flags (e.g., "move $150 to savings before Jan 15 because that month dips to $84"). `talk_to_human_url` comes from env `TALK_TO_HUMAN_URL` (optional; `null` hides the button in the UI).

**Cost:** Sonnet calls are ~3–6k input tokens each; a full demo run is ~5 calls. Budget is not a concern; latency is. Show skeleton loaders; evaluate should return projections *first* (fast) and explanations via a second request (`/explain`) so the chart appears in <1s.

---

## 7. API contract (`/api`)

All responses JSON. Errors: `{"error": {"code": str, "message": str}}` with proper status.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/health` | — | `{"ok": true, "data_mode": "plaid"\|"local", "index_chunks": int}` |
| POST | `/bank/connect` | `{}` | `{"item_id": str, "institution": str, "transactions": int}` — creates sandbox item (or loads local), syncs, builds profile |
| GET | `/profile` | — | `Profile` |
| PUT | `/profile` | partial `Profile` (`safety_floor_cents`, `one_offs`, edited `recurring`) | `Profile` |
| GET | `/profile/transactions?limit=50` | — | `list[Transaction]` |
| GET | `/projection/baseline` | — | `ProjectionResult` (option_id null) |
| GET | `/decisions` | — | `list[{id, title, description, input_schema}]` (JSON schema for the form) |
| POST | `/decisions/{id}/evaluate` | `{"inputs": {...}}` | `EvaluateResponse` = `{"options": list[Option], "constraints": list[Constraint], "projections": {"baseline": ProjectionResult, "<option_id>": ProjectionResult}, "eval_id": str}` |
| POST | `/decisions/{id}/explain` | `{"eval_id": str}` | `{"explanations": list[Explanation]}` |
| POST | `/decisions/{id}/stress` | `{"eval_id": str, "preferred_option_id": str}` | `{"scenarios": list[StressResult], "critique": Critique}` |
| POST | `/decisions/{id}/action` | `{"eval_id": str, "option_id": str}` | `ActionCard` |
| POST | `/rag/ask` | `{"question": str, "module": str\|null}` | `{"answer": str\|null, "refusal": str\|null, "citations": list[Citation]}` |
| POST | `/docs/upload` (stretch) | `{"label": str, "text": str}` | `{"chunks": int}` |

`eval_id` keys an in-memory (or sqlite) cache of the evaluate payload so explain/stress/action don't recompute or re-send inputs. Cache TTL 1h.

**Fixtures:** `backend/fixtures/{profile,baseline,decisions,evaluate_auto,explain_auto,stress_auto,action_auto,rag_ask_ok,rag_ask_refusal}.json`. Frontend dev can set `VITE_USE_FIXTURES=1` to serve these from `api.ts` instead of fetching.

---

## 8. Seed persona (`scripts/make_persona.py` → `data/persona_student.json`)

Single source of truth for both local mode and the Plaid custom user. All dates relative to `as_of = today`.

- **Who:** college junior, State College PA, one checking account, starting balance **$1,240.00** as of today.
- **Income:** `PENN STATE PAYROLL` net **$700.00 biweekly on Fridays** (last one yesterday-ish; generator picks the most recent Friday); `ZELLE FROM MOM` **$300.00 on the 1st** monthly.
- **Recurring outflows:** `RENT – THE META` $850.00 on the 1st · `VERIZON WIRELESS` $45.00 on the 12th · `PLANET FITNESS` $24.99 on the 5th · `SPOTIFY` $5.99 on the 18th.
- **Past one-offs in history:** `CARMAX DOWN PAYMENT` −$800.00 about 7 days ago (explains the current dip and sets up the moment) · `PENN STATE BURSAR` −$1,250.00 about 70 days ago (previous tuition installment; shows the pattern).
- **Future one-offs (pre-seeded, `source="user"`):** `Tuition installment` −$1,250.00 on Jan 15 · `Textbooks` −$220.00 on Jan 20 · `PennDOT registration/title` −$180.00 in ~12 days.
- **Variable spend:** generate ~15 debits/month over 4 full months across `GIANT FOOD`, `SHEETZ`, `CHIPOTLE`, `AMAZON`, `UBER`, `TARGET`, `MCLANAHANS`, amounts $6–$60, targeting **mean ≈ $290/month, std ≈ $70**.
- **Moment inputs for the demo:** vehicle value $9,500 · financed · loan payment $212/month · 48 months · driver age 21 · deductible comfort $600 · registration deadline = as_of + 30 days.
- **Safety floor:** $200.

**Tune the persona until these demo outcomes hold** (they are acceptance criteria; adjust tuition/variable amounts, not the logic):
1. Baseline monthly slack ≈ $600; after the car loan ≈ $390.
2. `pa_min_limited` is `disallowed` (financed).
3. Both standard options show a `below_floor` flag in January driven by tuition + textbooks; `std_full_500` dips lower than `std_limited_1000` (it's ~$35/mo more).
4. Deductible stress: `std_limited_1000` → `deductible_unaffordable` (a $1,000 claim in month 3 pushes min balance under the floor or negative); `std_full_500` → `deductible_ok`. This is the tradeoff the critique should surface: cheaper monthly but worse shock resilience, and the user said $600 was their comfort.
5. No month goes negative in the baseline.

---

## 9. Frontend

Vite + React + TS + Tailwind + Recharts. Minimal state via zustand. Routes: `/` Overview · `/moment` · `/compare` · `/stress` · `/action`. A persistent top stepper shows the four steps (Understand → Compare → Stress test → Act) to echo the track's chain.

**Visual direction:** bank-trustworthy, not startup-playful. Light theme default, system dark mode supported. One accent color (deep blue), semantic colors for flags (amber warn, red danger, green ok). Numbers in tabular figures. No emoji. A small footer line: "Estimates and educational information, not financial advice. Numbers are computed from your transactions; facts are cited."

**Overview page:** Connect button (with "Demo bank · Plaid sandbox" label) → after connect: balance card, income card (cadence + next date), recurring list with confidence dots, variable spend card, slack card, baseline chart. Floor editable inline.

**Moment page:** module picker (two cards; Rent shows "coming soon" if not built) → JSON-schema-driven form (hand-build the auto insurance form; don't write a generic schema renderer under time pressure).

**Compare page:** left: option cards (label, monthly price with Estimate/Quote/Unsourced badge, key attributes, constraint badges, status styling: disallowed = greyed with reason). Right: `ProjectionChart` — Recharts `LineChart`, x = month, y = end-of-month balance; baseline dashed; one line per option; floor as a `ReferenceLine`; months below floor get a `ReferenceArea` tint for the selected option; legend toggles lines. Below: `FlagList` for the selected option, each flag clickable → side panel with the explanation's `tight_months.why`. Option card click → explanation panel (verdict, pros, cons, citation chips that open the source URL). `AskWithSources` box at the bottom; refusals render in a neutral grey box, never as an error.

**Stress page:** "Try to break my plan" button → shows the 3 scenarios as cards with rationale, chart switches to show the preferred option under each scenario (toggle), critique panel with case-against / case-for / verdict pill.

**Action page:** the `ActionCard` as a printable card; "Talk to a human" link (hidden when no URL is configured); "Add reminder" (.ics download, stretch); "Copy as text".

Loading states everywhere; the explain/stress/action calls take 5–15s and must never block the chart.

---

## 10. Build plan — 19 hours

Phases run across up to five parallel Claude Code sessions in three waves; the session map, branch names, ownership, and merge order are in §15.2. Phase 0 is a single session on `main` and must finish first. Hour estimates are per-phase effort; wall-clock with parallelism is ~11–13h, leaving buffer for integration and the demo.

| # | Phase | Effort | Deliverable / exit test |
|---|---|---|---|
| 0 | **Scaffold** | 0.75h | Repo layout from §4; `models.py` complete; `requirements.txt`, Vite app, Tailwind, proxy, `typecheck` script; `/api/health` returns; `CLAUDE.md`; all fixtures hand-written from §7 shapes (short but valid); `.github/workflows/ci.yml` + `scripts/ci.sh` (§15.5) committed and green on GitHub; `docs/STATUS.md` created; `FakeLLM` and `FakeEmbedder` stubs in place so CI never touches the network. |
| 1 | **Persona + profile** | 2h | `make_persona.py` writes both JSONs; `local_loader`; `detect.py` finds all 4 recurring items + 2 income streams on the persona with confidence > 0.8; `GET /profile` matches fixture shape. pytest for detection. |
| 2 | **Projection + flags** | 2h | `project()` with golden tests; `GET /projection/baseline`; flags incl. deductible stress; persona outcomes §8.1 and §8.5 hold. |
| 3 | **Decision framework + auto insurance** | 2h | `base.py`, registry, auto module with rules + `pricing.json` (sourced); `POST /evaluate` returns options/constraints/projections; outcomes §8.2–8.4 hold. |
| 4 | **Frontend core** (Session B, parallel from Phase 1) | 3h | Overview, Moment form, Compare with chart + option cards + flags, all working against fixtures; then swap to live API when Phase 3 lands. |
| 5 | **RAG** | 2h | Corpus collected (≥8 files), index built, `POST /rag/ask` answers with citations and refuses off-corpus + investing questions. Constraints in Phase 3 wired to real chunk ids. |
| 6 | **LLM explainer + action + guardrail** | 2h | `client.py` forced-JSON; guardrail with tests (a planted bad number is caught); `/explain` and `/action` live; explanation renders with citation chips. |
| 7 | **Stress-tester** | 1.5h | `/stress` live; critique surfaces the deductible tradeoff on the persona; Stress page wired. |
| 8 | **Plaid sandbox** | 1.5h | `/bank/connect` creates custom-user item, syncs, profile built from real Plaid data; `DATA_MODE=local` still works as fallback. |
| 9 | **Deploy** | 1h | Render single service; env vars; index built at startup or committed; smoke test the full flow on the deployed URL. |
| 10 | **Polish + demo** | 1.5h | Demo script rehearsed (§12); recording made; local fallback verified on the presenting laptop. |
| S1 | Rent module | 1h | Only if ahead at hour 14. |
| S2 | Monte Carlo band | 1h | Only if ahead. |
| S3 | Plaid Link UI for the recording | 1h | Only if ahead. |
| S4 | User quote upload (PDF) | 1h | Only if ahead. |

**Checkpoints and cut lines:**

- **Hour 6:** Phases 1–3 done and Compare page renders fixtures. If not: drop Phase 8 entirely (present in `local` mode, say "Plaid sandbox" in the UI copy anyway since the persona JSON *is* the Plaid custom-user format), and simplify Phase 7 to three fixed scenarios with no LLM selection (keep the critique call).
- **Hour 12:** Phases 5–7 done. If not: drop user-doc upload and the out-of-scope classifier (keyword list only); keep corpus RAG and the refusal.
- **Hour 16:** Deployed and smoke-tested. If not: present locally; deployment is nice-to-have for the recording, not required for judging.
- **Never cut:** the multi-line projection chart with flags, constraint badges, the explainer with citation chips, the RAG refusal, the action card, the numeric guardrail. These are the pitch.

---

## 11. Acceptance checklist

- [ ] `DATA_MODE=local` full flow works offline except for LLM calls.
- [ ] `DATA_MODE=plaid` connect → profile shows the persona's recurring items and income.
- [ ] Projection golden tests pass; §8 demo outcomes 1–5 hold.
- [ ] `pa_min_limited` disallowed with a lender-requirement constraint citing a corpus chunk.
- [ ] Explanation for `std_limited_1000` names tuition + textbooks for January and the deductible stress result, with citations.
- [ ] Guardrail test: inject "$1,337" into a mocked LLM response → stripped (prod) / raised (dev).
- [ ] `/rag/ask` "What does limited tort mean in Pennsylvania?" → cited answer from the PA Insurance Department chunk.
- [ ] `/rag/ask` "Should I put my refund in an index fund?" → investing refusal, no citations.
- [ ] `/rag/ask` "Does PA require insurance on a bicycle?" → no-source refusal.
- [ ] Stress critique mentions the deductible scenario and recommends `reconsider` or `switch` away from `std_limited_1000` given a $600 comfort level.
- [ ] Action card deadline equals the registration deadline; steps mention getting multiple quotes (including an independent agency) and lender requirements.
- [ ] No sponsor or bank name appears anywhere in the UI, copy, or corpus.
- [ ] Chart appears in <1s after evaluate; explanations stream in after.
- [ ] Deployed URL serves frontend and `/api/health`.
- [ ] Presenting laptop runs the whole thing locally with no network except the Anthropic API.

---

## 12. Demo script (3 minutes) and pitch lines

0:00 — *"Budgeting apps tell you where your money went. Comparison sites tell you what to buy. Neither connects the decision you have to make this week to the money you actually have."*
0:20 — Overview: Connect bank. "Real transactions via Plaid. Recurring payments, income cadence, and about $600 a month of slack — detected, not typed."
0:45 — Moment: "I just financed a $9,500 car. Which insurance?" Enter inputs.
1:05 — Compare: "Three configurations. The state minimum is greyed out: my lender requires collision — that's a rule in code, citing the source. The chart is a deterministic projection of my balance under each. January dips under my floor on both: tuition and textbooks, same week." Click the flag.
1:40 — Click the cheaper option. "The AI explains it, every fact cited. And here's the thing it caught: my $1,000 deductible is above the $600 I said I could cover." Ask with sources: ask about limited tort → cited. Ask about index funds → refuses. "If it doesn't have a source, it doesn't guess."
2:10 — Stress test. "Now the AI tries to break my plan. It picked a deductible claim in month three — because it read that I'm on biweekly income with one stream. Cheaper option fails. The critique argues against my pick."
2:40 — Action card. "One next step: get three quotes for *this* configuration, including an independent agency, confirm lender requirements in writing, deadline is my registration date."
2:55 — *"Every number computed. Every fact sourced. One decision at a time, with a human at the end of it."*

Judge Q&A one-liners (pocket answers; none of this goes in the pitch):
- "Why not just ask ChatGPT?" → it would invent the premium and miss January.
- "Is this meant to be a bank feature?" → it's bank-agnostic by design. A bank could adopt it and would have an advantage: the transaction data we fetch through Plaid is already theirs.
- "Why would a bank care?" → primacy. The bank that helps you decide is the bank you keep your paycheck in. (If the room is FNB staff: they became Penn State's official bank this year; that's 90,000 students making these decisions for the first time.)
- "Does it scale to other decisions?" → the module interface; show the rent stub if built.

---

## 13. Environment and run

```
# backend/.env
ANTHROPIC_API_KEY=
PLAID_CLIENT_ID=
PLAID_SECRET=
PLAID_ENV=sandbox
DATA_MODE=plaid        # or local
DEV_MODE=1             # guardrail raises; set 0 in prod
TALK_TO_HUMAN_URL=     # optional; blank hides the button. No sponsor URLs.
```

Local: `cd backend && uvicorn app.main:app --reload --port 8000` and `cd frontend && npm run dev`. Prod (Render): build `pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build && cd ../backend && python ../scripts/build_index.py`; start `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `FASTEMBED_CACHE_PATH=/opt/render/project/.cache` or similar so the model download persists in the build. If the free tier spins down, use a paid instance for demo day or present locally.

---

## 14. Things to verify against current docs before relying on them

- Plaid: `/sandbox/public_token/create` options `override_username`/`override_password`; custom-user config schema; `/transactions/sync` cursor loop; python SDK method names.
- Anthropic: current model IDs; forced tool use syntax for structured output in the python SDK.
- fastembed: model name string and default cache dir.
- Render: static file serving from FastAPI with `StaticFiles(html=True)` mounted *after* API routes.

---

## 15. Parallel sessions, branching, and CI

### 15.1 Principles

- **`main` is always demoable.** Every commit on `main` passes `scripts/ci.sh` and the smoke test. Render auto-deploys `main`, so a green merge is a deploy.
- **Sessions own directories.** A session never edits another session's directories. Shared files have a protocol (§15.3).
- **Branches live for hours, not days.** Branch from fresh `origin/main`, rebase before every push, fast-forward merge when green, delete.
- **Commit every 20–40 minutes** with a message starting with the phase tag: `p2: projection engine + flags, golden tests`.
- **CI stays under 3 minutes and needs no secrets.** Tests mock the LLM and the embedder. Nobody adds a test that needs the network.

### 15.2 Session map

**Wave 0 — one session, directly on `main`, ~45 min.** Phase 0. Exit: `./scripts/ci.sh` green with fixture-backed endpoints, GitHub Actions green, `docs/STATUS.md` exists.

**Wave 1 — start all four simultaneously once Wave 0 is pushed.**

| Session | Branch | Phases | Owns (and only these) | Needs from others |
|---|---|---|---|---|
| **A** backend-core | `a/p1-p3` | 1, 2, 3 | `backend/app/bank/persona.py`, `bank/local_loader.py`, `profile/`, `projection/`, `decisions/`, `scripts/make_persona.py`, their tests | nothing |
| **B** frontend | `b/p4-core` | 4 (against fixtures) | `frontend/**` | fixtures from Phase 0 |
| **C** rag | `c/p5-rag` | 5 + corpus collection | `backend/corpus/**`, `backend/app/rag/`, `api/routes_rag.py`, `scripts/build_index.py`, `tests/test_rag.py` | nothing |
| **E** deploy | `e/p9-deploy` | 9 (config only) | `Dockerfile`, `render.yaml`, `.dockerignore` | nothing; verifies against the fixture-backed app |

Merge order in Wave 1: **A merges twice** (after P2 and after P3) so B can go live early. **C** merges when `/rag/ask` answers with citations and refuses off-corpus. **B** merges when Overview, Moment, and Compare render on fixtures. **E** merges when the Docker image builds locally and serves `/api/health`.

**Wave 2 — start when A-P3 and C are on `main`.**

| Session | Branch | Phases | Owns | Needs |
|---|---|---|---|---|
| **A** llm | `a/p6-p7` | 6, 7 | `backend/app/llm/`, the explain/stress/action handlers in `api/routes_decisions.py` | A-P3, C merged |
| **B** wire | `b/p4-live` | 4 live + Stress + Action pages | `frontend/**` | A-P3 (evaluate); later A-P6/P7 |
| **D** plaid | `d/p8-plaid` | 8 | `backend/app/bank/plaid_client.py`, `api/routes_bank.py`, `db.py` | A-P1 merged |

**Wave 3 — from roughly hour 14.** One **integration session** on short branches `i/<fix>`; all other sessions stop or move to stretch branches (`s/rent`, `s/montecarlo`, `s/link-ui`), each merged independently and only if the §10 checkpoints allow.

**Cloud vs local:** C and E are good candidates for Claude Code cloud sessions (web-heavy, no dev server needed). A, B, and D run locally where the dev servers are. On a shared machine, each local session gets its own git worktree (`git worktree add ../waypoint-b b/p4-core`, or Claude Code's worktree isolation) so working trees never collide.

### 15.3 Shared-file protocol

Conflict hotspots: `backend/app/models.py`, `backend/fixtures/*.json`, `frontend/src/types.ts`, `backend/app/main.py`, `backend/requirements.txt`, `frontend/package.json`.

- **Contract change** (`models.py`, fixtures, `types.ts`): never inside a feature branch. Make a standalone *contract commit* straight to `main` that touches only those three places, updated together, with CI green. Note it in `docs/STATUS.md`. Every session then runs `git fetch && git rebase origin/main` before its next commit.
- **`main.py`:** one `app.include_router(...)` line per router file; each session adds only its own line.
- **`requirements.txt` / `package.json`:** one dependency per line, alphabetical, so conflicts resolve trivially.
- **`CLAUDE.md`, `SPEC.md`, `.github/`:** only the Wave 0 or integration session edits them.

### 15.4 Git workflow (every session, every time)

```
git fetch origin
git checkout -b a/p2-projection origin/main      # branch from fresh main
# ... work; commit every 20–40 min
git commit -m "p2: projection engine + flags, golden tests"
git fetch origin && git rebase origin/main        # before every push, always rebase
./scripts/ci.sh                                   # must pass
git push -u origin a/p2-projection                # Actions runs on the branch
# when Actions is green:
git checkout main && git pull --ff-only
git merge --ff-only a/p2-projection && git push   # linear history; or a PR with auto-merge
git branch -d a/p2-projection
```

Rules: rebase, never merge `main` into a branch. Fast-forward only onto `main`. Resolve conflicts on the branch and re-run `ci.sh`. If a bad commit reaches `main`, `git revert` it within minutes; don't fix forward while the deploy is broken.

### 15.5 CI

Two files, created verbatim in Phase 0 (contents provided with this spec): `.github/workflows/ci.yml` and `scripts/ci.sh`. They run the same checks; the script is the fast local pre-push, Actions is the gate for merging.

What runs:
- Backend: `pytest -q` with `DATA_MODE=local`, `LLM_FAKE=1`, dummy API keys. Unit tests for `profile/detect.py`, `projection/`, `llm/guardrail.py`, `rag/retrieve.py`, plus the smoke test.
- Frontend: `npm ci`, `npm run typecheck` (`tsc --noEmit`), `npm run build`.

**Smoke test `backend/tests/test_smoke_api.py`** is the "is `main` demoable" gate. With `TestClient`: `/health` → `/bank/connect` → `/profile` → `/projection/baseline` → `/decisions/auto_insurance/evaluate`, asserting §8 outcomes 2 and 5 (state minimum disallowed; no negative baseline months). Extend it whenever an endpoint lands (explain, stress, action with `FakeLLM`; `/rag/ask` with `FakeEmbedder`). It only grows; nobody removes an assertion to get green.

**Testability seams (build these in Phase 0):**
- `rag/index.py` takes an `Embedder` protocol. `FakeEmbedder` (hashed bag-of-words into a fixed-size vector) is used when `LLM_FAKE=1`, so CI never downloads the model.
- `llm/client.py` exposes `FakeLLM` returning canned Pydantic objects per call type, selected by `LLM_FAKE=1`. Real tests of prompts are out of scope; tests cover plumbing, schemas, and the guardrail.

**Deploy:** Render auto-deploys `main` on push. Because `main` only receives fast-forward merges of green branches, every deploy is a green build. Optional: a `deploy-smoke` job that curls `/api/health` on the deployed URL after a push to `main` (URL as a repo variable, not a secret).

### 15.6 `docs/STATUS.md`

Tiny, human-readable sync point; git log is the truth.

```
| Session | Branch        | Phase | Last merged to main | Blocked on | Updated |
|---------|---------------|-------|---------------------|------------|---------|
| A       | a/p1-p3       | P2    | P1 @ 14:10          | —          | 15:02   |
| B       | b/p4-core     | P4    | —                   | —          | 15:00   |
| C       | c/p5-rag      | P5    | —                   | —          | 14:50   |
| E       | e/p9-deploy   | P9    | —                   | —          | 14:40   |
Contract commits: 14:35 models.py — added Flag.detail.contributors (A)
```

Every session reads it at start and updates its row at every merge and whenever it is blocked. Five-line summary when a session finishes.

### 15.7 Kickoff prompt template

Paste at the start of each session, filled in:

> You are **Session A** on the Waypoint repo. Read `CLAUDE.md`, then `SPEC.md` §0–§3 and the sections for your phases, then `docs/STATUS.md`. Your branch is `a/p1-p3`, created from `origin/main`. You own only: `backend/app/bank/persona.py`, `backend/app/bank/local_loader.py`, `backend/app/profile/`, `backend/app/projection/`, `backend/app/decisions/`, `scripts/make_persona.py`, and their tests. Do not edit anything else. If you need a contract change (`models.py`, fixtures, `types.ts`), stop, make it as a standalone contract commit to `main` per §15.3, then rebase. Your phases are 1, 2, 3 with the exit tests in §10; merge to `main` after Phase 2 and again after Phase 3. Commit every 20–40 minutes, run `./scripts/ci.sh` before every push, merge fast-forward only when Actions is green, and update `docs/STATUS.md` at each merge. When done or blocked, write a 5-line summary in `STATUS.md` and stop.

Session B: branch `b/p4-core`, owns `frontend/**`, Phase 4 against fixtures with `VITE_USE_FIXTURES=1`; merge when Overview, Moment, and Compare render; then continue as `b/p4-live` once A-P3 lands.

Session C: branch `c/p5-rag`, owns corpus, `rag/`, `routes_rag.py`, `build_index.py`, `test_rag.py`; collect the §6.5 corpus first (government/regulator/non-profit only), then Phase 5; merge when `/rag/ask` cites and refuses correctly and `test_rag.py` passes with `FakeEmbedder`.

Session E: branch `e/p9-deploy`, owns `Dockerfile`, `render.yaml`, `.dockerignore`; two-stage build (node → python:3.12-slim), image serves `/api/health` and the built frontend with `DATA_MODE=local`; merge when it builds locally.

Session D (Wave 2): branch `d/p8-plaid`, owns `plaid_client.py`, `routes_bank.py`, `db.py`; Phase 8 with the §6.1 retry logic; `DATA_MODE=local` must keep working; merge when the smoke test passes in both modes (Plaid mode test skipped in CI, run manually).
