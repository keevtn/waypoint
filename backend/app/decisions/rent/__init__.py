"""Rent decision module (SPEC.md §6.4 "Rent module (stretch)"). Proves the module pattern:
options are user-entered units, constraints are the HUD 30 percent standard and a move-in
cash check, and the generic pipeline, explainer, stress-tester and action card do the rest."""
from __future__ import annotations

from datetime import date
from typing import Any, ClassVar

from ...models import Commitment, Constraint, Option, Profile, ScenarioTemplate
from . import action, options, rules, scenarios
from .inputs import RentInputs, RentUnit

__all__ = ["RentModule", "RentInputs", "RentUnit"]


class RentModule:
    id: ClassVar[str] = "rent"
    title: ClassVar[str] = "Rent"
    description: ClassVar[str] = "Compare 2 to 4 apartments against your income and cash flow before you sign a lease."
    corpus_tags: ClassVar[list[str]] = ["rent", "general"]
    InputModel: ClassVar[type[RentInputs]] = RentInputs

    def candidate_options(self, inputs: RentInputs, profile: Profile) -> list[Option]:
        return options.build_options(inputs, profile)

    def constraints(self, inputs: RentInputs, profile: Profile, opts: list[Option]) -> list[Constraint]:
        return rules.build_constraints(inputs, profile, opts)

    def extra_commitments(self, inputs: RentInputs, profile: Profile) -> list[Commitment]:
        return []

    def scenario_menu(self, inputs: RentInputs, profile: Profile) -> list[ScenarioTemplate]:
        return scenarios.scenario_menu(inputs, profile)

    def action_template(self, inputs: RentInputs, option: Option, as_of: Any = None) -> dict[str, Any]:
        return action.action_template(inputs, option, as_of or date.today())
