"""Decision module plug-in protocol (SPEC.md §6.4).

A module turns user inputs + a Profile into candidate Options and Constraints.
The generic evaluation pipeline (`evaluate.py`) does everything else: status
resolution, projections per option, caching. Modules never do money math
beyond building Commitments; the projection engine owns balances.
"""
from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel

from ..models import Commitment, Constraint, Option, Profile, ProjectionResult, ScenarioTemplate, Suggestion


@runtime_checkable
class DecisionModule(Protocol):
    id: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    corpus_tags: ClassVar[list[str]]
    InputModel: ClassVar[type[BaseModel]]

    def candidate_options(self, inputs: Any, profile: Profile) -> list[Option]: ...

    def constraints(self, inputs: Any, profile: Profile, options: list[Option]) -> list[Constraint]: ...

    def extra_commitments(self, inputs: Any, profile: Profile) -> list[Commitment]:
        """Commitments applied to every option (e.g. the car loan)."""
        ...

    def scenario_menu(self, inputs: Any, profile: Profile) -> list[ScenarioTemplate]: ...

    def action_template(self, inputs: Any, option: Option) -> dict[str, Any]:
        """Seeds (steps, questions, deadline) for the action-card LLM call."""
        ...

    def suggestions(self, inputs: Any, profile: Profile, options: list[Option], projections: dict[str, ProjectionResult]) -> list[Suggestion]:
        """Optional: code-generated alternatives (input patches) once the projections are known. Default none."""
        ...


def module_suggestions(module: Any, inputs: Any, profile: Profile, options: list[Option], projections: dict[str, ProjectionResult]) -> list[Suggestion]:
    fn = getattr(module, "suggestions", None)
    return list(fn(inputs, profile, options, projections)) if callable(fn) else []


def resolve_statuses(options: list[Option], constraints: list[Constraint]) -> list[Option]:
    """Attach constraint ids to options and derive status: disallowed > flagged > allowed.

    `required` constraints are informational (they list the options that satisfy a
    requirement, or all options for a legal baseline); `disallowed` ones name the
    options that fail a hard requirement; `flag` ones warn.
    """
    out: list[Option] = []
    for o in options:
        mine = [c for c in constraints if o.id in c.applies_to]
        status: str = "allowed"
        if any(c.kind == "disallowed" for c in mine):
            status = "disallowed"
        elif any(c.kind == "flag" for c in mine):
            status = "flagged"
        out.append(o.model_copy(update={"status": status, "constraint_ids": [c.id for c in mine]}))
    return out
