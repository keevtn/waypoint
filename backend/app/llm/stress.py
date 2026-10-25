"""Stress-tester (SPEC.md §6.6 "Stress-tester", two LLM calls).

1. *Select*: the model picks exactly 3 scenarios from the module's scenario menu for
   this user. Code validates every choice against the template's params_schema
   (unknown templates dropped, parameters clamped to min/max, duplicates and
   missing picks back-filled from a deterministic default list), so the model can
   never run an absurd scenario or skip the deductible claim.
2. Code runs each scenario through `project()` for the baseline and every
   non-disallowed option by perturbing inputs: `one_off_overrides` for claims,
   shocks and rent increases; `income_multiplier` for income gaps and hours cuts.
3. *Critique*: the model argues against the preferred option using only the results;
   the guardrail is applied against that payload; citations are rebuilt from chunk ids.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..decisions.cache import Evaluation
from ..models import Critique, OneOff, Option, Profile, ProjectionResult, Scenario, ScenarioTemplate, StressResult
from ..projection import project
from . import guardrail, payload
from .client import get_llm
from .explainer import scrub_markers, used_chunk_ids

log = logging.getLogger(__name__)

N_SCENARIOS = 3
HORIZON = 12


class ScenarioParamsOut(BaseModel):
    """Union of every template's parameters; unused ones are null. Code clamps the rest."""

    model_config = ConfigDict(extra="forbid")
    month: int | None = None
    amount_cents: int | None = None
    months: int | None = None
    start_month: int | None = None
    pct: int | None = None
    from_month: int | None = None


class ScenarioOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: str
    params: ScenarioParamsOut
    rationale: str


class SelectOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenarios: list[ScenarioOut]


class CritiqueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_against: list[str]
    case_for: list[str]
    recommendation_shift: Literal["stay", "reconsider", "switch"]
    summary: str
    citation_ids: list[str]


# ---------------------------------------------------------------------------
# Scenario selection
# ---------------------------------------------------------------------------


def _clamp(value: Any, spec: dict) -> int:
    lo, hi = spec.get("minimum"), spec.get("maximum")
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = int(spec.get("default", lo if lo is not None else 1))
    if lo is not None:
        v = max(v, int(lo))
    if hi is not None:
        v = min(v, int(hi))
    return v


def normalize_scenario(template: ScenarioTemplate, params: dict[str, Any], rationale: str) -> Scenario:
    """Keep only the template's parameters, clamped into [minimum, maximum]."""
    props: dict[str, dict] = template.params_schema.get("properties", {})
    clean = {name: _clamp(params.get(name), spec) for name, spec in props.items()}
    return Scenario(template_id=template.id, params=clean, rationale=rationale.strip())


def default_scenarios(menu: list[ScenarioTemplate], ev: Evaluation) -> list[Scenario]:
    """Deterministic picks used to back-fill when the model's selection is unusable."""
    by_id = {t.id: t for t in menu}
    tight = sorted({m for p in ev.projections.values() for m in p.months_below_floor})
    months = payload.plan_months(ev.profile)
    inv = {v: k for k, v in months.items()}
    tight_n = inv.get(tight[0], 3) if tight else 3
    picks: list[tuple[str, dict, str]] = [
        ("deductible_claim", {"month": max(1, min(tight_n, 6))}, "A claim that lands in the month your balance is already lowest tests whether each deductible is actually affordable."),
        ("income_gap", {"months": 1, "start_month": max(1, tight_n - 1)}, "Payroll is your only earned income, so one missed month shows how little buffer the plan has."),
        ("shock_expense", {"amount_cents": 60000, "month": max(1, tight_n - 1)}, "An unexpected expense the size of your deductible comfort level, just before the tight month."),
        ("hours_cut", {"pct": 25, "from_month": 1}, "A cut in hours lowers every paycheck for the rest of the year."),
        ("rent_increase", {"pct": 8, "from_month": 1}, "Rent is your largest fixed cost; a renewal increase compounds every month."),
    ]
    return [normalize_scenario(by_id[t], p, r) for t, p, r in picks if t in by_id]


