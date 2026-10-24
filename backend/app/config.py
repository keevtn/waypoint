"""Environment configuration. Read once at import; nothing else reads os.environ."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
PLAID_CLIENT_ID: str = os.getenv("PLAID_CLIENT_ID", "")
PLAID_SECRET: str = os.getenv("PLAID_SECRET", "")
PLAID_ENV: str = os.getenv("PLAID_ENV", "sandbox")

# "plaid" when keys are present, else "local". Explicit DATA_MODE wins.
_default_mode = "plaid" if (PLAID_CLIENT_ID and PLAID_SECRET) else "local"
DATA_MODE: str = os.getenv("DATA_MODE", _default_mode)

DEV_MODE: bool = os.getenv("DEV_MODE", "1") == "1"
LLM_FAKE: bool = os.getenv("LLM_FAKE", "0") == "1"
TALK_TO_HUMAN_URL: str | None = os.getenv("TALK_TO_HUMAN_URL") or None

FIXTURES_DIR = BACKEND_DIR / "fixtures"
DATA_DIR = BACKEND_DIR / "data"
CORPUS_DIR = BACKEND_DIR / "corpus"
RAG_DIR = BACKEND_DIR / "rag"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
