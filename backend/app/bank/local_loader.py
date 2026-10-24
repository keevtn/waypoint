"""DATA_MODE=local ingestion (SPEC.md §6.1): load the persona document and
normalize it into §5 Transactions. Same downstream path as Plaid.

Reads backend/data/persona_student.json when present and current (written by
scripts/make_persona.py); otherwise generates the persona in memory for today,
so local mode never depends on a generated file and the history is always
"the last 4 months".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .. import config
from ..models import OneOff, Transaction
from ..profile.normalize import normalize_merchant
from . import persona

PERSONA_PATH: Path = config.DATA_DIR / "persona_student.json"


@dataclass
class LocalData:
    as_of: date
    balance_cents: int
    safety_floor_cents: int
    transactions: list[Transaction]
    one_offs: list[OneOff]
    declared_income: list[dict[str, Any]] = field(default_factory=list)
    declared_recurring: list[dict[str, Any]] = field(default_factory=list)
    moment: dict[str, Any] = field(default_factory=dict)
    institution: str = "Local persona (sandbox format)"
    item_id: str = "item_local_persona"


def load_document(as_of: date | None = None) -> dict[str, Any]:
    """Persona document for `as_of` (default today). Prefers the on-disk file when it is current."""
    today = as_of or date.today()
    if as_of is None and PERSONA_PATH.is_file():
        with PERSONA_PATH.open(encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("as_of") == today.isoformat():
            return doc
    return persona.generate(today)


def from_document(doc: dict[str, Any]) -> LocalData:
    txns = [
        Transaction(
            id=t["id"],
            date=date.fromisoformat(t["date"]),
            amount_cents=int(t["amount_cents"]),
            raw_name=t["raw_name"],
            merchant=normalize_merchant(t["raw_name"]).label,
            category=t.get("category"),
        )
        for t in doc["transactions"]
    ]
    return LocalData(
        as_of=date.fromisoformat(doc["as_of"]),
        balance_cents=int(doc["balance_cents"]),
        safety_floor_cents=int(doc.get("safety_floor_cents", persona.SAFETY_FLOOR_CENTS)),
        transactions=txns,
        one_offs=[OneOff.model_validate(o) for o in doc.get("future_one_offs", [])],
        declared_income=doc.get("declared_income", []),
        declared_recurring=doc.get("declared_recurring", []),
        moment=doc.get("moment", {}),
    )


def load(as_of: date | None = None) -> LocalData:
    return from_document(load_document(as_of))
