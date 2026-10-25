# STATUS

Tiny, human-readable sync point (SPEC.md §15.6). Git log is the truth. Every session reads this at start and updates its row at every merge and whenever it is blocked. Times are local (ET), 24h.

## Wave 0

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| 0 scaffold | main | P0 | P0 @ 2026-10-24 (5642438, Actions green) | — | 2026-10-24 |

## Wave 1 — start all four once Wave 0 is pushed

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| A backend-core | a/p1-p3 | done | P3 @ 2026-10-24 20:30 (P1+P2 @ 19:40) | — | 2026-10-24 20:30 |
| B frontend | b/p4-core | P4 | P4 fixtures @ 2026-10-24 (6576e06, Actions green) | — | 2026-10-24 |
| C rag | c/p5-rag | P5 done | P5 @ 2026-10-24 19:22 (contract 1d0b65c + RAG; CI green) | — | 2026-10-24 19:22 |
| E deploy | e/p9-deploy | P9 | P9 @ 2026-10-24 (Docker image + render.yaml) | — | 2026-10-24 |

## Wave 2 — start when A-P3 and C are on main

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| A llm | a/big-purchase | done | P6 + P7 @ 2026-10-24; labels fix; S1 rent module; eval cache sqlite; S2 big_purchase module + suggestions @ 2026-10-25 ~03:30 | — | 2026-10-25 |
| B wire | b/p4-live | P4 live | All pages verified on live explain/stress/action @ 2026-10-24 (528e997) | — | 2026-10-24 |
| D plaid | d/p8-plaid | P8 | — | A-P1 | — |

## Wave 3 — from roughly hour 14

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| I integration | i/<fix> | P10 | — | — | — |

## Contract commits

2026-10-25 ~02:30 contract (A): `Suggestion` model + `EvaluateResponse.suggestions: list[Suggestion] = []` in models.py; mirrored in `types.ts` (plus `Financing`/`BigPurchaseInputs` input types); `suggestions: []` added to `evaluate_auto.json`; new `evaluate_big_purchase.json` (computed from the engine on the persona: $1,800 laptop on 2026-11-01, options `cash_now` + `financed_12`, suggestions `earliest_safe_date` + `safest_financing`); `big_purchase` entry appended to `decisions.json`. **B:** `api.ts` `shortId()` maps `big_purchase` -> `big`, so fixture mode will look for `evaluate_big.json`; either special-case it or rename when you wire the module. Module itself lands on `a/big-purchase`.

