"""Big-purchase options: pay cash now, or finance over 6 / 12 / 24 months (plus the user's own
term when it differs). Standard amortization; `apr_bps = 0` allowed. Without a lender's rate
the plans use a conservative placeholder APR and are labelled as estimates (SPEC §3.6)."""
from __future__ import annotations

from datetime import date

from ...models import Commitment, Option, PriceEstimate, Profile
from .inputs import BigPurchaseInputs, Financing

ASSUMED_APR_BPS = 2499
ASSUMED_APR_TITLE = "Assumed APR; enter your lender's rate"
STANDARD_TERMS = (6, 12, 24)
CASH_ID = "cash_now"


def financed_id(term_months: int) -> str:
    return f"financed_{term_months}"


def monthly_payment_cents(principal_cents: int, apr_bps: int, term_months: int) -> int:
    """Standard amortized payment, rounded to the cent. 0% APR divides evenly (rounded up)."""
    if principal_cents <= 0 or term_months <= 0:
        return 0
    if apr_bps == 0:
        return -(-principal_cents // term_months)
    r = apr_bps / 10000 / 12
    return int(round(principal_cents * r / (1 - (1 + r) ** -term_months)))


def plan_figures(amount_cents: int, apr_bps: int, term_months: int, down_payment_cents: int) -> dict[str, int]:
    down = min(down_payment_cents, amount_cents)
    payment = monthly_payment_cents(amount_cents - down, apr_bps, term_months)
    total = down + payment * term_months
    return {
        "term_months": term_months,
        "apr_bps": apr_bps,
        "down_payment_cents": down,
        "monthly_payment_cents": payment,
        "total_cost_cents": total,
        "interest_cents": total - amount_cents,
    }


def cash_option(inputs: BigPurchaseInputs, on: date, as_of: date) -> Option:
    return Option(
        id=CASH_ID,
        label="Pay in cash",
        attributes={
            "term_months": 0,
            "apr_bps": 0,
            "down_payment_cents": inputs.amount_cents,
            "monthly_payment_cents": 0,
            "total_cost_cents": inputs.amount_cents,
            "interest_cents": 0,
            "date": on.isoformat(),
        },
        commitment=Commitment(
            id=f"cmt_{CASH_ID}",
            label=f"{inputs.name} (paid in cash)",
            upfront_cents=-inputs.amount_cents,
            recurring_cents=0,
            cadence="monthly",
            start_date=on,
            term_months=None,
            risk_exposure_cents=0,
        ),
        price=PriceEstimate(cents=inputs.amount_cents, kind="user_quote", source_url=None, source_title="Your purchase price", retrieved=as_of),
    )


def financed_option(inputs: BigPurchaseInputs, fin: Financing, on: date, as_of: date, *, assumed: bool) -> Option:
    f = plan_figures(inputs.amount_cents, fin.apr_bps, fin.term_months, fin.down_payment_cents)
    oid = financed_id(fin.term_months)
    return Option(
        id=oid,
        label=f"Finance over {fin.term_months} months",
        attributes={**f, "date": on.isoformat(), "apr_assumed": assumed},
        commitment=Commitment(
            id=f"cmt_{oid}",
            label=f"{inputs.name} payment ({fin.term_months} months)",
            upfront_cents=-f["down_payment_cents"],
            recurring_cents=-f["monthly_payment_cents"],
            cadence="monthly",
            start_date=on,
            term_months=fin.term_months,
            risk_exposure_cents=0,
        ),
        price=PriceEstimate(
            cents=f["monthly_payment_cents"],
            kind="estimate" if assumed else "user_quote",
            source_url=None,
            source_title=ASSUMED_APR_TITLE if assumed else "Your lender's terms",
            retrieved=as_of,
        ),
    )


def financing_terms(inputs: BigPurchaseInputs) -> list[tuple[Financing, bool]]:
    """(Financing, apr_assumed) per financed option: the standard terms, plus the user's own term
    when it is not one of them, all at the user's APR and down payment when given."""
    user = inputs.financing
    apr = user.apr_bps if user else ASSUMED_APR_BPS
    down = user.down_payment_cents if user else 0
    terms = list(STANDARD_TERMS)
    if user and user.term_months not in terms:
        terms = sorted([*terms, user.term_months])
    return [(Financing(apr_bps=apr, term_months=t, down_payment_cents=down), user is None) for t in terms]


def build_options(inputs: BigPurchaseInputs, profile: Profile) -> list[Option]:
    out = [cash_option(inputs, inputs.date, profile.as_of)]
    for fin, assumed in financing_terms(inputs):
        out.append(financed_option(inputs, fin, inputs.date, profile.as_of, assumed=assumed))
    return out
