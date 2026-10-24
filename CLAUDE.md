# Waypoint — project instructions for Claude Code

Read `SPEC.md` before doing anything. It is the full handoff: problem framing, data model (contract), API, module specs, 19-hour build plan with cut lines, and acceptance checklist. This file is the short version you keep in mind while working.

## What this is
HackPSU Fall 2026, FNB Challenge track. A cash-flow-aware decision engine: Plaid sandbox → profile (recurring, income, variable spend) → deterministic 12-month projection → decision module (auto insurance; rent as stretch) → RAG-cited explanations → AI stress-tester that argues against the user's pick → action card. Single demo user, no auth.
Standalone and bank-agnostic. No sponsor branding, names, or URLs anywhere in the product or corpus; the sponsor alignment is implicit (trust design, carrier neutrality, student persona).

## Stack
Python 3.12 · FastAPI · Pydantic v2 · sqlite3 · numpy · fastembed · anthropic SDK · plaid SDK · React 18 + TS + Vite · Tailwind · Recharts · zustand.
One deployable process: FastAPI serves `frontend/dist`. Dev: uvicorn on :8000 + vite on :5173 with `/api` proxy.

## Hard rules (do not relax these)
1. The LLM never generates a number the user acts on. All money math lives in `backend/app/projection/` and `backend/app/decisions/`. `llm/guardrail.py` strips/raises on any number in LLM output not present in the input payload.
2. Every factual claim about insurance, law, lenders, or prices carries a citation to a corpus chunk id. No chunk → the model refuses rather than guesses.
3. Carrier-agnostic and bank-agnostic. Recommend coverage configurations, never a carrier; no bank or sponsor names in the product.
4. No investment advice. `/api/rag/ask` refuses investing questions.
5. Money is integer cents internally; dates are ISO strings; `amount_cents` positive = inflow (Plaid's sign is flipped at ingestion).
6. `backend/app/models.py` is the contract. Changing a field name means updating `backend/fixtures/*.json` and `frontend/src/types.ts` in the same commit.
7. `DATA_MODE=local` must work end to end at all times; it is the stage fallback.

## Working conventions
- Write the fixture for an endpoint before implementing it; frontend builds against fixtures (`VITE_USE_FIXTURES=1`).
- pytest covers `profile/detect.py`, `projection/engine.py`, `projection/flags.py`, `llm/guardrail.py`. Mock the Anthropic client in tests.
- Verify external API details against current docs (Plaid custom user, Anthropic structured output, fastembed model name) — items marked `[VERIFY]` in SPEC.md. Do not rely on memory.
- Keep LLM prompts in `backend/app/llm/prompts/*.txt`, not inline strings.
- Loading states on anything that calls the LLM; the projection chart must render before explanations arrive.
- Government/regulator/non-profit sources only in `backend/corpus/`. No law-firm pages, no bank or sponsor content.
- When behind schedule, apply the cut lines in SPEC.md §10. Do not add scope.

## Parallel sessions, branching, CI (full detail: SPEC.md §15)
- You are one of several Claude Code sessions working at the same time. Your kickoff prompt names your session letter, your branch, and the directories you own. Edit nothing outside them. Session map and merge order: SPEC.md §15.2.
- `main` is always demoable and auto-deploys. Only fast-forward merges of branches that pass `./scripts/ci.sh` locally and GitHub Actions reach `main`.
- Branch from fresh `origin/main` (`<session>/<phase-slug>`), commit every 20–40 minutes (`pN: what changed`), `git rebase origin/main` before every push, never merge `main` into a branch, delete the branch after merging.
- Contract files (`backend/app/models.py`, `backend/fixtures/`, `frontend/src/types.ts`) change only via a standalone contract commit straight to `main` that updates all three together. Never inside a feature branch. Note it in `docs/STATUS.md`; everyone rebases.
- `main.py` router lines, `requirements.txt`, `package.json`: add only your own line, alphabetical.
- Run `./scripts/ci.sh` before every push. CI must stay under 3 minutes and needs no secrets: tests use `LLM_FAKE=1` (`FakeLLM`, `FakeEmbedder`) and `DATA_MODE=local`. Never add a test that needs the network or the embedding model.
- `backend/tests/test_smoke_api.py` is the "is main demoable" gate. Extend it when you add an endpoint; never remove an assertion to get green.
- If a bad commit reaches `main`, `git revert` it immediately; don't fix forward while the deploy is broken.
- Update `docs/STATUS.md` at every merge and whenever you're blocked. Read it when you start.
- On a shared machine, one git worktree per session.
- Don't edit `CLAUDE.md`, `SPEC.md`, or `.github/` unless you are the Wave 0 or integration session.

## Commands
```
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
./scripts/ci.sh                       # same checks as GitHub Actions; run before every push
cd backend && pytest -q
python scripts/make_persona.py        # regenerates data/persona_student.json + plaid custom-user json
python scripts/build_index.py         # rebuilds backend/rag/index.npz from corpus/
git worktree add ../waypoint-<x> <branch>   # one worktree per parallel session
```

## Demo persona (see SPEC.md §8 for the full definition and the acceptance outcomes)
Student in State College, PA. $1,240 balance. $700 biweekly payroll + $300/mo on the 1st. Rent $850, phone $45, gym $24.99, Spotify $5.99. Tuition $1,250 on Jan 15, textbooks $220 on Jan 20, registration $180 in ~12 days. Variable spend ~$290/mo ± $70. Moment: financed $9,500 car, $212/mo loan, age 21, deductible comfort $600. Floor $200.
Required outcomes: state minimum disallowed (lender); both standard options flag January; the $1,000-deductible option fails the deductible stress test, the $500 one passes.
