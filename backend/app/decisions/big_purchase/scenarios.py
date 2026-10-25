"""Big-purchase stress-scenario menu: shock_expense, income_gap, hours_cut. No deductible
(no option carries risk exposure). Min/max in params_schema bound the LLM's picks."""
from __future__ import annotations

from ...models import Profile, ScenarioTemplate
from .inputs import BigPurchaseInputs


def _int(minimum: int, maximum: int, description: str, default: int | None = None) -> dict:
    d: dict = {"type": "integer", "minimum": minimum, "maximum": maximum, "description": description}
    if default is not None:
        d["default"] = default
    return d


def scenario_menu(inputs: BigPurchaseInputs, profile: Profile) -> list[ScenarioTemplate]:
    return [
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
            id="spending_up",
            label="Your everyday spending runs higher than usual.",
            params_schema={
                "type": "object",
                "properties": {"pct": _int(10, 40, "Percent increase in everyday (variable) spending for the whole horizon", 25)},
                "required": ["pct"],
            },
        ),
    ]
