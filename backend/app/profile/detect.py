"""Profile detection (SPEC.md §6.2): transactions + balance -> Profile.

Pure functions, no I/O. Thresholds are module constants so tests can reason
about them.

Recurring rule: a merchant group is recurring when it has >= MIN_OCCURRENCES,
its amounts are consistent (max abs deviation from the median <= max($5, 15% of
median)), and its median gap is within GAP_TOLERANCE_DAYS of 7/14/15/30.
Cadence comes from the gap; `next_date` = last date + cadence; `confidence` =
fraction of gaps within tolerance.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median, pstdev
from typing import Any

from ..models import Cadence, IncomeStream, OneOff, Profile, RecurringItem, Transaction, VariableSpend
from .normalize import normalize_merchant, slug

MIN_OCCURRENCES = 3
GAP_TOLERANCE_DAYS = 3
AMOUNT_TOLERANCE_MIN_CENTS = 500
AMOUNT_TOLERANCE_PCT = 0.15
INCOME_MIN_CENTS = 10000
ONE_OFF_MIN_CENTS = 40000
HISTORY_FULL_MONTHS = 4  # observation window: this many full calendar months + the current partial month

CADENCE_DAYS: dict[Cadence, int] = {"weekly": 7, "biweekly": 14, "semimonthly": 15, "monthly": 30}
MONTHLY_FACTOR: dict[Cadence, float] = {
    "weekly": 52 / 12,
    "biweekly": 26 / 12,
    "semimonthly": 2.0,
    "monthly": 1.0,
    "once": 0.0,
}


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def advance(d: date, cadence: Cadence) -> date:
    """Next occurrence after `d` for a cadence."""
    if cadence == "monthly":
        return add_months(d, 1)
    if cadence == "semimonthly":
        # 1st/15th style: alternate halves of the month.
        if d.day < 15:
            return date(d.year, d.month, min(d.day + 15, monthrange(d.year, d.month)[1]))
        nxt = add_months(date(d.year, d.month, 1), 1)
        return date(nxt.year, nxt.month, max(1, d.day - 15))
    if cadence == "once":
        return d
    return d + timedelta(days=CADENCE_DAYS[cadence])


def monthly_equivalent(amount_cents: int, cadence: Cadence) -> int:
    return int(round(amount_cents * MONTHLY_FACTOR[cadence]))


@dataclass
class _Group:
    key: str
    label: str
    category: str | None
    txns: list[Transaction]


@dataclass
class _Detected:
    cadence: Cadence
    amount_cents: int
    next_date: date
    confidence: float


def _classify_gap(gap_days: float) -> Cadence | None:
    best: Cadence | None = None
    best_err = GAP_TOLERANCE_DAYS + 1
    for cadence, days in CADENCE_DAYS.items():
        err = abs(gap_days - days)
        if err <= GAP_TOLERANCE_DAYS and err < best_err:
            best, best_err = cadence, err
    return best


def _detect_group(txns: list[Transaction]) -> _Detected | None:
    if len(txns) < MIN_OCCURRENCES:
        return None
    txns = sorted(txns, key=lambda t: t.date)
    amounts = [abs(t.amount_cents) for t in txns]
    med = median(amounts)
    tol = max(AMOUNT_TOLERANCE_MIN_CENTS, AMOUNT_TOLERANCE_PCT * med)
    if max(abs(a - med) for a in amounts) > tol:
        return None
    gaps = [(b.date - a.date).days for a, b in zip(txns, txns[1:])]
    cadence = _classify_gap(median(gaps))
    if cadence is None:
        return None
    target = CADENCE_DAYS[cadence]
    ok = sum(1 for g in gaps if abs(g - target) <= GAP_TOLERANCE_DAYS)
    sign = 1 if txns[0].amount_cents > 0 else -1
    return _Detected(
        cadence=cadence,
        amount_cents=sign * int(round(med)),
        next_date=advance(txns[-1].date, cadence),
        confidence=round(ok / len(gaps), 3),
    )


def _groups(txns: list[Transaction]) -> list[_Group]:
    by_key: dict[str, _Group] = {}
    for t in txns:
        nm = normalize_merchant(t.raw_name)
        g = by_key.get(nm.key)
        if g is None:
            g = by_key[nm.key] = _Group(nm.key, nm.label, nm.category or t.category, [])
        g.txns.append(t)
    return list(by_key.values())


def _roll_forward(next_date: date, cadence: Cadence, as_of: date) -> date:
    """Guarantee next_date > as_of (history may end before the last expected occurrence)."""
    guard = 0
    while next_date <= as_of and guard < 60:
        next_date = advance(next_date, cadence)
        guard += 1
    return next_date


def detect_income(txns: list[Transaction], as_of: date) -> list[IncomeStream]:
    out: list[IncomeStream] = []
    credits = [t for t in txns if t.amount_cents >= INCOME_MIN_CENTS]
    for g in _groups(credits):
        d = _detect_group(g.txns)
        if d is None:
            continue
        out.append(
            IncomeStream(
                id=f"inc_{slug(g.key)}",
                label=g.label,
                amount_cents=d.amount_cents,
                cadence=d.cadence,
                next_date=_roll_forward(d.next_date, d.cadence, as_of),
                confidence=d.confidence,
            )
        )
    out.sort(key=lambda i: -monthly_equivalent(i.amount_cents, i.cadence))
    return out


def detect_recurring(txns: list[Transaction], as_of: date) -> list[RecurringItem]:
    out: list[RecurringItem] = []
    debits = [t for t in txns if t.amount_cents < 0]
    for g in _groups(debits):
        d = _detect_group(g.txns)
        if d is None:
            continue
        out.append(
            RecurringItem(
                id=f"rec_{slug(g.key)}",
                label=g.label,
                amount_cents=d.amount_cents,
                cadence=d.cadence,
                next_date=_roll_forward(d.next_date, d.cadence, as_of),
                confidence=d.confidence,
                category=g.category,
            )
        )
    out.sort(key=lambda r: r.amount_cents)  # largest outflow first
    return out


def detect_one_offs(txns: list[Transaction], recurring_ids: set[str]) -> list[OneOff]:
    """Large past debits that are not recurring, surfaced for the user to confirm as future one-offs."""
    out: list[OneOff] = []
    for t in txns:
        if t.amount_cents > -ONE_OFF_MIN_CENTS:
            continue
        nm = normalize_merchant(t.raw_name)
        if f"rec_{slug(nm.key)}" in recurring_ids:
            continue
        out.append(OneOff(id=f"oo_detected_{t.id}", label=nm.label, amount_cents=t.amount_cents, date=t.date, source="detected"))
    return out


def window_start(as_of: date) -> date:
    return add_months(date(as_of.year, as_of.month, 1), -HISTORY_FULL_MONTHS)


def detect_variable(txns: list[Transaction], as_of: date, recurring_ids: set[str]) -> VariableSpend:
    """Debits not recurring and below the one-off threshold, summed per full calendar month
    inside the observation window (the current partial month is excluded)."""
    per_month: dict[str, int] = defaultdict(int)
    current = as_of.strftime("%Y-%m")
    start = window_start(as_of)
    for t in txns:
        if t.amount_cents >= 0 or t.amount_cents <= -ONE_OFF_MIN_CENTS:
            continue
        nm = normalize_merchant(t.raw_name)
        if f"rec_{slug(nm.key)}" in recurring_ids:
            continue
        ym = t.date.strftime("%Y-%m")
        if ym == current or t.date < start:
            continue
        per_month[ym] += -t.amount_cents
    if not per_month:
        return VariableSpend(mean_monthly_cents=0, std_monthly_cents=0, months_observed=0)
    vals = list(per_month.values())
    return VariableSpend(
        mean_monthly_cents=int(round(sum(vals) / len(vals))),
        std_monthly_cents=int(round(pstdev(vals))) if len(vals) > 1 else 0,
        months_observed=len(vals),
    )


def compute_slack(income: list[IncomeStream], recurring: list[RecurringItem], variable: VariableSpend) -> int:
    inc = sum(monthly_equivalent(i.amount_cents, i.cadence) for i in income)
    rec = sum(monthly_equivalent(-r.amount_cents, r.cadence) for r in recurring)
    return inc - rec - variable.mean_monthly_cents


def build_profile(
    txns: list[Transaction],
    balance_cents: int,
    as_of: date,
    *,
    user_one_offs: list[OneOff] | None = None,
    safety_floor_cents: int = 20000,
    declared_income: list[dict[str, Any]] | None = None,
    declared_recurring: list[dict[str, Any]] | None = None,
) -> Profile:
    """Full §6.2 pipeline. `declared_*` is the DATA_MODE=plaid fallback (merged in when detection finds < 2 recurring)."""
    start = window_start(as_of)
    txns = [t for t in txns if start <= t.date <= as_of]
    income = detect_income(txns, as_of)
    recurring = detect_recurring(txns, as_of)
    if len(recurring) < 2 and declared_recurring:
        recurring = _merge_declared_recurring(recurring, declared_recurring, as_of)
    if not income and declared_income:
        income = _merge_declared_income(income, declared_income, as_of)
    rec_ids = {r.id for r in recurring}
    detected = detect_one_offs(txns, rec_ids)
    variable = detect_variable(txns, as_of, rec_ids)
    one_offs = list(user_one_offs or []) + detected
    return Profile(
        as_of=as_of,
        balance_cents=balance_cents,
        income=income,
        recurring=recurring,
        one_offs=one_offs,
        variable=variable,
        safety_floor_cents=safety_floor_cents,
        monthly_slack_cents=compute_slack(income, recurring, variable),
    )


def _merge_declared_recurring(found: list[RecurringItem], declared: list[dict[str, Any]], as_of: date) -> list[RecurringItem]:
    out = list(found)
    have = {r.id for r in found}
    for d in declared:
        nm = normalize_merchant(d["raw_name"])
        rid = f"rec_{slug(nm.key)}"
        if rid in have:
            continue
        nxt = date(as_of.year, as_of.month, min(int(d.get("day", 1)), monthrange(as_of.year, as_of.month)[1]))
        nxt = _roll_forward(nxt, d.get("cadence", "monthly"), as_of)
        out.append(
            RecurringItem(
                id=rid,
                label=nm.label,
                amount_cents=int(d["amount_cents"]),
                cadence=d.get("cadence", "monthly"),
                next_date=nxt,
                confidence=0.5,
                category=nm.category or d.get("category"),
            )
        )
    return out


def _merge_declared_income(found: list[IncomeStream], declared: list[dict[str, Any]], as_of: date) -> list[IncomeStream]:
    out = list(found)
    have = {i.id for i in found}
    for d in declared:
        nm = normalize_merchant(d["raw_name"])
        iid = f"inc_{slug(nm.key)}"
        if iid in have:
            continue
        cadence: Cadence = d.get("cadence", "monthly")
        nxt = _roll_forward(as_of, cadence, as_of)
        out.append(IncomeStream(id=iid, label=nm.label, amount_cents=int(d["amount_cents"]), cadence=cadence, next_date=nxt, confidence=0.5))
    return out
