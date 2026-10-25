"""Decision routes (SPEC.md §7).

Phase 3 (Session A): GET /decisions and POST /evaluate are real (decisions/registry.py,
decisions/evaluate.py). Phase 6 (Session A, Wave 2): /explain and /action call the LLM
layer (llm/explainer.py, llm/action.py) on the cached evaluation; Phase 7: /stress (llm/stress.py).

An unknown or expired eval_id is 404 `unknown_eval` (cache TTL is 1h). LLM failures are
502 `llm_unavailable`; a numeric-guardrail violation under DEV_MODE=1 is 502
`guardrail_violation` listing the offending numbers (SPEC §3.2: raise in dev, strip in prod).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

import logging

from ..decisions import cache, registry
from ..decisions.evaluate import InvalidInputs, evaluate as run_evaluate
from ..llm import action as llm_action
from ..llm import explainer, stress as llm_stress
from ..llm.client import LLMError
from ..llm.guardrail import GuardrailViolation
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
from .routes_profile import check_horizon

log = logging.getLogger(__name__)

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


def _evaluation(decision_id: str, eval_id: str) -> cache.Evaluation:
    ev = cache.get(eval_id)
    if ev is None or ev.module_id != decision_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "unknown_eval", "message": f"No evaluation {eval_id!r} for {decision_id!r}; run /evaluate again"},
        )
    return ev


def _option(ev: cache.Evaluation, option_id: str):
    for o in ev.options:
        if o.id == option_id:
            return o
    raise HTTPException(status_code=404, detail={"code": "unknown_option", "message": f"No option {option_id!r} in this evaluation"})


def _llm_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, GuardrailViolation):
        log.error("guardrail violation (%s): %s", exc.where, exc.offending)
        return HTTPException(
            status_code=502,
            detail={"code": "guardrail_violation", "message": f"The model produced numbers that are not in its input and the response was rejected: {', '.join(exc.offending)}"},
        )
    log.error("llm failure: %s", exc)
    return HTTPException(status_code=502, detail={"code": "llm_unavailable", "message": str(exc)})


@router.get("", response_model=list[DecisionSummary])
def list_decisions() -> list[DecisionSummary]:
    return registry.summaries()


@router.post("/{decision_id}/evaluate", response_model=EvaluateResponse)
def evaluate(decision_id: str, body: EvaluateRequest) -> EvaluateResponse:
    mod = _module(decision_id)
    check_horizon(body.horizon_months)
    try:
        return run_evaluate(mod, body.inputs, store.get_profile())
    except InvalidInputs as e:
        raise HTTPException(status_code=422, detail={"code": "invalid_inputs", "message": "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors)})


@router.post("/{decision_id}/explain", response_model=ExplainResponse)
def explain(decision_id: str, body: ExplainRequest) -> ExplainResponse:
    _check(decision_id)
    ev = _evaluation(decision_id, body.eval_id)
    try:
        return ExplainResponse(explanations=explainer.explain(ev))
    except (LLMError, GuardrailViolation) as e:
        raise _llm_errors(e) from e


@router.post("/{decision_id}/stress", response_model=StressResponse)
def stress(decision_id: str, body: StressRequest) -> StressResponse:
    mod = _module(decision_id)
    ev = _evaluation(decision_id, body.eval_id)
    preferred = _option(ev, body.preferred_option_id)
    try:
        results, crit = llm_stress.stress_test(ev, mod, preferred)
    except (LLMError, GuardrailViolation) as e:
        raise _llm_errors(e) from e
    return StressResponse(scenarios=results, critique=crit)


@router.post("/{decision_id}/action", response_model=ActionCard)
def action(decision_id: str, body: ActionRequest) -> ActionCard:
    mod = _module(decision_id)
    ev = _evaluation(decision_id, body.eval_id)
    option = _option(ev, body.option_id)
    try:
        return llm_action.action_card(ev, mod, option)
    except (LLMError, GuardrailViolation) as e:
        raise _llm_errors(e) from e
