"""Phase 2 golden tests (SPEC.md §6.3 "Tests"): hand-computed balances, min-date logic, deductible stress."""
from __future__ import annotations

from datetime import date

from app.models import Commitment, IncomeStream, OneOff, Profile, RecurringItem, VariableSpend
from app.projection import flags, project
from app.projection.engine import horizon_months, walk

START = date(2026, 10, 31)


def _profile(**over) -> Profile:
    base = dict(
        as_of=START,
        balance_cents=100000,
        income=[IncomeStream(id="inc_pay", label="Payroll", amount_cents=50000, cadence="biweekly", next_date=date(2026, 11, 6), confidence=1.0)],
        recurring=[RecurringItem(id="rec_rent", label="Rent", amount_cents=-60000, cadence="monthly", next_date=date(2026, 11, 1), confidence=1.0)],
        one_offs=[OneOff(id="oo_fee", label="Lab fee", amount_cents=-30000, date=date(2026, 12, 5), source="user")],
        variable=VariableSpend(mean_monthly_cents=0, std_monthly_cents=0, months_observed=4),
        safety_floor_cents=20000,
        monthly_slack_cents=48333,  # 50000*26/12 - 60000
    )
    base.update(over)
    return Profile(**base)


def test_three_month_golden():
    r = project(_profile(), [], horizon_months=3)
    assert [p.month for p in r.series] == ["2026-11", "2026-12", "2027-01"]
    nov, dec, jan = r.series
    # Nov: rent 1st -> 40,000; paychecks 6th, 20th
    assert (nov.end_balance_cents, nov.min_balance_cents, nov.min_balance_date) == (140000, 40000, date(2026, 11, 1))
    assert (nov.inflow_cents, nov.outflow_cents) == (100000, 60000)
    # Dec: rent 1st -> 80,000; pay 4th; fee 5th; pay 18th
    assert (dec.end_balance_cents, dec.min_balance_cents, dec.min_balance_date) == (150000, 80000, date(2026, 12, 1))
    assert (dec.inflow_cents, dec.outflow_cents) == (100000, 90000)
    # Jan: rent and payday both on the 1st -> outflow applied first, min 90,000 before the paycheck
    assert (jan.end_balance_cents, jan.min_balance_cents, jan.min_balance_date) == (240000, 90000, date(2027, 1, 1))
    assert (jan.inflow_cents, jan.outflow_cents) == (150000, 60000)
    assert (r.min_balance_cents, r.min_balance_date) == (40000, date(2026, 11, 1))
    assert r.monthly_slack_cents == 48333
    assert r.months_below_floor == [] and r.months_negative == []
    assert [f.code for f in r.flags] == ["target_reached"]
    assert r.option_id is None


def test_one_off_day_before_paycheck_sets_min_date_and_flags():
    p = _profile(one_offs=[OneOff(id="oo_big", label="Deposit", amount_cents=-90000, date=date(2026, 11, 5), source="user")])
    r = project(p, [], horizon_months=1)
    nov = r.series[0]
    assert nov.min_balance_cents == -50000 and nov.min_balance_date == date(2026, 11, 5)
    assert nov.end_balance_cents == 50000
    assert r.months_negative == ["2026-11"] and r.months_below_floor == ["2026-11"]
    codes = {f.code: f for f in r.flags}
    assert {"below_floor", "negative"} <= set(codes)
    d = codes["negative"].detail
    assert d["min_balance_cents"] == -50000 and d["floor_cents"] == 20000 and d["shortfall_cents"] == 70000
    labels = [c["label"] for c in d["contributors"]]
    assert labels[:2] == ["Deposit", "Rent"]  # largest outflows within the 7-day window, biggest first


def test_variable_drip_sums_exactly_and_affects_min():
    p = _profile(variable=VariableSpend(mean_monthly_cents=31000, std_monthly_cents=0, months_observed=4), one_offs=[])
    w = walk(p, [], horizon=1)
    assert sum(v for d, v in w.drip_by_day.items() if d.month == 11) == 31000
    r = project(p, [], horizon_months=1)
    assert r.series[0].outflow_cents == 60000 + 31000
    assert r.series[0].end_balance_cents == 100000 - 60000 + 100000 - 31000


def test_commitment_upfront_term_and_slack():
    c = Commitment(id="c1", label="Plan", upfront_cents=5000, recurring_cents=-10000, cadence="monthly", start_date=date(2026, 11, 15), term_months=2)
    r = project(_profile(one_offs=[]), [c], horizon_months=4, option_id="opt")
    # upfront 5,000 + two payments (Nov 15, Dec 15) then nothing
    assert r.series[0].outflow_cents == 60000 + 5000 + 10000
    assert r.series[1].outflow_cents == 60000 + 10000
    assert r.series[2].outflow_cents == 60000
    assert r.option_id == "opt"
    assert r.monthly_slack_cents == 48333 - 10000


