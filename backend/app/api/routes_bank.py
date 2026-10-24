"""Bank routes (SPEC.md §7). Phase 0: fixture-backed stubs. Phase 8 (Session D) makes them real."""
from __future__ import annotations

from fastapi import APIRouter

from .. import fixtures
from ..models import ConnectResponse

router = APIRouter(prefix="/api/bank", tags=["bank"])


@router.post("/connect", response_model=ConnectResponse)
def connect(body: dict | None = None) -> ConnectResponse:
    return ConnectResponse.model_validate(fixtures.load("connect"))
