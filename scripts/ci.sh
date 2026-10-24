#!/usr/bin/env bash
# Place at scripts/ci.sh and `chmod +x` it.
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

echo "== backend: pytest"
( cd backend && python -m pytest -q )

echo "== frontend: typecheck + build"
( cd frontend && npm run typecheck --silent && npm run build --silent )

echo "== CI OK ($(( $(date +%s) - start ))s)"
