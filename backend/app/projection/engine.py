"""Deterministic 12-month projection (SPEC.md §6.3). Pure: no I/O, no randomness.

Semantics
- `start` (default `profile.as_of`) is the day the balance is known; the walk
  covers start+1 .. the last day of the `horizon_months`-th full calendar month
  after start's month. Only those full months become MonthPoints (the partial
  current month is simulated but not emitted), so a 12-month horizon from
  2026-10-24 yields 2026-11 .. 2027-10.
- Each day: outflow events, then inflow events, then the variable-spend drip.
  The month minimum considers the balance right after outflows (before that
  day's inflows) and at end of day, so "paid the same day as payday" is
  conservative.
- Variable spend drips `mean_monthly_cents / days_in_month` per day using
  cumulative rounding, so a month's drip sums exactly to the mean.
- `one_off_overrides`: extra OneOffs; one whose id matches a profile one-off
  replaces it. `income_multiplier[i]` scales income events in emitted month i
  (0 = first full month). Both exist so stress scenarios perturb inputs
  without special-casing the engine.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from ..models import Cadence, Commitment, MonthPoint, OneOff, Profile, ProjectionResult
from ..profile.detect import add_months, advance, monthly_equivalent

EventKind = Literal["income", "recurring", "one_off", "commitment", "stress"]


@dataclass(frozen=True)
class Event:
    date: date
    amount_cents: int  # + inflow, - outflow
    label: str
    source_id: str
    kind: EventKind


@dataclass
class Walk:
    """Full day-by-day trace; `flags.derive` reads it, callers normally only need `.result`."""

    start: date
    end: date
    months: list[str]
    events: list[Event]
    daily_end_balance: dict[date, int] = field(default_factory=dict)
    drip_by_day: dict[date, int] = field(default_factory=dict)
    series: list[MonthPoint] = field(default_factory=list)


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def first_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def last_of_month(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def horizon_months(start: date, n: int) -> list[str]:
    first = add_months(first_of_month(start), 1)
    return [month_key(add_months(first, i)) for i in range(n)]


def _series_dates(first: date, cadence: Cadence, lo: date, hi: date, max_count: int | None = None) -> list[date]:
    """Occurrences of a cadence starting at `first`, kept when lo < d <= hi."""
    out: list[date] = []
    d = first
    count = 0
    guard = 0
    while d <= hi and guard < 2000:
        if max_count is not None and count >= max_count:
            break
        if d > lo:
            out.append(d)
        count += 1
        if cadence == "once":
            break
        d = advance(d, cadence)
        guard += 1
    return out


def expand_events(
    profile: Profile,
    commitments: list[Commitment],
    start: date,
    end: date,
    one_off_overrides: list[OneOff] | None = None,
) -> list[Event]:
    events: list[Event] = []
    for inc in profile.income:
        for d in _series_dates(inc.next_date, inc.cadence, start, end):
            events.append(Event(d, inc.amount_cents, inc.label, inc.id, "income"))
    for rec in profile.recurring:
        for d in _series_dates(rec.next_date, rec.cadence, start, end):
            events.append(Event(d, rec.amount_cents, rec.label, rec.id, "recurring"))

    one_offs = {o.id: o for o in profile.one_offs}
    for o in one_off_overrides or []:
        one_offs[o.id] = o
    for o in one_offs.values():
        if start < o.date <= end:
            kind: EventKind = "stress" if o.source == "module" else "one_off"
            events.append(Event(o.date, o.amount_cents, o.label, o.id, kind))

    for c in commitments:
        if c.upfront_cents and start < c.start_date <= end:
            events.append(Event(c.start_date, -abs(c.upfront_cents), f"{c.label} (upfront)", c.id, "commitment"))
        if c.recurring_cents:
            hi = end
            max_count = None
            if c.term_months is not None:
                if c.cadence == "monthly":
                    max_count = c.term_months
                else:
                    hi = min(end, add_months(c.start_date, c.term_months) - timedelta(days=1))
            for d in _series_dates(c.start_date, c.cadence, start, hi, max_count):
                events.append(Event(d, c.recurring_cents, c.label, c.id, "commitment"))
    events.sort(key=lambda e: (e.date, e.amount_cents))
    return events


def _drip_for_day(d: date, mean_monthly_cents: int) -> int:
    days = monthrange(d.year, d.month)[1]
    return (mean_monthly_cents * d.day) // days - (mean_monthly_cents * (d.day - 1)) // days


def walk(
    profile: Profile,
    commitments: list[Commitment],
    horizon: int = 12,
    start: date | None = None,
    one_off_overrides: list[OneOff] | None = None,
    income_multiplier: list[float] | None = None,
) -> Walk:
    start = start or profile.as_of
    months = horizon_months(start, horizon)
    end = last_of_month(date.fromisoformat(months[-1] + "-01"))
    events = expand_events(profile, commitments, start, end, one_off_overrides)
    by_day: dict[date, list[Event]] = {}
    for e in events:
        by_day.setdefault(e.date, []).append(e)
    month_index = {m: i for i, m in enumerate(months)}

    w = Walk(start=start, end=end, months=months, events=events)
    balance = profile.balance_cents
    cur_month: str | None = None
    m_min = m_min_date = m_in = m_out = None  # type: ignore[assignment]
    day = start + timedelta(days=1)

    def close_month() -> None:
        if cur_month is not None and cur_month in month_index:
            w.series.append(
                MonthPoint(
                    month=cur_month,
                    end_balance_cents=balance,
                    min_balance_cents=m_min,
                    min_balance_date=m_min_date,
                    inflow_cents=m_in,
                    outflow_cents=m_out,
                )
            )

    while day <= end:
        mk = month_key(day)
        if mk != cur_month:
            close_month()
            cur_month, m_min, m_min_date, m_in, m_out = mk, None, None, 0, 0
        mult = 1.0
        if income_multiplier and mk in month_index and month_index[mk] < len(income_multiplier):
            mult = income_multiplier[month_index[mk]]
        todays = by_day.get(day, [])
        for e in todays:
            if e.amount_cents < 0:
                balance += e.amount_cents
                m_out += -e.amount_cents
        after_outflows = balance
        for e in todays:
            if e.amount_cents > 0:
                amt = int(round(e.amount_cents * mult)) if e.kind == "income" else e.amount_cents
                balance += amt
                m_in += amt
        drip = _drip_for_day(day, profile.variable.mean_monthly_cents)
        balance -= drip
        m_out += drip
        w.drip_by_day[day] = drip
        w.daily_end_balance[day] = balance
        low = min(after_outflows, balance)
        if m_min is None or low < m_min:
            m_min, m_min_date = low, day
        day += timedelta(days=1)
    close_month()
    return w


def result_from_walk(w: Walk, profile: Profile, commitments: list[Commitment], option_id: str | None) -> ProjectionResult:
    series = w.series
    worst = min(series, key=lambda p: (p.min_balance_cents, p.min_balance_date))
    slack = profile.monthly_slack_cents + sum(monthly_equivalent(c.recurring_cents, c.cadence) for c in commitments)
    return ProjectionResult(
        option_id=option_id,
        series=series,
        min_balance_cents=worst.min_balance_cents,
        min_balance_date=worst.min_balance_date,
        monthly_slack_cents=slack,
        months_below_floor=[p.month for p in series if p.min_balance_cents < profile.safety_floor_cents],
        months_negative=[p.month for p in series if p.min_balance_cents < 0],
        flags=[],
    )


def project(
    profile: Profile,
    commitments: list[Commitment],
    horizon_months: int = 12,
    start: date | None = None,
    one_off_overrides: list[OneOff] | None = None,
    income_multiplier: list[float] | None = None,
    *,
    option_id: str | None = None,
    derive_flags: bool = True,
) -> ProjectionResult:
    """SPEC.md §6.3 entry point. `option_id` labels the result; `derive_flags=False` skips flags (used by re-runs)."""
    from . import flags  # local import: flags re-enters project() for the deductible stress

    w = walk(profile, commitments, horizon_months, start, one_off_overrides, income_multiplier)
    res = result_from_walk(w, profile, commitments, option_id)
    if derive_flags:
        res.flags = flags.derive(profile, commitments, w, res, start=start, one_off_overrides=one_off_overrides, income_multiplier=income_multiplier)
    return res
