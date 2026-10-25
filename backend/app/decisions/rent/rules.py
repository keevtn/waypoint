"""Rent constraints (SPEC.md §6.4 "Rent module"). Every rule cites a corpus chunk id.

- `flag` when rent > 30% of monthly income (HUD 30 percent standard).
- `disallowed` when rent + utilities > 45% of monthly income (between HUD's 30% cost-burden
  line and its 50% severe-burden line; the module's hard stop).
- `flag` when deposit + first month's rent > current balance - safety floor.
"""
from __future__ import annotations

from ...models import Constraint, Option, Profile
from ...profile.detect import monthly_equivalent
from ...rag import facts
from .inputs import RentInputs
from .options import monthly_housing_cents

RENT_SHARE_FLAG = 0.30
HOUSING_SHARE_DISALLOW = 0.45

RENT_30_PERCENT = [facts.RENT_30_PERCENT]
MOVE_IN_CASH = [facts.EMERGENCY_FUND, facts.RENT_30_PERCENT]


def monthly_income_cents(profile: Profile) -> int:
    return sum(monthly_equivalent(i.amount_cents, i.cadence) for i in profile.income)


def build_constraints(inputs: RentInputs, profile: Profile, options: list[Option]) -> list[Constraint]:
    income = monthly_income_cents(profile)
    units = {o.id: u for o, u in zip(options, inputs.units)}
    out: list[Constraint] = []

    over_45 = [o.id for o in options if income <= 0 or monthly_housing_cents(units[o.id]) > income * HOUSING_SHARE_DISALLOW]
    if over_45:
        out.append(
            Constraint(
                id="c_housing_45pct",
                kind="disallowed",
                applies_to=over_45,
                rule="Rent plus utilities would take more than 45% of your monthly income, well past the 30 percent standard for affordable housing and close to the level HUD calls a severe cost burden.",
                citation_ids=RENT_30_PERCENT,
            )
        )

    over_30 = [o.id for o in options if o.id not in over_45 and units[o.id].rent_cents > income * RENT_SHARE_FLAG]
    if over_30:
        out.append(
            Constraint(
                id="c_rent_30pct",
                kind="flag",
                applies_to=over_30,
                rule="Rent alone would take more than 30% of your monthly income, the standard above which housing is considered a cost burden.",
                citation_ids=RENT_30_PERCENT,
            )
        )

    out.append(
        Constraint(
            id="c_rent_30pct_standard",
            kind="required",
            applies_to=[o.id for o in options],
            rule="Housing is generally considered affordable when rent and utilities together stay within 30 percent of income.",
            citation_ids=RENT_30_PERCENT,
        )
    )

    spare = profile.balance_cents - profile.safety_floor_cents
    cash_short = [o.id for o in options if units[o.id].deposit_cents + units[o.id].rent_cents > spare]
    if cash_short:
        out.append(
            Constraint(
                id="c_move_in_cash",
                kind="flag",
                applies_to=cash_short,
                rule="The deposit plus first month's rent is more than your current balance minus your safety floor, so signing would use up your cushion.",
                citation_ids=MOVE_IN_CASH,
            )
        )
    return out