def test_deductible_stress_month3_is_december_from_october():
    assert flags.deductible_claim_date(START) == date(2026, 12, 1)
    assert horizon_months(date(2026, 10, 24), 12)[0] == "2026-11"
    unaffordable = Commitment(id="c_big", label="Premium", recurring_cents=-10000, start_date=date(2026, 11, 1), risk_exposure_cents=100000)
    ok = Commitment(id="c_small", label="Premium", recurring_cents=-10000, start_date=date(2026, 11, 1), risk_exposure_cents=30000)
    r1 = project(_profile(one_offs=[]), [unaffordable], horizon_months=3)
    r2 = project(_profile(one_offs=[]), [ok], horizon_months=3)
    f1 = next(f for f in r1.flags if f.code.startswith("deductible"))
    f2 = next(f for f in r2.flags if f.code.startswith("deductible"))
    # Dec 1 balance after rent + premium = 130,000 - 70,000 = 60,000
    assert f1.code == "deductible_unaffordable" and f1.severity == "danger"
    assert f1.detail["min_balance_cents"] == -40000 and f1.detail["claim_date"] == "2026-12-01"
    assert f2.code == "deductible_ok" and f2.severity == "info"
    assert f2.detail["min_balance_cents"] == 30000
    # the stress run does not leak into the main series
    assert r1.series[1].min_balance_cents == 60000


def test_income_multiplier_and_low_slack():
    p = _profile(one_offs=[])
    r = project(p, [], horizon_months=2, income_multiplier=[0.0, 1.0])
    assert r.series[0].inflow_cents == 0 and r.series[1].inflow_cents == 100000
    c = Commitment(id="c_heavy", label="Heavy", recurring_cents=-40000, start_date=date(2026, 11, 1))
    r = project(p, [c], horizon_months=2)
    assert any(f.code == "low_slack" and f.detail["monthly_slack_cents"] == 8333 for f in r.flags)


def test_persona_baseline_outcomes():
    """§8 outcomes 1 and 5 on the generated persona for a fixed as_of."""
    from app.bank import local_loader
    from app.profile import detect

    data = local_loader.load(date(2026, 10, 24))
    profile = detect.build_profile(data.transactions, data.balance_cents, data.as_of, user_one_offs=data.one_offs)
    r = project(profile, [])
    assert [p.month for p in r.series] == ["2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04", "2027-05", "2027-06", "2027-07", "2027-08", "2027-09", "2027-10"]
    assert r.months_negative == [] and r.months_below_floor == []
    assert 57000 <= r.monthly_slack_cents <= 66000
    loan = Commitment(id="cmt_loan", label="Car loan", recurring_cents=-21200, start_date=date(2026, 11, 17), term_months=48)
    r2 = project(profile, [loan])
    assert 36000 <= r2.monthly_slack_cents <= 45000  # ~$390 after the car loan


def test_spend_multiplier_scales_the_drip():
    from app.bank import local_loader
    from app.profile import detect
    from datetime import date

    data = local_loader.load(date(2026, 10, 24))
    p = detect.build_profile(data.transactions, data.balance_cents, data.as_of, user_one_offs=data.one_offs)
    base = project(p, [], 12, derive_flags=False)
    up = project(p, [], 12, derive_flags=False, spend_multiplier=[1.25] * 12)
    assert up.min_balance_cents <= base.min_balance_cents  # the persona's baseline minimum is day 1 (rent), before the drip accumulates
    assert up.series[-1].end_balance_cents < base.series[-1].end_balance_cents
    assert all(u.end_balance_cents < b.end_balance_cents for u, b in zip(up.series, base.series))
    # month 1's extra outflow is 25% of the variable mean (cumulative rounding sums the drip exactly)
    assert up.series[0].outflow_cents - base.series[0].outflow_cents == int(round(p.variable.mean_monthly_cents * 1.25)) - p.variable.mean_monthly_cents
    # a multiplier only on month 3 leaves months 1-2 untouched
    only3 = project(p, [], 12, derive_flags=False, spend_multiplier=[1.0, 1.0, 1.4])
    assert [m.end_balance_cents for m in only3.series[:2]] == [m.end_balance_cents for m in base.series[:2]]
    assert only3.series[2].end_balance_cents < base.series[2].end_balance_cents
