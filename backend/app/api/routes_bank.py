"""Bank routes (SPEC.md §7).

Phase 1 (Session A): local mode ingests the persona through profile/store.py.
Phase 8 (Session D) adds the Plaid sandbox path behind store.connect().
"""
from __future__ import annotations

from fastapi import APIRouter

from ..models import ConnectResponse
from ..profile import store

router = APIRouter(prefix="/api/bank", tags=["bank"])


@router.post("/connect", response_model=ConnectResponse)
def connect(body: dict | None = None) -> ConnectResponse:
    state = store.connect()
    return ConnectResponse(item_id=state.item_id, institution=state.institution, transactions=len(state.transactions))
