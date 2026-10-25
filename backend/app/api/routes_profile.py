"""Profile + baseline projection routes (SPEC.md §7).

Phase 1 (Session A): GET/PUT /profile and /profile/transactions come from
profile/store.py (detect.py over the ingested transactions). PUT /profile edits balance,
income, recurring, one-offs and the floor in the single-user store; POST /bank/connect resets.
Phase 2 (Session A): /projection/baseline = project(profile, []) from projection/engine.py.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from ..models import HORIZON_CHOICES, Profile, ProjectionResult, Transaction
from ..profile import store
from ..projection import project

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=Profile)
def get_profile() -> Profile:
    return store.get_profile()


@router.put("/profile", response_model=Profile)
def put_profile(patch: dict) -> Profile:
    """Partial Profile body: balance_cents, income / recurring / one_offs (full list replace) and
    safety_floor_cents. Unknown and computed fields are ignored; slack is recomputed server-side."""
    try:
        return store.update_profile(patch)
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors(include_url=False))
        raise HTTPException(status_code=422, detail={"code": "invalid_profile", "message": msg})


@router.get("/profile/transactions", response_model=list[Transaction])
def get_transactions(limit: int = Query(50, ge=1, le=500)) -> list[Transaction]:
    return store.get_transactions(limit)


def check_horizon(horizon_months: int) -> int:
    if horizon_months not in HORIZON_CHOICES:
        raise HTTPException(status_code=422, detail={"code": "invalid_horizon", "message": f"horizon_months must be one of {', '.join(map(str, HORIZON_CHOICES))}"})
    return horizon_months


@router.get("/projection/baseline", response_model=ProjectionResult)
def get_baseline(horizon_months: int = Query(12)) -> ProjectionResult:
    return project(store.get_profile(), [], horizon_months=check_horizon(horizon_months))
