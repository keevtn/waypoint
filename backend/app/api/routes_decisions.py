"""Decision routes (SPEC.md §7). Phase 0: fixture-backed stubs.

Phase 3 (Session A) makes /evaluate real; Phase 6–7 (Session A, Wave 2) make
/explain, /stress, /action real via llm/.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import fixtures
from ..models import (
    ActionCard,
    ActionRequest,
    DecisionSummary,
    EvaluateRequest,
    EvaluateResponse,
    ExplainRequest,
    ExplainResponse,
    StressRequest,
    StressResponse,
)

router = APIRouter(prefix="/api/decisions", tags=["decisions"])

_KNOWN = {"auto_insurance"}


def _check(decision_id: str) -> None:
    if decision_id not in _KNOWN:
        raise HTTPException(
            status_code=404,
            detail={"code": "unknown_decision", "message": f"No decision module {decision_id!r}"},
        )


@router.get("", response_model=list[DecisionSummary])
def list_decisions() -> list[DecisionSummary]:
    return [DecisionSummary.model_validate(d) for d in fixtures.load("decisions")]


@router.post("/{decision_id}/evaluate", response_model=EvaluateResponse)
def evaluate(decision_id: str, body: EvaluateRequest) -> EvaluateResponse:
    _check(decision_id)
    return EvaluateResponse.model_validate(fixtures.load("evaluate_auto"))


@router.post("/{decision_id}/explain", response_model=ExplainResponse)
def explain(decision_id: str, body: ExplainRequest) -> ExplainResponse:
    _check(decision_id)
    return ExplainResponse.model_validate(fixtures.load("explain_auto"))


@router.post("/{decision_id}/stress", response_model=StressResponse)
def stress(decision_id: str, body: StressRequest) -> StressResponse:
    _check(decision_id)
    return StressResponse.model_validate(fixtures.load("stress_auto"))


@router.post("/{decision_id}/action", response_model=ActionCard)
def action(decision_id: str, body: ActionRequest) -> ActionCard:
    _check(decision_id)
    card = ActionCard.model_validate(fixtures.load("action_auto"))
    return card.model_copy(update={"option_id": body.option_id})
