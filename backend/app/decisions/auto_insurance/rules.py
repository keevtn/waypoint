"""Auto-insurance constraints (SPEC.md §6.4 "Constraints"). Every rule cites corpus chunk ids.

Kinds: `disallowed` names options that fail a hard requirement (lender);
`required` is informational (legal baseline, applies to all); `flag` warns.
"""
from __future__ import annotations

from ...models import Constraint, Option, Profile
from .. import citations
from .inputs import AutoInsuranceInputs

LOW_VALUE_VEHICLE_CENTS = 400000


def _has_comp_coll(o: Option) -> bool:
    return bool(o.attributes.get("collision")) and bool(o.attributes.get("comprehensive"))


def build_constraints(inputs: AutoInsuranceInputs, profile: Profile, options: list[Option]) -> list[Constraint]:
    out: list[Constraint] = []

    if inputs.financed:
        lacking = [o.id for o in options if not _has_comp_coll(o)]
        if lacking:
            out.append(
                Constraint(
                    id="c_lender_comp_coll",
                    kind="disallowed",
                    applies_to=lacking,
                    rule="Lenders generally require collision and comprehensive coverage on a financed vehicle; this configuration has neither.",
                    citation_ids=citations.LENDER_REQUIRES_COMP_COLL,
                )
            )

    out.append(
        Constraint(
            id="c_pa_minimum",
            kind="required",
            applies_to=[o.id for o in options],
            rule="Pennsylvania requires 15/30/5 liability plus $5,000 first-party medical benefits; a lapse can suspend registration.",
            citation_ids=citations.PA_MINIMUM_COVERAGE,
        )
    )

    if inputs.vehicle_value_cents < LOW_VALUE_VEHICLE_CENTS:
        ids = [o.id for o in options if _has_comp_coll(o)]
        if ids:
            out.append(
                Constraint(
                    id="c_low_value_collision",
                    kind="flag",
                    applies_to=ids,
                    rule="Collision coverage may cost more than it returns on a low-value car.",
                    citation_ids=citations.LOW_VALUE_COLLISION,
                )
            )

    over = [o.id for o in options if int(o.attributes.get("deductible") or 0) * 100 > inputs.deductible_comfort_cents]
    if over:
        out.append(
            Constraint(
                id="c_deductible_comfort",
                kind="flag",
                applies_to=over,
                rule="Deductible exceeds what you said you could pay on short notice.",
                citation_ids=citations.DEDUCTIBLE_TRADEOFF,
            )
        )

    limited = [o.id for o in options if o.attributes.get("tort") == "limited"]
    if limited:
        out.append(
            Constraint(
                id="c_limited_tort",
                kind="flag",
                applies_to=limited,
                rule="Limited tort lowers the premium but waives most pain-and-suffering claims unless an exception applies.",
                citation_ids=citations.PA_LIMITED_TORT,
            )
        )
    return out
