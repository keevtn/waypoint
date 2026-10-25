"""Bank routes (SPEC.md §7).

Phase 1 (Session A): local mode ingests the persona through profile/store.py.
Phase 8 (Session D) adds the Plaid sandbox path behind store.connect().
"""
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..bank import csv_import
from ..models import ConnectResponse, CsvImportResponse
from ..profile import store

router = APIRouter(prefix="/api/bank", tags=["bank"])


@router.post("/connect", response_model=ConnectResponse)
def connect(body: dict | None = None) -> ConnectResponse:
    state = store.connect()
    return ConnectResponse(item_id=state.item_id, institution=state.institution, transactions=len(state.transactions))


@router.post("/import_csv", response_model=CsvImportResponse)
async def import_csv(
    file: UploadFile = File(...),
    mapping: str | None = Form(None),
    balance_cents: int | None = Form(None),
) -> CsvImportResponse:
    """Replace the single-user store's transactions with a bank CSV export and rebuild the profile.
    The file stays in memory (never written to disk) and row contents are never logged."""
    data = await file.read(csv_import.MAX_BYTES + 1)
    try:
        cols = json.loads(mapping) if mapping else None
        if cols is not None and not (isinstance(cols, dict) and all(isinstance(v, str) for v in cols.values())):
            raise ValueError("mapping must be an object of column names")
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_mapping", "message": f"mapping is not valid JSON: {e}"})
    try:
        parsed = csv_import.parse(csv_import.decode(data), cols)
    except csv_import.CsvImportError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_csv", "message": str(e)})
    profile, warnings = store.import_transactions(parsed.transactions, balance_cents)
    return CsvImportResponse(imported=len(parsed.transactions), skipped=parsed.skipped, profile=profile, warnings=[*parsed.warnings, *warnings])
