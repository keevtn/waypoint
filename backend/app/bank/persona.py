"""Seed persona (SPEC.md §8): the single source of truth for local mode and the
Plaid sandbox custom user.

`generate(as_of)` returns the local JSON document; `to_plaid_custom_user(doc)`
converts it to Plaid's custom-user config (SPEC.md §6.1, verified against
https://plaid.com/docs/sandbox/user-custom/ on 2026-10-24: `override_accounts[]`
with `type`, `subtype`, `starting_balance`, `meta`, `transactions[]`; each
transaction has `date_transacted`, `date_posted`, `amount`, `description`,
`currency`; Plaid's sign convention is positive = money leaving the account).

All dates are relative to `as_of` so the history is always "the last ~4 months".
Amounts are the tuning knobs for the §8 demo outcomes; the generator is
deterministic (seeded) so repeated runs produce identical history.
"""
from __future__ import annotations

import random
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

PERSONA_ID = "persona_student"
SAFETY_FLOOR_CENTS = 20000

# --- tuning knobs (amounts only; see SPEC.md §8 "tune the persona") -----------
BALANCE_CENTS = 184000  # current balance as of today (tuned from §8's $1,240; see docs/STATUS.md)
PAYROLL_CENTS = 70000  # biweekly, Fridays
FAMILY_CENTS = 30000  # 1st of month
RENT_CENTS = 85000  # 1st
PHONE_CENTS = 4500  # 12th
GYM_CENTS = 2499  # 5th
MUSIC_CENTS = 599  # 18th
DOWN_PAYMENT_CENTS = 80000  # ~7 days ago
PAST_TUITION_CENTS = 150000  # ~70 days ago
TUITION_CENTS = 150000  # next Jan 15 (tuned from §8's $1,250)
TEXTBOOKS_CENTS = 22000  # next Jan 20
REGISTRATION_CENTS = 18000  # as_of + 12 days
# Variable spend per full history month, oldest -> newest. mean 260 (tuned from §8's ~290), pop. std ~67.
VARIABLE_MONTH_TOTALS_CENTS = [17000, 23000, 29000, 35000]
VARIABLE_TXNS_PER_MONTH = 15
HISTORY_FULL_MONTHS = 4

# Moment inputs for the demo (AutoInsuranceInputs, SPEC.md §6.4 / §8).
MOMENT_AUTO_INSURANCE = {
    "state": "PA",
    "vehicle_value_cents": 950000,
    "financed": True,
    "loan_payment_cents": 21200,
    "loan_term_months": 48,
    "driver_age": 21,
    "deductible_comfort_cents": 60000,
    # registration_deadline is filled in by generate(): as_of + 30 days
}

VARIABLE_MERCHANTS = [
    ("GIANT FOOD #6421", "groceries"),
    ("SHEETZ 0319", "gas"),
    ("CHIPOTLE 2210", "dining"),
    ("AMAZON.COM*2K4PL", "shopping"),
    ("UBER *TRIP", "transport"),
    ("TARGET T-2855", "shopping"),
    ("MCLANAHANS DOWNTOWN", "groceries"),
]


@dataclass(frozen=True)
class _Recurring:
    raw_name: str
    cents: int  # signed, our convention (+ inflow, - outflow)
    day: int
    category: str


RECURRING_MONTHLY = [
    _Recurring("ZELLE FROM MOM", FAMILY_CENTS, 1, "income"),
    _Recurring("RENT - THE META", -RENT_CENTS, 1, "housing"),
    _Recurring("PLANET FITNESS", -GYM_CENTS, 5, "subscriptions"),
    _Recurring("VERIZON WIRELESS", -PHONE_CENTS, 12, "utilities"),
    _Recurring("SPOTIFY", -MUSIC_CENTS, 18, "subscriptions"),
]


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def _most_recent_friday_before(d: date) -> date:
    """Most recent Friday strictly before `d` ("last one yesterday-ish")."""
    x = d - timedelta(days=1)
    while x.weekday() != 4:
        x -= timedelta(days=1)
    return x


def _next_month_day(as_of: date, month: int, day: int) -> date:
    """First occurrence of month/day strictly after as_of."""
    cand = date(as_of.year, month, day)
    if cand <= as_of:
        cand = date(as_of.year + 1, month, day)
    return cand


def history_start(as_of: date) -> date:
    """First day of the month HISTORY_FULL_MONTHS full months before as_of's month."""
    return add_months(date(as_of.year, as_of.month, 1), -HISTORY_FULL_MONTHS)


