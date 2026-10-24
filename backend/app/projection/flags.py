"""Flag derivation (SPEC.md §6.3 "Flags"). Every number here is computed; the
`detail` dicts are what the explainer is allowed to quote.

Codes
- below_floor (warn): month min < safety floor. detail.contributors = outflow
  events in the CONTRIBUTOR_WINDOW_DAYS up to the min date, plus the variable
  drip over that window, so "why is this month tight" can be answered.
- negative (danger): month min < 0 (also listed as below_floor).
- low_slack (warn): monthly slack after the commitment < LOW_SLACK_CENTS.
- deductible_ok / deductible_unaffordable: for each commitment with
  risk_exposure_cents > 0, re-run with a one-off of -risk_exposure on the first
  day of plan month DEDUCTIBLE_CLAIM_MONTH (month 1 = the month containing
  `start`, so from late October the claim lands on December 1). Unaffordable
  when the stressed balance in that month falls below the safety floor.
- target_reached (info): first month whose end balance >= floor + TARGET_ABOVE_FLOOR_CENTS.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..models import Commitment, Flag, OneOff, Profile, ProjectionResult
from ..profile.detect import add_months
from . import engine

CONTRIBUTOR_WINDOW_DAYS = 7
MAX_CONTRIBUTORS = 6
LOW_SLACK_CENTS = 15000
DEDUCTIBLE_CLAIM_MONTH = 3
TARGET_ABOVE_FLOOR_CENTS = 100000


def deductible_claim_date(start: date) -> date:
    return add_months(engine.first_of_month(start), DEDUCTIBLE_CLAIM_MONTH - 1)


def contributors(w: engine.Walk, min_date: date) -> list[dict]:
    lo = min_date - timedelta(days=CONTRIBUTOR_WINDOW_DAYS - 1)
    outs = [e for e in w.events if e.amount_cents < 0 and lo <= e.date <= min_date]
    outs.sort(key=lambda e: e.amount_cents)
    items = [
        {"id": e.source_id, "label": e.label, "amount_cents": e.amount_cents, "date": e.date.isoformat(), "kind": e.kind}
        for e in outs[:MAX_CONTRIBUTORS]
    ]
    drip = sum(v for d, v in w.drip_by_day.items() if lo <= d <= min_date)
    if drip:
        items.append(
            {
                "id": "variable",
                "label": "Variable spending",
                "amount_cents": -drip,
                "date": min_date.isoformat(),
                "kind": "variable",
                "window_days": CONTRIBUTOR_WINDOW_DAYS,
            }
        )
    return items


def derive(
    profile: Profile,
    commitments: list[Commitment],
    w: engine.Walk,
    res: ProjectionResult,
    *,
    start: date | None = None,
    one_off_overrides: list[OneOff] | None = None,
    income_multiplier: list[float] | None = None,
) -> list[Flag]:
    floor = profile.safety_floor_cents
    out: list[Flag] = []

    for p in res.series:
        if p.min_balance_cents < floor:
            contrib = contributors(w, p.min_balance_date)
            base = {
                "min_balance_cents": p.min_balance_cents,
                "min_balance_date": p.min_balance_date.isoformat(),
                "floor_cents": floor,
                "shortfall_cents": floor - p.min_balance_cents,
                "contributors": contrib,
            }
            out.append(Flag(id=f"flag_below_floor_{p.month}", severity="warn", month=p.month, code="below_floor", detail=base))
            if p.min_balance_cents < 0:
                out.append(Flag(id=f"flag_negative_{p.month}", severity="danger", month=p.month, code="negative", detail=base))

    if commitments and res.monthly_slack_cents < LOW_SLACK_CENTS:
        out.append(
            Flag(
                id="flag_low_slack",
                severity="warn",
                month=None,
                code="low_slack",
                detail={
                    "monthly_slack_cents": res.monthly_slack_cents,
                    "threshold_cents": LOW_SLACK_CENTS,
                    "baseline_slack_cents": profile.monthly_slack_cents,
                    "commitment_ids": [c.id for c in commitments],
                },
            )
        )

    claim_date = deductible_claim_date(w.start)
    claim_month = engine.month_key(claim_date)
    for c in commitments:
        if c.risk_exposure_cents <= 0 or claim_date > w.end:
            continue
        claim = OneOff(
            id=f"stress_deductible_{c.id}",
            label=f"Deductible claim ({c.label})",
            amount_cents=-abs(c.risk_exposure_cents),
            date=claim_date,
            source="module",
        )
        stressed = engine.project(
            profile,
            commitments,
            len(w.months),
            start,
            [*(one_off_overrides or []), claim],
            income_multiplier,
            option_id=res.option_id,
            derive_flags=False,
        )
        s_month = next(p for p in stressed.series if p.month == claim_month)
        b_month = next(p for p in res.series if p.month == claim_month)
        ok = s_month.min_balance_cents >= floor
        out.append(
            Flag(
                id=f"flag_deductible_{c.id}",
                severity="info" if ok else "danger",
                month=claim_month,
                code="deductible_ok" if ok else "deductible_unaffordable",
                detail={
                    "commitment_id": c.id,
                    "deductible_cents": abs(c.risk_exposure_cents),
                    "claim_date": claim_date.isoformat(),
                    "floor_cents": floor,
                    "min_balance_cents": s_month.min_balance_cents,
                    "min_balance_date": s_month.min_balance_date.isoformat(),
                    "unstressed_min_balance_cents": b_month.min_balance_cents,
                    "stressed_overall_min_balance_cents": stressed.min_balance_cents,
                    "months_below_floor": stressed.months_below_floor,
                    "months_negative": stressed.months_negative,
                },
            )
        )

    for p in res.series:
        if p.end_balance_cents >= floor + TARGET_ABOVE_FLOOR_CENTS:
            out.append(
                Flag(
                    id="flag_target_reached",
                    severity="info",
                    month=p.month,
                    code="target_reached",
                    detail={"end_balance_cents": p.end_balance_cents, "target_cents": floor + TARGET_ABOVE_FLOOR_CENTS, "floor_cents": floor},
                )
            )
            break
    return out
