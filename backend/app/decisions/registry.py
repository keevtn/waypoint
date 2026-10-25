"""id -> DecisionModule instance (SPEC.md §6.4). GET /api/decisions lists these."""
from __future__ import annotations

from ..models import DecisionSummary
from .auto_insurance import AutoInsuranceModule
from .base import DecisionModule
from .rent import RentModule

MODULES: dict[str, DecisionModule] = {m.id: m for m in [AutoInsuranceModule(), RentModule()]}


def get(decision_id: str) -> DecisionModule | None:
    return MODULES.get(decision_id)


def summaries() -> list[DecisionSummary]:
    return [
        DecisionSummary(id=m.id, title=m.title, description=m.description, input_schema=m.InputModel.model_json_schema())
        for m in MODULES.values()
    ]