def _split_total(total: int, n: int, lo: int, hi: int, rng: random.Random) -> list[int]:
    """Split `total` cents into n amounts roughly in [lo, hi], summing exactly to total."""
    raw = [rng.uniform(lo, hi) for _ in range(n)]
    scale = total / sum(raw)
    amounts = [max(lo // 2, int(round(a * scale))) for a in raw]
    amounts[-1] += total - sum(amounts)
    return amounts


def generate(as_of: date | None = None) -> dict[str, Any]:
    """Build the persona document (local JSON shape). Pure and deterministic."""
    as_of = as_of or date.today()
    rng = random.Random(f"{PERSONA_ID}:{as_of.isoformat()}")
    start = history_start(as_of)
    txns: list[dict[str, Any]] = []

    def add(d: date, cents: int, raw_name: str, category: str | None) -> None:
        if start <= d <= as_of:
            txns.append({"date": d, "amount_cents": cents, "raw_name": raw_name, "category": category})

    # Biweekly payroll on Fridays, walking back from the most recent Friday.
    pay = _most_recent_friday_before(as_of)
    while pay >= start:
        add(pay, PAYROLL_CENTS, "PENN STATE PAYROLL", "income")
        pay -= timedelta(days=14)

    # Monthly items on fixed days.
    for r in RECURRING_MONTHLY:
        for k in range(HISTORY_FULL_MONTHS + 1):
            m = add_months(start, k)
            add(date(m.year, m.month, min(r.day, monthrange(m.year, m.month)[1])), r.cents, r.raw_name, r.category)

    # Past one-offs.
    add(as_of - timedelta(days=7), -DOWN_PAYMENT_CENTS, "CARMAX DOWN PAYMENT", "auto")
    add(as_of - timedelta(days=70), -PAST_TUITION_CENTS, "PENN STATE BURSAR", "education")

    # Variable spend: full months get their configured total; the current partial month is pro-rated.
    for k in range(HISTORY_FULL_MONTHS + 1):
        m = add_months(start, k)
        days = monthrange(m.year, m.month)[1]
        if k < HISTORY_FULL_MONTHS:
            total = VARIABLE_MONTH_TOTALS_CENTS[k % len(VARIABLE_MONTH_TOTALS_CENTS)]
            n = VARIABLE_TXNS_PER_MONTH
            last_day = days
        else:
            last_day = as_of.day
            mean = sum(VARIABLE_MONTH_TOTALS_CENTS) // len(VARIABLE_MONTH_TOTALS_CENTS)
            total = mean * last_day // days
            n = max(1, VARIABLE_TXNS_PER_MONTH * last_day // days)
        for a in _split_total(total, n, 600, 6000, rng):
            raw, cat = rng.choice(VARIABLE_MERCHANTS)
            add(date(m.year, m.month, rng.randint(1, last_day)), -a, raw, cat)

    txns.sort(key=lambda t: (t["date"], t["raw_name"]))
    for i, t in enumerate(txns, 1):
        t["id"] = f"txn_{i:04d}"
        t["date"] = t["date"].isoformat()

    future_one_offs = [
        {
            "id": "oo_registration",
            "label": "Vehicle registration/title",
            "amount_cents": -REGISTRATION_CENTS,
            "date": (as_of + timedelta(days=12)).isoformat(),
            "source": "user",
        },
        {
            "id": "oo_tuition",
            "label": "Tuition installment",
            "amount_cents": -TUITION_CENTS,
            "date": _next_month_day(as_of, 1, 15).isoformat(),
            "source": "user",
        },
        {
            "id": "oo_textbooks",
            "label": "Textbooks",
            "amount_cents": -TEXTBOOKS_CENTS,
            "date": _next_month_day(as_of, 1, 20).isoformat(),
            "source": "user",
        },
    ]

    # Declared streams: the DATA_MODE=plaid fallback when detection finds <2 items (SPEC.md §6.2).
    declared_income = [
        {"raw_name": "PENN STATE PAYROLL", "amount_cents": PAYROLL_CENTS, "cadence": "biweekly"},
        {"raw_name": "ZELLE FROM MOM", "amount_cents": FAMILY_CENTS, "cadence": "monthly"},
    ]
    declared_recurring = [
        {"raw_name": r.raw_name, "amount_cents": r.cents, "cadence": "monthly", "day": r.day, "category": r.category}
        for r in RECURRING_MONTHLY
        if r.cents < 0
    ]

    return {
        "persona_id": PERSONA_ID,
        "as_of": as_of.isoformat(),
        "balance_cents": BALANCE_CENTS,
        "safety_floor_cents": SAFETY_FLOOR_CENTS,
        "account": {"name": "Student Checking", "mask": "4321", "currency": "USD"},
        "transactions": txns,
        "future_one_offs": future_one_offs,
        "declared_income": declared_income,
        "declared_recurring": declared_recurring,
        "moment": {
            "auto_insurance": {
                **MOMENT_AUTO_INSURANCE,
                "registration_deadline": (as_of + timedelta(days=30)).isoformat(),
            }
        },
    }


def to_plaid_custom_user(doc: dict[str, Any]) -> dict[str, Any]:
    """Plaid sandbox custom-user config (override_password JSON). Sign flipped: Plaid + = outflow."""
    acct = doc["account"]
    return {
        "version": 2,
        "override_accounts": [
            {
                "type": "depository",
                "subtype": "checking",
                "starting_balance": doc["balance_cents"] / 100,
                "currency": acct["currency"],
                "meta": {"name": "Checking", "official_name": acct["name"], "mask": acct["mask"]},
                "transactions": [
                    {
                        "date_transacted": t["date"],
                        "date_posted": t["date"],
                        "amount": -t["amount_cents"] / 100,
                        "description": t["raw_name"],
                        "currency": acct["currency"],
                    }
                    for t in doc["transactions"]
                ],
            }
        ],
    }
