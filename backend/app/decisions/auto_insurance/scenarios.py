"""Stress-scenario menu (SPEC.md §6.4 "Scenario menu"). Templates carry min/max so the
LLM (Wave 2, /stress) cannot pick absurd parameters; the backend runs them through project()."""
from __future__ import annotations

from ...models import Profile, ScenarioTemplate
from .inputs import AutoInsuranceInputs


def _int(minimum: int, maximum: int, description: str, default: int | None = None) -> dict:
    d: dict = {"type": "integer", "minimum": minimum, "maximum": maximum, "description": description}
    if default is not None:
        d["default"] = default
    return d


def scenario_menu(inputs: AutoInsuranceInputs, profile: Profile) -> list[ScenarioTemplate]:
    return [
        ScenarioTemplate(
            id="deductible_claim",
            label="You have to pay the deductible after a claim",
            params_schema={
                "type": "object",
                "properties": {"month": _int(1, 6, "Plan month of the claim (1 = next month)", 2)},
                "required": ["month"],
            },
        ),
        ScenarioTemplate(
            id="shock_expense",
            label="An unexpected expense",
            params_schema={
                "type": "object",
                "properties": {
                    "amount_cents": _int(20000, 150000, "Size of the expense in cents"),
                    "month": _int(1, 12, "Plan month it lands (1 = next month)"),
                },
                "required": ["amount_cents", "month"],
            },
        ),
        ScenarioTemplate(
            id="income_gap",
            label="Paychecks stop for a while",
            params_schema={
                "type": "object",
                "properties": {
                    "months": _int(1, 3, "How many months without payroll"),
                    "start_month": _int(1, 10, "Plan month the gap starts (1 = next month)"),
                },
                "required": ["months", "start_month"],
            },
        ),
        ScenarioTemplate(
            id="hours_cut",
            label="Hours get cut",
            params_schema={
                "type": "object",
                "properties": {
                    "pct": _int(10, 50, "Percent reduction in payroll"),
                    "from_month": _int(1, 12, "Plan month the cut starts (1 = next month)"),
                },
                "required": ["pct", "from_month"],
            },
        ),
        ScenarioTemplate(
            id="rent_increase",
            label="Rent goes up at renewal",
            params_schema={
                "type": "object",
                "properties": {
                    "pct": _int(3, 15, "Percent rent increase"),
                    "from_month": _int(1, 12, "Plan month the new rent starts (1 = next month)"),
                },
                "required": ["pct", "from_month"],
            },
        ),
    ]
