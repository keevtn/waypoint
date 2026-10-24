"""Load hand-written JSON fixtures from backend/fixtures/.

Phase 0 endpoints return these verbatim. Later phases replace the stubs with
real implementations; the fixtures stay as the frontend's VITE_USE_FIXTURES=1
source and as golden shapes for the smoke test.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .config import FIXTURES_DIR


@lru_cache(maxsize=None)
def load(name: str) -> Any:
    path = FIXTURES_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)