def select_payload(ev: Evaluation, menu: list[ScenarioTemplate], preferred_option_id: str) -> dict:
    return {
        "profile": payload.profile_view(ev.profile),
        "inputs": payload.inputs_view(ev.inputs),
        "options": [
            {"id": o.id, "label": o.label, "status": o.status, "price_display": f"{payload.dollars(o.price.cents)}/month", "deductible_display": payload.option_view(o, ev.constraints)["deductible_display"]}
            for o in ev.options
        ],
        "preferred_option_id": preferred_option_id,
        "projections": {k: payload.projection_view(p) for k, p in ev.projections.items()},
        "plan_months": {str(k): v for k, v in payload.plan_months(ev.profile).items()},
        "menu": [t.model_dump() for t in menu],
    }


def select_scenarios(ev: Evaluation, menu: list[ScenarioTemplate], preferred_option_id: str) -> list[Scenario]:
    by_id = {t.id: t for t in menu}
    data = select_payload(ev, menu, preferred_option_id)
    chosen: list[Scenario] = []
    try:
        out = get_llm().call("select", data, SelectOut)
        out = guardrail.apply(out, guardrail.allowed_numbers(data), where="select")
        for s in out.scenarios:
            t = by_id.get(s.template_id)
            if t is None or any(c.template_id == t.id for c in chosen):
                continue
            chosen.append(normalize_scenario(t, s.params.model_dump(), s.rationale))
            if len(chosen) == N_SCENARIOS:
                break
    except guardrail.GuardrailViolation:
        raise
    except Exception:
        log.exception("stress: scenario selection failed; using defaults")
        chosen = []

    has_deductible = any(o.commitment.risk_exposure_cents > 0 for o in ev.options if o.status != "disallowed")
    defaults = default_scenarios(menu, ev)
    if has_deductible and "deductible_claim" in by_id and not any(c.template_id == "deductible_claim" for c in chosen):
        chosen = [next(d for d in defaults if d.template_id == "deductible_claim"), *chosen][:N_SCENARIOS]
    for d in defaults:
        if len(chosen) >= N_SCENARIOS:
            break
        if not any(c.template_id == d.template_id for c in chosen):
            chosen.append(d)
    return chosen[:N_SCENARIOS]


# ---------------------------------------------------------------------------
# Running scenarios through the projection
# ---------------------------------------------------------------------------


def _rent_item(profile: Profile):
    rent = [r for r in profile.recurring if "rent" in r.label.lower()]
    pool = rent or list(profile.recurring)
    return min(pool, key=lambda r: r.amount_cents) if pool else None  # most negative = largest outflow


def perturbation(scenario: Scenario, profile: Profile, option: Option | None) -> tuple[list[OneOff], list[float] | None]:
    """(one_off_overrides, income_multiplier) that `project()` applies for this scenario."""
    p = scenario.params
    tid = scenario.template_id
    start = lambda n: payload.plan_month_start(profile, n)  # noqa: E731

    if tid == "deductible_claim":
        exposure = option.commitment.risk_exposure_cents if option else 0
        if exposure <= 0:
            return [], None
        return [OneOff(id="stress_deductible_claim", label=f"Deductible claim ({option.label})", amount_cents=-abs(exposure), date=start(p["month"]), source="module")], None

    if tid == "shock_expense":
        return [OneOff(id="stress_shock_expense", label="Unexpected expense", amount_cents=-abs(int(p["amount_cents"])), date=start(p["month"]), source="module")], None

    if tid == "income_gap":
        mult = [1.0] * HORIZON
        for i in range(p["start_month"] - 1, min(HORIZON, p["start_month"] - 1 + p["months"])):
            mult[i] = 0.0
        return [], mult

    if tid == "hours_cut":
        mult = [1.0] * HORIZON
        for i in range(p["from_month"] - 1, HORIZON):
            mult[i] = 1.0 - p["pct"] / 100.0
        return [], mult

    if tid == "rent_increase":
        rent = _rent_item(profile)
        if rent is None:
            return [], None
        extra = -int(round(abs(rent.amount_cents) * p["pct"] / 100.0))
        if extra == 0:
            return [], None
        day = min(rent.next_date.day, 28)
        one_offs = []
        for n in range(p["from_month"], HORIZON + 1):
            d = start(n).replace(day=day)
            one_offs.append(OneOff(id=f"stress_rent_increase_{n}", label=f"Rent increase ({p['pct']}%)", amount_cents=extra, date=d, source="module"))
        return one_offs, None

    return [], None


