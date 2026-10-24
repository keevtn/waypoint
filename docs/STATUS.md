# STATUS

Tiny, human-readable sync point (SPEC.md §15.6). Git log is the truth. Every session reads this at start and updates its row at every merge and whenever it is blocked. Times are local (ET), 24h.

## Wave 0

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| 0 scaffold | main | P0 | P0 (in progress) | — | 2026-10-24 |

## Wave 1 — start all four once Wave 0 is pushed

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| A backend-core | a/p1-p3 | P1 | — | — | — |
| B frontend | b/p4-core | P4 | — | — | — |
| C rag | c/p5-rag | P5 | — | — | — |
| E deploy | e/p9-deploy | P9 | — | — | — |

## Wave 2 — start when A-P3 and C are on main

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| A llm | a/p6-p7 | P6 | — | A-P3, C | — |
| B wire | b/p4-live | P4 live | — | A-P3 | — |
| D plaid | d/p8-plaid | P8 | — | A-P1 | — |

## Wave 3 — from roughly hour 14

| Session | Branch | Phase | Last merged to main | Blocked on | Updated |
|---------|--------|-------|---------------------|------------|---------|
| I integration | i/<fix> | P10 | — | — | — |

## Contract commits

(none yet — format: `HH:MM models.py — what changed (session)`)

## Phase 0 notes for Wave 1

- Every endpoint in SPEC.md §7 exists and returns the matching fixture from `backend/fixtures/`. Replace the stub body in your own router; keep the response model.
- `backend/app/fixtures.py` loads fixtures by name. `backend/tests/test_fixtures_valid.py` validates every fixture against §5; keep it green.
- Seams: `app.llm.client.get_llm()` returns `FakeLLM` under `LLM_FAKE=1`; `app.rag.index.get_embedder()` returns `FakeEmbedder`. `index_chunk_count()` is the `/api/health` `index_chunks` source (Session C replaces it).
- Local Python is 3.14 by default; CI is 3.12. Use `backend/.venv` (3.12): `backend/.venv/Scripts/python -m pytest -q`. `scripts/ci.sh` uses it automatically when present.
- Frontend: `npm run typecheck` and `npm run build` pass on stubs. `VITE_USE_FIXTURES=1` makes `api.ts` import `backend/fixtures/*.json` directly via Vite glob.
