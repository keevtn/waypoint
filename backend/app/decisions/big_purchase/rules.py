"""Big-purchase constraints. Nothing is disallowed: buying something is the user's call.

- `flag` when monthly slack after the option falls below LOW_SLACK_CENTS ($150).
- `flag` on every financed option stating its interest cost and total.
No corpus chunk covers these arithmetic facts, so `citation_ids = []` (the figures are the
module's own computation, not a factual claim about law or lenders)."""
from __future__ import annotations

from ...models import Constraint, Option, Profile
from ...profile.detect import monthly_equivalent
from .inputs import BigPurchaseInputs

LOW_SLACK_CENTS = 15000


def dollars(cents: int) -> str:
    return f"${abs(int(cents)) // 100:,}"


def pct(bps: int) -> str:
    return f"{bps / 100:.2f}%".replace(".00%", "%")


def slack_after(profile: Profile, o: Option) -> int:
    return profile.monthly_slack_cents + monthly_equivalent(o.commitment.recurring_cents, o.commitment.cadence)


def build_constraints(inputs: BigPurchaseInputs, profile: Profile, options: list[Option]) -> list[Constraint]:
    out: list[Constraint] = []

    low = [o.id for o in options if slack_after(profile, o) < LOW_SLACK_CENTS]
    if low:
        out.append(
            Constraint(
                id="c_low_slack",
                kind="flag",
                applies_to=low,
                rule=f"After this payment your monthly slack (income minus bills and typical spending) would be under {dollars(LOW_SLACK_CENTS)}.",
                citation_ids=[],
            )
        )

    for o in options:
        a = o.attributes
        if int(a.get("term_months") or 0) <= 0:
            continue
        assumed = " (an assumed rate; enter your lender's APR to replace it)" if a.get("apr_assumed") else ""
        out.append(
            Constraint(
                id=f"c_interest_{o.id}",
                kind="flag",
                applies_to=[o.id],
                rule=(
                    f"Financing over {a['term_months']} months at {pct(int(a['apr_bps']))} APR{assumed} adds "
                    f"{dollars(int(a['interest_cents']))} of interest, for a total cost of {dollars(int(a['total_cost_cents']))} "
                    f"versus {dollars(inputs.amount_cents)} in cash."
                ),
                citation_ids=[],
            )
        )
    return out