def run_scenario(ev: Evaluation, scenario: Scenario) -> StressResult:
    results: dict[str, ProjectionResult] = {}
    one_offs, mult = perturbation(scenario, ev.profile, None)
    results["baseline"] = project(ev.profile, ev.extra_commitments, HORIZON, None, one_offs or None, mult)
    for o in ev.options:
        if o.status == "disallowed":
            continue
        one_offs, mult = perturbation(scenario, ev.profile, o)
        results[o.id] = project(ev.profile, [*ev.extra_commitments, o.commitment], HORIZON, None, one_offs or None, mult, option_id=o.id)
    return StressResult(scenario=scenario, results=results)


# ---------------------------------------------------------------------------
# Critique
# ---------------------------------------------------------------------------


def critique_payload(ev: Evaluation, preferred: Option, stress: list[StressResult]) -> dict:
    from ..rag import facts

    cited = [facts.DEDUCTIBLE_AFFORDABLE, facts.DEDUCTIBLE_TRADEOFF] + [cid for c in ev.constraints for cid in c.citation_ids]
    query = "deductible you can afford higher deductible lower premium emergency savings lender requires collision comprehensive"
    chunks = payload.merge_chunks(payload.chunks_for_ids(cited), payload.retrieve_chunks(query, ev.module_id, k=4))
    return {
        "preferred_option_id": preferred.id,
        "options": [payload.option_view(o, ev.constraints) for o in ev.options],
        "inputs": payload.inputs_view(ev.inputs),
        "floor_display": payload.dollars(ev.profile.safety_floor_cents),
        "evaluations": {k: payload.projection_view(p) for k, p in ev.projections.items()},
        "scenarios": [
            {
                "template_id": s.scenario.template_id,
                "params": s.scenario.params,
                "rationale": s.scenario.rationale,
                "results": {k: payload.projection_view(p) for k, p in s.results.items()},
            }
            for s in stress
        ],
        "chunks": chunks,
    }


def critique(ev: Evaluation, preferred: Option, stress: list[StressResult]) -> Critique:
    data = critique_payload(ev, preferred, stress)
    out = get_llm().call("critique", data, CritiqueOut)
    out = guardrail.apply(out, guardrail.allowed_numbers(data), where="critique")
    chunk_ids = {c["id"] for c in data["chunks"]}
    constraint_ids = {c.id for c in ev.constraints}
    against = [x for x in (scrub_markers(s, chunk_ids, constraint_ids) for s in out.case_against) if x]
    for_ = [x for x in (scrub_markers(s, chunk_ids, constraint_ids) for s in out.case_for) if x]
    summary = scrub_markers(out.summary, chunk_ids, constraint_ids)
    if summary and summary not in against + for_:
        (against if out.recommendation_shift != "stay" else for_).append(summary)
    ids = used_chunk_ids(*against, *for_) + [c for c in out.citation_ids if c in chunk_ids]
    return Critique(
        preferred_option_id=preferred.id,
        case_against=against,
        case_for=for_,
        recommendation_shift=out.recommendation_shift,
        citations=payload.citations_for(ids, chunk_ids),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def stress_test(ev: Evaluation, module, preferred: Option) -> tuple[list[StressResult], Critique]:
    menu = module.scenario_menu(ev.inputs, ev.profile)
    scenarios = select_scenarios(ev, menu, preferred.id)
    results = [run_scenario(ev, s) for s in scenarios]
    return results, critique(ev, preferred, results)


__all__ = ["CritiqueOut", "SelectOut", "critique", "default_scenarios", "normalize_scenario", "perturbation", "run_scenario", "select_scenarios", "stress_test"]
