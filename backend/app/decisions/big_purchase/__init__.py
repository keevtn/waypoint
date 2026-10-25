"""Big purchase decision module: when to buy something large, and whether to pay cash or
finance it. Options are the cash plan plus amortized financing terms; constraints are slack
and interest-cost flags (nothing disallowed); when cash on the chosen date breaks the floor,
`suggest.py` adds code-generated alternatives the client can apply as input patches."""
from __future__ import annotations

from datetime import date
from typing import Any, ClassVar

from ...models import Commitment, Constraint, Option, Profile, ProjectionResult, ScenarioTemplate, Suggestion
from . import action, options, rules, scenarios, suggest
from .inputs import BigPurchaseInputs, Financing

__all__ = ["BigPurchaseModule", "BigPurchaseInputs", "Financing"]


class BigPurchaseModule:
    id: ClassVar[str] = "big_purchase"
    title: ClassVar[str] = "Big purchase"
    description: ClassVar[str] = "Decide when to buy something large, and whether to pay cash or finance it, without dipping below your safety floor."
    corpus_tags: ClassVar[list[str]] = ["general"]
    InputModel: ClassVar[type[BigPurchaseInputs]] = BigPurchaseInputs

    def candidate_options(self, inputs: BigPurchaseInputs, profile: Profile) -> list[Option]:
        return options.build_options(inputs, profile)

    def constraints(self, inputs: BigPurchaseInputs, profile: Profile, opts: list[Option]) -> list[Constraint]:
        return rules.build_constraints(inputs, profile, opts)

    def extra_commitments(self, inputs: BigPurchaseInputs, profile: Profile) -> list[Commitment]:
        return []

    def scenario_menu(self, inputs: BigPurchaseInputs, profile: Profile) -> list[ScenarioTemplate]:
        return scenarios.scenario_menu(inputs, profile)

    def action_template(self, inputs: BigPurchaseInputs, option: Option, as_of: Any = None) -> dict[str, Any]:
        return action.action_template(inputs, option, as_of or date.today())

    def suggestions(self, inputs: BigPurchaseInputs, profile: Profile, opts: list[Option], projections: dict[str, ProjectionResult]) -> list[Suggestion]:
        return suggest.suggest(inputs, profile, projections)
