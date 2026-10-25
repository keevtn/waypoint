"""Generic evaluation pipeline (SPEC.md §6.4 "Evaluation pipeline", steps 1-3).

Steps 4-5 (corpus retrieval + LLM explainer) belong to /explain in Wave 2 and
read the cached Evaluation; the chart must render before explanations arrive.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from datetime import date

from ..models import Constraint, EvaluateResponse, Option, Profile, ProjectionResult
from ..projection import project
from . import cache
from .base import DecisionModule, module_suggestions, resolve_statuses
from .citations import PROJECTION_FLOOR

HORIZON_MONTHS = 12
HORIZON_ASSUMPTION = "Beyond 12 months this assumes income and recurring bills stay as they are today and one-time costs are not repeated."


def _dollars(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(int(cents)) // 100:,}"


def _when(d: date) -> str:
    return f"{d:%b} {d.day}"


def projection_constraints(options: list[Option], projections: dict[str, ProjectionResult], profile: Profile, horizon_months: int = HORIZON_MONTHS) -> list[Constraint]:
    """Module-agnostic flags derived from each option's own projection, so an option that dips
    below the floor (or negative) reads "Flagged", never "Fits". Disallowed still wins in
    `resolve_statuses`. Figures come from the engine; the rule text is templated here."""
    out: list[Constraint] = []
    floor = _dollars(profile.safety_floor_cents)
    for o in options:
        p = projections.get(o.id)
        if p is None:
            continue
        low = f"lowest {_dollars(p.min_balance_cents)} on {_when(p.min_balance_date)}"
        if p.months_below_floor:
            n = len(p.months_below_floor)
            out.append(
                Constraint(
                    id=f"below_floor_{o.id}",
                    kind="flag",
                    applies_to=[o.id],
                    rule=f"Projected below your {floor} floor in {n} of the next {horizon_months} months ({low}).",
                    citation_ids=PROJECTION_FLOOR,
                )
            )
        if p.months_negative:
            n = len(p.months_negative)
            out.append(
                Constraint(
                    id=f"negative_{o.id}",
                    kind="flag",
                    applies_to=[o.id],
                    rule=f"Projected to run out of money: the balance goes negative in {n} of the next {horizon_months} months ({low}).",
                    citation_ids=PROJECTION_FLOOR,
                )
            )
    return out


class InvalidInputs(ValueError):
    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__("invalid inputs")
        self.errors = errors


def with_horizon_assumption(options: list[Option], horizon_months: int) -> list[Option]:
    """Beyond 12 months every option carries the assumption as attributes (`horizon_months`,
    `horizon_assumption`), so the client and the LLM payloads see it without a new model field."""
    if horizon_months <= HORIZON_MONTHS:
        return options
    return [o.model_copy(update={"attributes": {**o.attributes, "horizon_months": horizon_months, "horizon_assumption": HORIZON_ASSUMPTION}}) for o in options]


def evaluate(module: DecisionModule, raw_inputs: dict[str, Any], profile: Profile, horizon_months: int = HORIZON_MONTHS) -> EvaluateResponse:
    """`horizon_months` (12 / 60 / 120, validated by the route) is the projection length for the
    baseline, every option and later stress runs. Financed options amortize over their own term
    regardless. Module suggestions keep their 12-month view (see big_purchase/suggest.py)."""
    try:
        inputs = module.InputModel.model_validate(raw_inputs)
    except ValidationError as e:
        raise InvalidInputs(e.errors(include_url=False)) from e

    options = module.candidate_options(inputs, profile)
    constraints = module.constraints(inputs, profile, options)
    options = resolve_statuses(options, constraints)
    extra = module.extra_commitments(inputs, profile)

    projections = {"baseline": project(profile, extra, horizon_months)}
    for o in options:  # disallowed options are projected too so the chart can grey them out
        projections[o.id] = project(profile, [*extra, o.commitment], horizon_months, option_id=o.id)

    constraints = [*constraints, *projection_constraints(options, projections, profile, horizon_months)]
    options = resolve_statuses(options, constraints)  # re-resolve: a below-floor option is "flagged", not "fits"

    suggestions = module_suggestions(module, inputs, profile, options, projections)
    options = with_horizon_assumption(options, horizon_months)

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
        horizon_months=horizon_months,
    )
    cache.put(ev)
    return EvaluateResponse(options=options, constraints=constraints, projections=projections, eval_id=ev.eval_id, suggestions=suggestions)
