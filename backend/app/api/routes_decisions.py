"""Decision routes (SPEC.md §7).

Phase 3 (Session A): GET /decisions and POST /evaluate are real (decisions/registry.py,
decisions/evaluate.py). Phase 6-7 (Session A, Wave 2) make /explain, /stress, /action
real via llm/; until then they return fixtures.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import fixtures
from ..decisions import registry
from ..decisions.evaluate import InvalidInputs, evaluate as run_evaluate
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

from ..profile import store

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


def _module(decision_id: str):
    mod = registry.get(decision_id)
    if mod is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "unknown_decision", "message": f"No decision module {decision_id!r}"},
        )
    return mod


def _check(decision_id: str) -> None:
    _module(decision_id)


@router.get("", response_model=list[DecisionSummary])
def list_decisions() -> list[DecisionSummary]:
    return registry.summaries()


@router.post("/{decision_id}/evaluate", response_model=EvaluateResponse)
def evaluate(decision_id: str, body: EvaluateRequest) -> EvaluateResponse:
    mod = _module(decision_id)
    try:
        return run_evaluate(mod, body.inputs, store.get_profile())
    except InvalidInputs as e:
        raise HTTPException(status_code=422, detail={"code": "invalid_inputs", "message": "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors)})


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
