"""Candidate coverage configurations (SPEC.md §6.4 "Options"). Ids are fixed; prices come from pricing.json."""
from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from ...models import Commitment, Option, PriceEstimate
from .inputs import AutoInsuranceInputs

PRICING_PATH = Path(__file__).with_name("pricing.json")

# Policy starts shortly after purchase so coverage is in force before the registration
# visit; the first premium is due then and monthly after. The loan's first payment is
# ~30 days after purchase (the persona bought the car ~7 days before as_of).
PREMIUM_START_OFFSET_DAYS = 10
LOAN_FIRST_PAYMENT_OFFSET_DAYS = 24

CONFIGS: list[dict[str, Any]] = [
    {
        "id": "pa_min_limited",
        "label": "State minimum, limited tort",
        "commitment_label": "Auto insurance premium (state minimum)",
        "attributes": {
            "bi_per_person": 15000,
            "bi_per_accident": 30000,
            "pd": 5000,
            "medical": 5000,
            "tort": "limited",
            "collision": False,
            "comprehensive": False,
            "deductible": 0,
        },
    },
    {
        "id": "std_limited_1000",
        "label": "Standard, $1,000 deductible, limited tort",
        "commitment_label": "Auto insurance premium (standard, $1,000 deductible)",
        "attributes": {
            "bi_per_person": 50000,
            "bi_per_accident": 100000,
            "pd": 25000,
            "medical": 5000,
            "tort": "limited",
            "collision": True,
            "comprehensive": True,
            "deductible": 1000,
        },
    },
    {
        "id": "std_full_500",
        "label": "Standard, $500 deductible, full tort",
        "commitment_label": "Auto insurance premium (standard, $500 deductible)",
        "attributes": {
            "bi_per_person": 100000,
            "bi_per_accident": 300000,
            "pd": 50000,
            "medical": 5000,
            "tort": "full",
            "collision": True,
            "comprehensive": True,
            "deductible": 500,
        },
    },
]


@lru_cache(maxsize=1)
def pricing() -> dict[str, Any]:
    with PRICING_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def price_for(option_id: str) -> PriceEstimate:
    p = pricing()
    entry = p["options"].get(option_id)
    if entry is None:  # unsourced: the UI shows a red "Unsourced" badge (SPEC §3.6)
        return PriceEstimate(cents=0, kind="estimate", source_url=None, source_title=None, retrieved=None)
    return PriceEstimate(
        cents=int(entry["cents"]),
        kind="estimate",
        source_url=entry.get("source_url") or p["default_source"]["source_url"],
        source_title=entry.get("source_title") or p["default_source"]["source_title"],
        retrieved=date.fromisoformat(entry.get("retrieved") or p["retrieved"]),
    )


def premium_start(as_of: date) -> date:
    return as_of + timedelta(days=PREMIUM_START_OFFSET_DAYS)


def _commitment(option_id: str, label: str, monthly_cents: int, deductible_dollars: int, as_of: date) -> Commitment:
    return Commitment(
        id=f"cmt_{option_id}",
        label=label,
        upfront_cents=0,
        recurring_cents=-abs(monthly_cents),
        cadence="monthly",
        start_date=premium_start(as_of),
        term_months=None,
        risk_exposure_cents=int(deductible_dollars) * 100,
    )


def build_options(inputs: AutoInsuranceInputs, as_of: date) -> list[Option]:
    out: list[Option] = []
    for cfg in CONFIGS:
        price = price_for(cfg["id"])
        out.append(
            Option(
                id=cfg["id"],
                label=cfg["label"],
                attributes=dict(cfg["attributes"]),
                commitment=_commitment(cfg["id"], cfg["commitment_label"], price.cents, cfg["attributes"]["deductible"], as_of),
                price=price,
            )
        )
    for n, q in enumerate(inputs.user_quotes, 1):
        oid = f"quote_{n}"
        attrs: dict[str, Any] = {
            "bi_per_person": 0,
            "bi_per_accident": 0,
            "pd": 0,
            "medical": 5000,
            "tort": "limited",
            "collision": False,
            "comprehensive": False,
            "deductible": 0,
            **q.attributes,
        }
        ded = int(attrs.get("deductible") or 0)
        out.append(
            Option(
                id=oid,
                label=q.label,
                attributes=attrs,
                commitment=_commitment(oid, f"Auto insurance premium ({q.label})", q.monthly_cents, ded, as_of),
                price=PriceEstimate(cents=q.monthly_cents, kind="user_quote", source_url=None, source_title="Your quote", retrieved=as_of),
            )
        )
    return out


def loan_commitment(inputs: AutoInsuranceInputs, as_of: date) -> Commitment | None:
    if not inputs.financed or not inputs.loan_payment_cents:
        return None
    return Commitment(
        id="cmt_car_loan",
        label="Car loan payment",
        upfront_cents=0,
        recurring_cents=-abs(inputs.loan_payment_cents),
        cadence="monthly",
        start_date=as_of + timedelta(days=LOAN_FIRST_PAYMENT_OFFSET_DAYS),
        term_months=inputs.loan_term_months,
        risk_exposure_cents=0,
    )
