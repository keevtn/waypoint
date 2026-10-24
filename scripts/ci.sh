#!/usr/bin/env bash
# Same checks as .github/workflows/ci.yml. Run before every push.
set -euo pipefail
cd "$(dirname "$0")/.."

export DATA_MODE=local
export LLM_FAKE=1
export DEV_MODE=1
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-test}"
export PLAID_CLIENT_ID="${PLAID_CLIENT_ID:-test}"
export PLAID_SECRET="${PLAID_SECRET:-test}"
export PLAID_ENV="${PLAID_ENV:-sandbox}"

start=$(date +%s)

# Prefer the project venv (Python 3.12, matches CI) when it exists.
PY=python
[ -x backend/.venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
[ -x backend/.venv/bin/python ] && PY=.venv/bin/python

echo "== backend: pytest ($PY)"
( cd backend && "$PY" -m pytest -q )

echo "== frontend: typecheck + build"
( cd frontend && npm run typecheck --silent && npm run build --silent )

echo "== CI OK ($(( $(date +%s) - start ))s)"
