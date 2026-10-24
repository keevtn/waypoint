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
| C rag | c/p5-rag | P5 | — | — | — |
| E deploy | e/p9-deploy | P9 | — | — | — |

## Wave 2 — start when A-P3 and C are on main

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| A llm | a/p6-p7 | P6 | — | A-P3, C | — |
| B wire | b/p4-live | P4 live | — | A-P3 (evaluate), then A-P6/P7 | 2026-10-24 |
| D plaid | d/p8-plaid | P8 | — | A-P1 | — |

## Wave 3 — from roughly hour 14

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| I integration | i/<fix> | P10 | — | — | — |

## Contract commits

(none yet — format: `HH:MM models.py — what changed (session)`)

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
