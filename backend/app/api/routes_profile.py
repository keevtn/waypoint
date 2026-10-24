"""Profile + baseline projection routes (SPEC.md §7).

Phase 1 (Session A): GET/PUT /profile and /profile/transactions come from
profile/store.py (detect.py over the ingested transactions).
Phase 2 (Session A): /projection/baseline = project(profile, []) from projection/engine.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..models import Profile, ProjectionResult, Transaction
from ..profile import store
from ..projection import project

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=Profile)
def get_profile() -> Profile:
    return store.get_profile()


@router.put("/profile", response_model=Profile)
def put_profile(patch: dict) -> Profile:
    return store.update_profile(patch)


@router.get("/profile/transactions", response_model=list[Transaction])
def get_transactions(limit: int = Query(50, ge=1, le=500)) -> list[Transaction]:
    return store.get_transactions(limit)


@router.get("/projection/baseline", response_model=ProjectionResult)
def get_baseline() -> ProjectionResult:
    return project(store.get_profile(), [])