19:12 fixtures — citation chunk ids remapped to the real corpus (pa-auto-insurance-guide#0 minimums, #1 tort; cfpb-auto-loan-insurance#0 lender; naic-deductibles#2 deductible); values only, no field changes; models.py/types.ts untouched (C)

## Wave 0 summary (Phase 0 done)

1. Scaffold is on `main` and GitHub Actions is green; `./scripts/ci.sh` passes locally in ~7s (12 pytest + typecheck + build).
2. `backend/app/models.py` is the complete §5 contract plus §7 request/response envelopes; `frontend/src/types.ts` mirrors it field for field.
3. Every §7 endpoint exists and returns its hand-written fixture; 11 fixtures validate against the models and encode §8 outcomes 2 and 5.
4. `FakeLLM` and `FakeEmbedder` are wired behind `get_llm()` / `get_embedder()` under `LLM_FAKE=1`; no business logic exists yet, stubs only.
5. Wave 1 (A, B, C, E) can start now from `origin/main`; `scripts/make_persona.py` and `scripts/build_index.py` are placeholders for A and C to replace.

## Session A summary (Phases 1-3 done, merged to main)

1. `/bank/connect` (local), `GET/PUT /profile`, `/profile/transactions`, `/projection/baseline`, `GET /decisions`, `POST /decisions/auto_insurance/evaluate` are real; explain/stress/action still return fixtures and accept any `eval_id` (Wave 2 reads `app/decisions/cache.py`, TTL 1h, which holds inputs, options, constraints, extra commitments, projections and the profile snapshot per `eval_id`).
2. All five SPEC §8 outcomes hold on the generated persona and are asserted in `test_smoke_api.py`, `test_projection.py`, `test_decisions.py` (34 tests, ~0.5s); persona amounts were tuned (balance $1,840, tuition $1,500, variable $260) because the spec's outflows-first rule made every option negative at the $1,240 balance.
3. Decision framework: `decisions/base.py` (Protocol + `resolve_statuses`: disallowed > flagged > allowed), `registry.py`, `evaluate.py`; auto module in `decisions/auto_insurance/` (`inputs.py`, `options.py` + sourced `pricing.json`, `rules.py`, `scenarios.py`, `action.py`). The lender rule is emitted with kind `disallowed` applying to options lacking comp+collision; `required` is informational (PA minimum, applies to all).
4. Constraint citation ids live in `decisions/citations.py` and import Session C's `app.rag.facts` constants (PA minimum `pa-auto-insurance-guide#0`, tort `#1`, lender `cfpb-auto-loan-insurance#0`, deductible `naic-deductibles#2`); `test_decisions.py` checks every constraint id is in `facts.EXPECTED_TEXT`.
5. Prices: Insurify PA state averages (all ages, retrieved 2026-10-24), $90 / $161 / $185 per month; the $185 figure is the $161 full-coverage average plus a labeled ~15% adjustment for the $500 deductible, higher limits and full tort. `source_title` says "all ages; young drivers typically pay more" so the UI can show the caveat; nothing renders "Unsourced".

## Session A summary (Phases 6-7 done, merged to main)

1. `/explain`, `/stress`, `/action` are live on the cached evaluation (`eval_id` from `/evaluate`; 404 `unknown_eval` after the 1h TTL, so the UI should re-run evaluate). `LLM_FAKE=1` still returns fixture-shaped answers through the same pipeline, so CI and the stage fallback never touch the network. Checked manually against the real key: explain ~11-19s, action ~6s, stress ~19s (two calls); all passed the guardrail in `DEV_MODE=1`.
2. `llm/client.py`: `AnthropicLLM` forces JSON with structured outputs (`output_config.format=json_schema`, closed schemas from the LLM-facing Pydantic models), validates with Pydantic and retries once with the error appended; 30s timeout, 1 SDK retry. **Forced `tool_choice` (SPEC §6.6) is a 400 on `claude-sonnet-5-5` per current docs, so structured outputs replace it.** Prompts live in `llm/prompts/{explainer,select,critique,action,rag}.txt` (C: `rag.txt` is there as requested).
3. `llm/guardrail.py`: every number in LLM output must be in the payload (numeric values, cents→dollars, numbers inside payload strings incl. chunk text and `*_display` labels; small ints 0-12 and years 2020-2030 whitelisted; ±1%). `DEV_MODE=1` → the route answers 502 `guardrail_violation` naming the numbers (pitch demo); `DEV_MODE=0` → the offending sentence is stripped and logged. **Set `DEV_MODE=0` on the presenting laptop and Render** unless you want a strict fail. LLM failures are 502 `llm_unavailable`.
4. Citations are never model-generated: the model returns `[s:chunk]` / `[c:constraint]` markers and chunk ids; code drops markers for ids it was not given and rebuilds `Citation` objects via `rag.retrieve.citation_for`. Payloads (`llm/payload.py`) carry compact views with `*_display` strings ("$1,000") so the model copies figures instead of converting cents.
5. Stress (`llm/stress.py`): the model picks 3 scenarios from the module's menu; code clamps params to the template's min/max, drops unknown templates/duplicates, forces a `deductible_claim` when any option has a deductible, and back-fills from deterministic defaults if the call fails. Scenarios run through `project()` via `one_off_overrides` (claim, shock, rent increase as monthly one-offs) and `income_multiplier` (gap, hours cut) for baseline + every non-disallowed option. On the persona the critique returns `reconsider` for `std_limited_1000` citing `naic-deductibles#2` (§11). Tests: `test_guardrail.py` (planted $1,337 caught), `test_llm.py`, `test_stress.py`; smoke extended.
6. Labels fix (a/p6-labels, per B's report of raw ids like `std_limited_1000` in prose): every payload now carries `option_labels` (id→label, incl. `baseline`), `preferred_option_label`, and a `label` on each per-option projection/result; all four prompts say labels in prose, ids only inside `[c:]`/`[s:]`. As a safety net `payload.replace_option_ids` rewrites any leaked option id in explain/action/critique/rationale prose to its label (markers untouched). Verified on the persona with the real key: critique, rationales and explanations name options by label, zero raw ids.

## Session A note: evaluation cache persisted to sqlite (merged to main)

`decisions/cache.py` now writes every evaluation through to a sqlite table (`evaluations` in `config.DB_PATH`, default `backend/waypoint.db`, already gitignored; override with `DB_PATH`) and reads it back on an in-memory miss, so a restart or redeploy between `/evaluate` and `/explain|/stress|/action` no longer yields 404 `unknown_eval`. TTL stays 1h in both layers (expired rows are evicted on every put/get). Rows are pydantic JSON dumps rehydrated through the module's `InputModel`; a row that no longer validates (contract change) or whose module is gone is treated as a miss. If the file cannot be created (read-only disk) the cache logs once and runs memory-only. Tests use a temp `DB_PATH` (`tests/conftest.py`). **Render: the disk is ephemeral per deploy, so this covers restarts within a deploy, not across deploys, unless a persistent disk is mounted and `DB_PATH` points at it.**

## Session A summary (S2 big_purchase module + suggestions, backend only, merged to main)

1. `decisions/big_purchase/` registered as `big_purchase`; `GET /api/decisions` lists it with `BigPurchaseInputs` `{name, amount_cents, date, financing: {apr_bps, term_months, down_payment_cents} | null}`. **B: build the form from that schema; no frontend was touched** (except the `types.ts` mirror in the contract commit). Options: `cash_now` (upfront = -amount on `date`, `price.kind="user_quote"`) and `financed_6/12/24` (standard amortization, down payment upfront, `recurring_cents = -payment`, `term_months`; the user's own term is added as `financed_<n>` when it is not 6/12/24). Without `financing` the plans use an assumed 24.99% APR with `price.kind="estimate"`, `source_title="Assumed APR; enter your lender's rate"`, `source_url=null` and `attributes.apr_assumed=true`; with it, `kind="user_quote"`. `attributes`: `term_months, apr_bps, down_payment_cents, monthly_payment_cents, total_cost_cents, interest_cents, date, apr_assumed`.
2. Constraints (all `citation_ids=[]`, nothing disallowed): `c_low_slack` flag when slack after the payment < $150; `c_interest_financed_<n>` flag per financed option stating interest and total cost. Scenario menu: `shock_expense`, `income_gap`, `hours_cut` (no deductible). Action template: set the date, move the cash / down payment to a separate bucket, APR + total cost in writing, prepayment penalty; `deadline` = the chosen date.
3. **Suggestions** (`EvaluateResponse.suggestions`, contract dbdc69b): computed by `big_purchase/suggest.py` only when `cash_now` has `months_below_floor` or `months_negative`. `earliest_safe_date` steps the date forward a day at a time to the horizon end (`patch={"date": iso}`); if no date works, `wait_beyond_horizon` with `projected.cash_gap_cents` = floor minus the best minimum in the horizon (`patch={}`). `safest_financing` scans term {3,6,12,24} x down {0,25,50}% and returns the cheapest total that keeps the floor with slack >= 0 (`patch={"financing": {...}}`). Guardrails in code: an actionable suggestion never projects a minimum below the floor; patches never touch `name` or raise `amount_cents`. **B: apply a suggestion by merging `patch` into the inputs and re-posting `/evaluate`**; `projected.option_id` names the option it lands on in that re-evaluation. Persona ($1,800 laptop on 2026-11-01): cash goes to -$860 in November; earliest safe cash date 2027-03-13; safest financing 12 months with $450 down ($1,989 total). $20,000 -> `wait_beyond_horizon`. Evaluate cost: ~0.7s for the $1,800 case, ~1.6s for the $20,000 scan.
4. Generic pipeline: `DecisionModule.suggestions(inputs, profile, options, projections)` is an optional hook (`base.module_suggestions`); the eval cache stores suggestions (sqlite too); `/explain` and `/action` payloads carry `suggestions` with `*_display` strings and `projected.option_label`; `explainer.txt` rule 9 asks for one sentence per suggestion using only displayed values, `action.txt` allows one pointer step. Verified on the persona with the real key in `DEV_MODE=1`: explain 24s, action 4s, stress 22s, all pass the guardrail; the explanation and action card name both suggestions with their exact figures. One fix outside the module: `llm/stress.py` now lets a select rationale quote the scenario's own *clamped* params (a "30% cut in hours" rationale was a 502 before).
5. Tests: `tests/test_big_purchase.py` (12: amortization hand-computed, options, user financing, low-slack flag, earliest safe date is the first safe day and the day before is not, wait_beyond_horizon for $20,000, safest financing never below floor and cheapest among the scan, guardrails, action deadline, API round trip incl. explain/action/stress under `LLM_FAKE=1`); smoke extended with `test_evaluate_big_purchase_suggests_alternatives`. 154 tests, CI ~30s. Fixture note: `api.ts` `shortId()` turns `big_purchase` into `big`, so fixture mode looks for `evaluate_big.json`; the committed fixture is `evaluate_big_purchase.json` as agreed, B to reconcile.

## Session A summary (S1 rent module, backend only, merged to main)

1. `decisions/rent/` registered as `rent`; `GET /api/decisions` lists it with `RentInputs` (`units`: 2-4 `{label, rent_cents, deposit_cents, utilities_est_cents, lease_months, start_date}`, optional `current_rent_cents`). **B: build the form from that schema; no frontend was touched.** Options are `unit_<n>` with the unit's label; `price.kind="user_quote"` (rent + utilities).
2. Commitments carry the *change* in housing cost: `recurring_cents = -(rent + utilities - current rent)` from `start_date` for `lease_months`, deposit as `upfront_cents`. Current rent defaults to the profile's "Rent" recurring item ($850 on the persona), so the baseline is "stay put" and each option is "move". Constraints (all cite `hud-housing-affordability#0`): `c_housing_45pct` disallowed when rent+utilities > 45% of monthly income; `c_rent_30pct` flag when rent > 30%; `c_rent_30pct_standard` info; `c_move_in_cash` flag when deposit + first month > balance - floor (also cites `cfpb-emergency-fund#1`). Monthly income uses `profile.detect.monthly_equivalent` (persona: ~$1,817 -> 30% = $545, 45% = $817).
3. Scenario menu: `income_gap` ("Paychecks stop over the summer", months 1-3 default 2), `shock_expense`, `rent_increase`. `rent_increase` on a rent option now scales the *unit's* rent from its lease start (auto module unchanged: scales the profile rent).
4. Prompts are module-agnostic now (`module` {id,title,description} is in every payload); `FakeLLM` derives number-free, payload-grounded answers for any module the auto fixtures do not fit, so `/explain`, `/stress`, `/action` work for rent under `LLM_FAKE=1` (smoke + `tests/test_rent.py`, 9 tests). Verified against the real key on the persona with three sample units: explain 15s, action 4s, stress 9s; all pass the guardrail in `DEV_MODE=1`; the critique returned `reconsider` for the flagged shared house citing the HUD chunk.
5. Known limits: only one rent corpus doc (`hud-housing-affordability.md`) + the CFPB emergency-fund page; C could add a CFPB/HUD renting or security-deposit guide under `corpus/rent/` for richer action-card citations. Sample units used in tests/manual check: Studio $750+$90 (disallowed), Shared house $550+$60 (flagged), 1BR $1,200+$100 (disallowed, negative Jan-Jul).

## Session A notes (P1+P2 merged)

- `/bank/connect` (local), `GET/PUT /profile`, `/profile/transactions`, `/projection/baseline` are real. Single-user state lives in `app/profile/store.py`; Session D plugs Plaid in by filling the same `State` (see `store.connect()`).
- Persona tuned per SPEC §8 "tune amounts, not logic" so all five outcomes hold with the spec's outflows-first rule: balance **$1,840** (was $1,240), tuition **$1,500** (was $1,250, both past and future), variable mean **$260** (was ~$290). Loan due on the 17th (first payment ~31 days after purchase), premium from as_of+10 days. Slack: baseline $630, after loan $419.
- Deductible stress: claim on the 1st of plan month 3 counting the current month as month 1 (Dec 1 from late October); unaffordable = stressed balance in that month below the safety floor. Options flag Jan (+Feb/Mar as the tuition hole recovers); nothing goes negative.
- `backend/data/persona_student.json` + `plaid_custom_user.json` are committed for reference; the loader regenerates in memory when the file's `as_of` is not today, so nothing goes stale. `python scripts/make_persona.py` refreshes them.
- Flag `detail` shapes: below_floor/negative carry `contributors[]` (`id,label,amount_cents,date,kind`, plus a `variable` drip entry); deductible flags carry `deductible_cents, claim_date, min_balance_cents, unstressed_min_balance_cents`.

## Phase 0 notes for Wave 1

- Every endpoint in SPEC.md §7 exists and returns the matching fixture from `backend/fixtures/`. Replace the stub body in your own router; keep the response model.
- `backend/app/fixtures.py` loads fixtures by name. `backend/tests/test_fixtures_valid.py` validates every fixture against §5; keep it green.
- Seams: `app.llm.client.get_llm()` returns `FakeLLM` under `LLM_FAKE=1`; `app.rag.index.get_embedder()` returns `FakeEmbedder`. `index_chunk_count()` is the `/api/health` `index_chunks` source (Session C replaces it).
- Local Python is 3.14 by default; CI is 3.12. Use `backend/.venv` (3.12): `backend/.venv/Scripts/python -m pytest -q`. `scripts/ci.sh` uses it automatically when present.
- Frontend: `npm run typecheck` and `npm run build` pass on stubs. `VITE_USE_FIXTURES=1` makes `api.ts` import `backend/fixtures/*.json` directly via Vite glob.

## Session B notes (P4 on fixtures merged)

- Overview, Moment (hand-built auto form), and Compare render end to end with `VITE_USE_FIXTURES=1`; Stress and Action are still stubs (b/p4-live).
- `api.ts` adds a ~0.9s delay to explain/stress/action/ask in fixture mode only, so loading skeletons are visible; live mode is unchanged.
- `ProjectionChart` takes `series: {id,label,result}[]`; pass `"baseline"` as the id for the dashed reference line. Fixture projections only carry 2 months; the chart unions whatever months it gets.
- Prices without `source_url`/`source_title` render a red **Unsourced** badge (SPEC §3.6). Session A: populate `PriceEstimate.source_*` from `pricing.json` so the demo never shows it.
- Explanation text renders `[s:chunk]` as citation chips and `[c:constraint]` as a "rule" tag with the constraint rule as tooltip; `tight_months.why` feeds the "why this month is tight" panel, falling back to `Flag.detail.contributors`.

## Session B notes (Stress + Action merged; live swap partial)

- All five pages render. Verified end to end in two modes: `VITE_USE_FIXTURES=1`, and live against `main` with `DATA_MODE=local LLM_FAKE=1` (connect, profile, baseline are real; evaluate/explain/stress/action still return fixtures on `main`).
- The app only restores a profile on refresh after this tab has gone through Connect (sessionStorage flag), because the local backend serves `/api/profile` before any connect and the demo must start on the Connect button.
- Overview lists one-offs dated on/after `as_of` as upcoming and summarizes earlier `detected` ones in a footnote.
- Action page: printable card, "Copy as text", "Add reminder" (.ics with a 3-day alarm, only when `deadline` is set), "Talk to a human" hidden when `talk_to_human_url` is null.
- Compare verified against real `/evaluate` with the §8 inputs: ids/statuses, constraint badges, Jan+Feb below-floor bands, "Estimate · source" badges (full source title in tooltip). Deductible flag summary reads the engine's `claim_date`/`min_balance_cents` keys as well as the fixture keys. Remaining: re-verify Stress/Action once A-P6/P7 land.

## Session C notes (P5 RAG)

**Chunk ids for constraints (Session A): import them, don't hard-code.** `from app.rag import facts`. Each id is test-checked (`tests/test_rag.py`) to exist and still hold its fact, so a corpus edit can't silently break a citation.

| Fact | Constant | Chunk id |
|---|---|---|
| PA minimum coverage (15/30/5 + $5,000 medical) | `facts.PA_MIN_COVERAGE` | `pa-auto-insurance-guide#0` (PennDOT copy: `penndot-insurance-law#0`) |
| Limited vs full tort | `facts.PA_TORT` | `pa-auto-insurance-guide#1` |
| Lender requires collision + comprehensive on a financed car | `facts.LENDER_REQUIRES_PHYSICAL_DAMAGE` | `cfpb-auto-loan-insurance#0` (NAIC "lenders may require": `naic-consumer-auto-guide#1`) |
| Deductible you can afford | `facts.DEDUCTIBLE_AFFORDABLE` | `naic-deductibles#2` (tradeoff: `#1`) |
| At least 3 quotes / independent agent | `facts.GET_THREE_QUOTES`, `facts.INDEPENDENT_AGENT` | `naic-shopping-agents#0`, `#2` |
| Lapse → 3-month registration suspension | `facts.PA_LAPSE_SUSPENSION` | `penndot-insurance-law#2` |
| Force-placed insurance | `facts.FORCE_PLACED` | `cfpb-auto-loan-insurance#2` |
| Emergency fund / rent 30% rule | `facts.EMERGENCY_FUND`, `facts.RENT_30_PERCENT` | `cfpb-emergency-fund#1`, `hud-housing-affordability#0` |

Fixtures were remapped to these ids in contract commit 1d0b65c.

**RAG API for the explainer/stress/action (A, Wave 2):** `retrieve.retrieve(query, k=6, module="auto_insurance") -> list[Hit]` (`hit.chunk.id/.text/.title`, `hit.score`); `retrieve.citation_for(chunk_id) -> Citation | None` to turn `citation_ids` into `Citation` objects. Chunk ids are `<slug>#<n>`: one `##` section = one chunk, n from 0.

**`/rag/ask` and the LLM (A, P6):** under a real client, `rag/answer.py` calls `get_llm().call("rag", {"question", "chunks": [{id, title, publisher, text}]}, RagAskResponse)`. Please add `llm/prompts/rag.txt` (I don't own `llm/`): *"Answer only from the provided chunks. End every sentence with [s:<chunk id>]. If the chunks don't answer the question, return answer=null and refusal="I don't have a trusted source for that, so I won't guess." No numbers that aren't in the chunks."* Whatever the LLM returns, `answer.py` keeps only `[s:]` markers for retrieved chunks and rebuilds `citations` itself; an uncited answer, an error, or `LLM_FAKE=1` falls back to an extractive answer (verbatim source sentences + markers). So `/rag/ask` works today with no LLM.

**Refusals:** investing (regex, before retrieval, never calls the LLM; "emergency fund" is not investing) → `Investing is outside what this tool covers.` No source → cosine threshold, then an idf-weighted check that the question's key terms appear in the top chunks (this is what refuses "insurance on a bicycle"; similarity alone doesn't).

**Index:** `python scripts/build_index.py` writes `backend/rag/index.npz` + `index_meta.json` (gitignored). The app loads it if corpus hash + embedder match, else rebuilds at startup in a background thread (`/api/health` shows `index_chunks: 0` until ready). If fastembed can't load its model (offline laptop, no cache), it logs and falls back to `FakeEmbedder`, so `/rag/ask` still works. **E:** run `build_index.py` in the image build with `FASTEMBED_CACHE_PATH` set so the model is baked in.

**Caveats (open):**
1. The corpus was written in a cloud session whose network allows only package registries: pa.gov, consumerfinance.gov, naic.org pages could not be fetched. Each file is condensed from web-search excerpts of the named official page (marked `provenance:` in the frontmatter). Someone with network should spot-check each file against its `url` before the demo; facts in `facts.py` were all confirmed by at least one official-domain excerpt.
2. `FastEmbedEmbedder.min_score = 0.45` (SPEC default) is untuned: huggingface.co was blocked, so the real model never ran here. Model name `BAAI/bge-small-en-v1.5` verified against fastembed 0.9.1's supported list. Tune with real queries; the lexical coverage check (`answer.MIN_COVERAGE = 0.6`) is embedder-independent and does the off-corpus refusals either way.

## Session E — deploy (P9 config done)

1. `Dockerfile` (node:20-slim → python:3.12-slim), `.dockerignore`, `render.yaml` are on `main`. Image builds and serves `/api/health`, the SPA, and `/api/*` with `DATA_MODE=local LLM_FAKE=1`; pytest passes inside the image.
2. Build runs `scripts/build_index.py` only when `backend/corpus/**/*.md` exists; a failing index build fails the image build (Render keeps the previous deploy). With C's corpus on `main` this step now runs on every deploy. **Unverified:** the model download (huggingface.co) is blocked in the cloud sandbox, so the strict build was only checked to fail cleanly; with `--build-arg INDEX_REQUIRED=0` the image built, indexed 46 chunks at startup, and `/rag/ask` answered with citations. **First Render deploy:** confirm the build log shows `N chunks from M files, embedder=fastembed:...`. If Hugging Face is unreachable there, set the Docker build arg `INDEX_REQUIRED=0`; the app then falls back to FakeEmbedder.
3. `FASTEMBED_CACHE_PATH=/app/.cache/fastembed` is set in the image, so the model downloads at build time and is baked in. `FastEmbedEmbedder` should honour that env var (or pass `cache_dir`).
4. Container runs as uid 10001 with `/app` writable (sqlite under `backend/`). Image is ~650 MB.
5. **Integration/B:** a refresh on a client route (`/compare`) returns 404, because `StaticFiles(html=True)` has no SPA fallback and the app uses `BrowserRouter`. Fix in `main.py` (catch-all that returns `index.html` for non-`/api` paths) or switch to `HashRouter`. Not E's files.

### Render-side settings the owner must set

- New → Blueprint → pick this repo; Render reads `render.yaml` (Docker runtime, branch `main`, health check `/api/health`).
- Env vars (prompted once on blueprint creation, all `sync: false`):
  - `DATA_MODE=local` until Phase 8 is live, then `plaid`. `LLM_FAKE=0` for the real demo (`1` = canned answers, no key needed).
  - `DEV_MODE=0` in prod (guardrail strips instead of raising; dev CORS off).
  - `ANTHROPIC_API_KEY`, `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV=sandbox`. `TALK_TO_HUMAN_URL` blank or a neutral URL (no sponsor URLs).
  - Do **not** set `PORT`; Render injects it and the image honours it.
- Plan: free tier spins down after idle (cold start ~1 min). Use a paid instance on demo day (SPEC §13).
- `[VERIFY]` blueprint keys couldn't be checked against render.com from the build sandbox. `autoDeployTrigger: commit` is the current key (it replaces the older `autoDeploy: true`). If Render rejects it, use `autoDeploy: true`. `checksPass` would wait for GitHub Actions before deploying; this is worth switching to.
- Optional: set the deployed URL as repo variable for the §15.5 `deploy-smoke` job.

## Session B summary (P4 live complete)

1. All five pages verified end to end against the live backend with the real key (`LLM_FAKE=0`): evaluate, explain, stress, action all 200; full flow ~53s in headless Chrome, no console errors. 502 `llm_unavailable` states verified by intercepting each LLM endpoint.
2. `/explain` is prefetched the moment `/evaluate` returns (store action `prefetchExplanations`, keyed by `eval_id`, ignores stale responses), so Compare shows the explanation as soon as it exists; the Compare effect only re-triggers on a direct landing or Retry.
3. Every LLM-backed panel has a skeleton and a plain-language error with Retry (`friendlyError` maps 502/504/`llm_unavailable` and expired `eval_id`). Action requests are deduped per (eval, option) so StrictMode remounts don't double-call.
4. Stress flag lists dedupe below_floor/negative pairs and collapse past 6 rows ("Show N more").
5. For A, cosmetic only: LLM prose on Stress/Compare sometimes uses raw ids (`std_limited_1000`, `deductible_unaffordable`); the explainer/critique prompts could ask for option labels instead.

## Session B — S1 rent UI merged (2026-10-25)

1. Moment: the Rent card is live (no more "Coming soon"). Hand-built form for 2–4 units (name, rent, deposit, utilities estimate, lease months, start date) plus optional "what you pay now"; blank uses the rent detected in the profile. Defaults: three State College units ($520 room / $725 shared 2BR / $1,050 studio) so the demo shows Fits / Flagged (over 30%) / Not allowed (over 45%) at once.
2. Compare, Stress, Action work unchanged for rent against the live backend (`LLM_FAKE=1`, headless Chrome, no console errors, no 4xx/5xx). Option cards render rent attributes (rent, utilities, move-in, lease, "vs. today"); constraint badges map `c_housing_45pct` / `c_rent_30pct` / `c_rent_30pct_standard` / `c_move_in_cash`; baseline is labelled "stay put"; Ask-with-sources has a rent placeholder and a HUD 30% suggestion.
3. `RentInputs` lives in `frontend/src/lib/decisionInputs.ts` (frontend-only, mirrors `rent/inputs.py`) rather than `types.ts`, to avoid a contract commit. The store's `inputs` is now tagged `{ decisionId, inputs }`; `withFreshEval` re-evaluates with the right module. There is no `evaluate_rent.json` fixture, so `VITE_USE_FIXTURES=1` only covers the auto module.
4. Next (B): big-purchase UI once A's contract commit + `fixtures/evaluate_big_purchase.json` land.
