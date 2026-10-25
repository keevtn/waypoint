"""Generic evaluation pipeline (SPEC.md §6.4 "Evaluation pipeline", steps 1-3).

Steps 4-5 (corpus retrieval + LLM explainer) belong to /explain in Wave 2 and
read the cached Evaluation; the chart must render before explanations arrive.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..models import EvaluateResponse, Profile
from ..projection import project
from . import cache
from .base import DecisionModule, module_suggestions, resolve_statuses


class InvalidInputs(ValueError):
    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__("invalid inputs")
        self.errors = errors


def evaluate(module: DecisionModule, raw_inputs: dict[str, Any], profile: Profile) -> EvaluateResponse:
    try:
        inputs = module.InputModel.model_validate(raw_inputs)
    except ValidationError as e:
        raise InvalidInputs(e.errors(include_url=False)) from e

    options = module.candidate_options(inputs, profile)
    constraints = module.constraints(inputs, profile, options)
    options = resolve_statuses(options, constraints)
    extra = module.extra_commitments(inputs, profile)

    projections = {"baseline": project(profile, extra)}
    for o in options:  # disallowed options are projected too so the chart can grey them out
        projections[o.id] = project(profile, [*extra, o.commitment], option_id=o.id)

    suggestions = module_suggestions(module, inputs, profile, options, projections)

    ev = cache.Evaluation(
        eval_id=cache.new_id(),
        module_id=module.id,
        inputs=inputs,
        profile=profile,
        options=options,
        constraints=constraints,
        extra_commitments=extra,
        projections=projections,
        suggestions=suggestions,
    )
    cache.put(ev)
    return EvaluateResponse(options=options, constraints=constraints, projections=projections, eval_id=ev.eval_id, suggestions=suggestions)
