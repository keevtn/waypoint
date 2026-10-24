"""Auto insurance decision module (SPEC.md §6.4 "Auto insurance module")."""
from __future__ import annotations

from typing import Any, ClassVar

from ...models import Commitment, Constraint, Option, Profile, ScenarioTemplate
from . import action, options, rules, scenarios
from .inputs import AutoInsuranceInputs, UserQuote

__all__ = ["AutoInsuranceModule", "AutoInsuranceInputs", "UserQuote"]


class AutoInsuranceModule:
    id: ClassVar[str] = "auto_insurance"
    title: ClassVar[str] = "Auto insurance"
    description: ClassVar[str] = "Choose a coverage configuration for a car you just bought or financed."
    corpus_tags: ClassVar[list[str]] = ["auto_insurance", "general"]
    InputModel: ClassVar[type[AutoInsuranceInputs]] = AutoInsuranceInputs

    def candidate_options(self, inputs: AutoInsuranceInputs, profile: Profile) -> list[Option]:
        return options.build_options(inputs, profile.as_of)

    def constraints(self, inputs: AutoInsuranceInputs, profile: Profile, opts: list[Option]) -> list[Constraint]:
        return rules.build_constraints(inputs, profile, opts)

    def extra_commitments(self, inputs: AutoInsuranceInputs, profile: Profile) -> list[Commitment]:
        loan = options.loan_commitment(inputs, profile.as_of)
        return [loan] if loan else []

    def scenario_menu(self, inputs: AutoInsuranceInputs, profile: Profile) -> list[ScenarioTemplate]:
        return scenarios.scenario_menu(inputs, profile)

    def action_template(self, inputs: AutoInsuranceInputs, option: Option, as_of: Any = None) -> dict[str, Any]:
        from datetime import date

        return action.action_template(inputs, option, as_of or date.today())
