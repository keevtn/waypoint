"""Shared test setup. Forces the offline seams before the app imports config."""
from __future__ import annotations

import os

os.environ.setdefault("DATA_MODE", "local")
os.environ.setdefault("LLM_FAKE", "1")
os.environ.setdefault("DEV_MODE", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("PLAID_CLIENT_ID", "test")
os.environ.setdefault("PLAID_SECRET", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
