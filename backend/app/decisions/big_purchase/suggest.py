"""Code-generated alternatives when paying cash on the chosen date breaks the safety floor.

Pure functions over the projection engine; the LLM never sees these until they exist and
may only restate their `*_display` values. Guardrails (`_safe`): an actionable suggestion
never projects a minimum below the floor, and a patch never changes `name` or raises
`amount_cents`.

- earliest_safe_date: step the purchase date forward one day at a time to the end of the
  12-month horizon; the first date where the cash plan stays at or above the floor in every
  month wins (`patch = {"date": iso}`). If no date qualifies, `wait_beyond_horizon` reports the
  best case: `cash_gap_cents` = floor - the highest minimum any date in the horizon achieves.
- safest_financing: scan term in {3, 6, 12, 24} x down payment in {0%, 25%, 50%} of the price
  (the user's APR when given, else the assumed APR); keep plans whose minimum stays at or above
  the floor with non-negative slack; return the cheapest total (`patch = {"financing": {...}}`).
"""
from __future__ import annotations

from datetime import date, timedelta

from ...models import Profile, ProjectionResult, Suggestion
from ...projection import project
from ...projection.engine import horizon_months, last_of_month
from .inputs import BigPurchaseInputs, Financing
from .options import ASSUMED_APR_BPS, CASH_ID, cash_option, financed_option
from .rules import dollars, pct

SCAN_TERMS = (3, 6, 12, 24)
SCAN_DOWN_PCTS = (0, 25, 50)
HORIZON_MONTHS = 12


def horizon_end(profile: Profile) -> date:
    return last_of_month(date.fromisoformat(horizon_months(profile.as_of, HORIZON_MONTHS)[-1] + "-01"))


def _projected(r: ProjectionResult, option_id: str, total_cost_cents: int) -> dict:
    return {
        "option_id": option_id,
        "min_balance_cents": r.min_balance_cents,
        "min_balance_date": r.min_balance_date.isoformat(),
        "months_below_floor": list(r.months_below_floor),
        "monthly_slack_cents": r.monthly_slack_cents,
        "total_cost_cents": total_cost_cents,
    }


def _cash_result(inputs: BigPurchaseInputs, profile: Profile, on: date) -> ProjectionResult:
    return project(profile, [cash_option(inputs, on, profile.as_of).commitment], option_id=CASH_ID, derive_flags=False)


def _safe_for(r: ProjectionResult, profile: Profile) -> bool:
    return r.min_balance_cents >= profile.safety_floor_cents and not r.months_below_floor and not r.months_negative


def needs_suggestions(cash: ProjectionResult) -> bool:
    return bool(cash.months_below_floor or cash.months_negative)


def earliest_safe_date(inputs: BigPurchaseInputs, profile: Profile) -> Suggestion:
    floor = profile.safety_floor_cents
    end = horizon_end(profile)
    d = inputs.date
    best: tuple[date, ProjectionResult] | None = None
    while d <= end:
        r = _cash_result(inputs, profile, d)
        if _safe_for(r, profile):
            return Suggestion(
                id="s_earliest_safe_date",
                type="earliest_safe_date",
                label=f"Wait until {d.isoformat()} to pay cash",
                rationale=(
                    f"Paying {dollars(inputs.amount_cents)} in cash on {d.isoformat()} keeps every month at or above your "
                    f"{dollars(floor)} floor (lowest point {dollars(r.min_balance_cents)} on {r.min_balance_date.isoformat()}); "
                    f"paying on {inputs.date.isoformat()} does not."
                ),
                patch={"date": d.isoformat()},
                projected=_projected(r, CASH_ID, inputs.amount_cents),
            )
        if best is None or r.min_balance_cents > best[1].min_balance_cents:
            best = (d, r)
        d += timedelta(days=1)
    assert best is not None
    d, r = best
    gap = floor - r.min_balance_cents
    return Suggestion(
        id="s_wait_beyond_horizon",
        type="wait_beyond_horizon",
        label="No date in the next 12 months works for paying cash",
        rationale=(
            f"Even on the best date in the next 12 months ({d.isoformat()}), paying {dollars(inputs.amount_cents)} in cash "
            f"drops your balance {dollars(gap)} below your {dollars(floor)} floor. You would need about {dollars(gap)} more saved first."
        ),
        patch={},
        projected={**_projected(r, CASH_ID, inputs.amount_cents), "cash_gap_cents": gap},
    )


def safest_financing(inputs: BigPurchaseInputs, profile: Profile) -> Suggestion | None:
    floor = profile.safety_floor_cents
    apr = inputs.financing.apr_bps if inputs.financing else ASSUMED_APR_BPS
    assumed = inputs.financing is None
    best: tuple[int, Financing, ProjectionResult, str] | None = None
    for term in SCAN_TERMS:
        for p in SCAN_DOWN_PCTS:
            fin = Financing(apr_bps=apr, term_months=term, down_payment_cents=inputs.amount_cents * p // 100)
            o = financed_option(inputs, fin, inputs.date, profile.as_of, assumed=assumed)
            r = project(profile, [o.commitment], option_id=o.id, derive_flags=False)
            if not _safe_for(r, profile) or r.monthly_slack_cents < 0:
                continue
            total = int(o.attributes["total_cost_cents"])
            if best is None or total < best[0]:
                best = (total, fin, r, o.id)
    if best is None:
        return None
    total, fin, r, oid = best
    rate = f"{pct(apr)} APR" + (" (assumed; enter your lender's rate)" if assumed else "")
    return Suggestion(
        id="s_safest_financing",
        type="safest_financing",
        label=f"Finance over {fin.term_months} months with {dollars(fin.down_payment_cents)} down",
        rationale=(
            f"Of the financing plans that keep every month at or above your {dollars(floor)} floor, this one costs the least: "
            f"{dollars(total)} in total at {rate}, {dollars(total - inputs.amount_cents)} of it interest, "
            f"with {dollars(r.monthly_slack_cents)} of monthly slack left."
        ),
        patch={"financing": {"apr_bps": fin.apr_bps, "term_months": fin.term_months, "down_payment_cents": fin.down_payment_cents}},
        projected=_projected(r, oid, total),
    )


def _safe(s: Suggestion, inputs: BigPurchaseInputs, profile: Profile) -> bool:
    """Code guardrails: actionable suggestions never sit below the floor; patches never rename or raise the price."""
    if "name" in s.patch:
        return False
    if int(s.patch.get("amount_cents", inputs.amount_cents)) > inputs.amount_cents:
        return False
    if s.type == "wait_beyond_horizon":
        return not s.patch
    return int(s.projected["min_balance_cents"]) >= profile.safety_floor_cents and not s.projected["months_below_floor"]


def suggest(inputs: BigPurchaseInputs, profile: Profile, projections: dict[str, ProjectionResult]) -> list[Suggestion]:
    cash = projections.get(CASH_ID)
    if cash is None or not needs_suggestions(cash):
        return []
    out = [earliest_safe_date(inputs, profile)]
    fin = safest_financing(inputs, profile)
    if fin is not None:
        out.append(fin)
    return [s for s in out if _safe(s, inputs, profile)]
