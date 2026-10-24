"""Profile + baseline projection routes (SPEC.md §7). Phase 0: fixture-backed stubs.

Phase 1 (Session A) wires GET/PUT /profile and /profile/transactions to detect.py;
Phase 2 wires /projection/baseline to projection/engine.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from .. import fixtures
from ..models import Profile, ProjectionResult, Transaction

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=Profile)
def get_profile() -> Profile:
    return Profile.model_validate(fixtures.load("profile"))


@router.put("/profile", response_model=Profile)
def put_profile(patch: dict) -> Profile:
    base = Profile.model_validate(fixtures.load("profile"))
    allowed = {k: v for k, v in patch.items() if k in {"safety_floor_cents", "one_offs", "recurring"}}
    return Profile.model_validate({**base.model_dump(mode="json"), **allowed})


@router.get("/profile/transactions", response_model=list[Transaction])
def get_transactions(limit: int = Query(50, ge=1, le=500)) -> list[Transaction]:
    return [Transaction.model_validate(t) for t in fixtures.load("transactions")][:limit]


@router.get("/projection/baseline", response_model=ProjectionResult)
def get_baseline() -> ProjectionResult:
    return ProjectionResult.model_validate(fixtures.load("baseline"))
