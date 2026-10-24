# STATUS

Tiny, human-readable sync point (SPEC.md §15.6). Git log is the truth. Every session reads this at start and updates its row at every merge and whenever it is blocked. Times are local (ET), 24h.

## Wave 0

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| 0 scaffold | main | P0 | P0 @ 2026-10-24 (5642438, Actions green) | — | 2026-10-24 |

## Wave 1 — start all four once Wave 0 is pushed

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| A backend-core | a/p1-p3 | P3 | P1+P2 @ 2026-10-24 19:40 | — | 2026-10-24 19:40 |
| B frontend | b/p4-core | P4 | P4 fixtures @ 2026-10-24 (6576e06, Actions green) | — | 2026-10-24 |
| C rag | c/p5-rag | P5 done | — (ready: CI green locally, rebased on 1d0b65c) | GitHub push access (403) | 2026-10-24 19:30 |
| E deploy | e/p9-deploy | P9 | — | — | — |

## Wave 2 — start when A-P3 and C are on main

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| A llm | a/p6-p7 | P6 | — | A-P3, C | — |
| B wire | b/p4-live | P4 live | Stress + Action pages, live connect/profile/baseline verified @ 2026-10-24 | A-P3 (evaluate), then A-P6/P7 for real explain/stress/action | 2026-10-24 |
| D plaid | d/p8-plaid | P8 | — | A-P1 | — |

## Wave 3 — from roughly hour 14

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| I integration | i/<fix> | P10 | — | — | — |

## Contract commits

19:12 fixtures — citation chunk ids remapped to the real corpus (pa-auto-insurance-guide#0 minimums, #1 tort; cfpb-auto-loan-insurance#0 lender; naic-deductibles#2 deductible); values only, no field changes; models.py/types.ts untouched (C)

## Wave 0 summary (Phase 0 done)

1. Scaffold is on `main` and GitHub Actions is green; `./scripts/ci.sh` passes locally in ~7s (12 pytest + typecheck + build).
2. `backend/app/models.py` is the complete §5 contract plus §7 request/response envelopes; `frontend/src/types.ts` mirrors it field for field.
3. Every §7 endpoint exists and returns its hand-written fixture; 11 fixtures validate against the models and encode §8 outcomes 2 and 5.
4. `FakeLLM` and `FakeEmbedder` are wired behind `get_llm()` / `get_embedder()` under `LLM_FAKE=1`; no business logic exists yet, stubs only.
5. Wave 1 (A, B, C, E) can start now from `origin/main`; `scripts/make_persona.py` and `scripts/build_index.py` are placeholders for A and C to replace.

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
- Remaining for B: re-verify Compare once A-P3's real `/evaluate` lands (option ids and `PriceEstimate.source_*` drive badges), then Stress/Action once A-P6/P7 land. No frontend code change is expected for the swap.

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
