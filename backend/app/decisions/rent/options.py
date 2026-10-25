"""Rent options: one per candidate unit (SPEC.md §6.4 "Rent module"). No pricing source: the
user entered the figures, so `price.kind = "user_quote"`.

The persona already pays rent as a recurring item in the Profile. The projection engine cannot
remove a profile item, so each unit's Commitment carries the *change* in monthly housing cost
(new rent + utilities - current rent) from the lease start, plus the deposit upfront. That way
the baseline is "stay put" and each option is "move to this unit".
"""
from __future__ import annotations

from datetime import date

from ...models import Commitment, Option, PriceEstimate, Profile
from .inputs import RentInputs, RentUnit


def option_id(n: int) -> str:
    return f"unit_{n}"


def current_rent_cents(inputs: RentInputs, profile: Profile) -> int:
    """Current monthly rent: the user's figure, else the largest recurring item labelled rent, else 0."""
    if inputs.current_rent_cents is not None:
        return inputs.current_rent_cents
    rent = [r for r in profile.recurring if "rent" in r.label.lower()]
    return abs(min((r.amount_cents for r in rent), default=0))


def monthly_housing_cents(u: RentUnit) -> int:
    return u.rent_cents + u.utilities_est_cents


def _commitment(oid: str, u: RentUnit, current_rent: int) -> Commitment:
    return Commitment(
        id=f"cmt_{oid}",
        label=f"Housing change ({u.label})",
        upfront_cents=u.deposit_cents,
        recurring_cents=-(monthly_housing_cents(u) - current_rent),  # negative when the move costs more
        cadence="monthly",
        start_date=u.start_date,
        term_months=u.lease_months,
        risk_exposure_cents=0,
    )


def build_options(inputs: RentInputs, profile: Profile) -> list[Option]:
    current = current_rent_cents(inputs, profile)
    out: list[Option] = []
    for n, u in enumerate(inputs.units, 1):
        oid = option_id(n)
        out.append(
            Option(
                id=oid,
                label=u.label,
                attributes={
                    "rent_cents": u.rent_cents,
                    "deposit_cents": u.deposit_cents,
                    "utilities_est_cents": u.utilities_est_cents,
                    "monthly_housing_cents": monthly_housing_cents(u),
                    "move_in_cents": u.deposit_cents + u.rent_cents,
                    "lease_months": u.lease_months,
                    "start_date": u.start_date.isoformat(),
                    "current_rent_cents": current,
                },
                commitment=_commitment(oid, u, current),
                price=PriceEstimate(
                    cents=monthly_housing_cents(u),
                    kind="user_quote",
                    source_url=None,
                    source_title="Rent plus your utilities estimate",
                    retrieved=profile.as_of,
                ),
            )
        )
    return out
