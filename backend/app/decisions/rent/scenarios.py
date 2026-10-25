"""Rent stress-scenario menu (SPEC.md §6.4 "Rent module"): income_gap (a summer gap for a
student), shock_expense, rent_increase. Min/max in params_schema bound the LLM's picks."""
from __future__ import annotations

from ...models import Profile, ScenarioTemplate
from .inputs import RentInputs


def _int(minimum: int, maximum: int, description: str, default: int | None = None) -> dict:
    d: dict = {"type": "integer", "minimum": minimum, "maximum": maximum, "description": description}
    if default is not None:
        d["default"] = default
    return d


def scenario_menu(inputs: RentInputs, profile: Profile) -> list[ScenarioTemplate]:
    return [
        ScenarioTemplate(
            id="income_gap",
            label="Paychecks stop over the summer",
            params_schema={
                "type": "object",
                "properties": {
                    "months": _int(1, 3, "How many months without payroll (a summer gap between semesters is usually 2 to 3)", 2),
                    "start_month": _int(1, 10, "Plan month the gap starts (1 = next month)"),
                },
                "required": ["months", "start_month"],
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
