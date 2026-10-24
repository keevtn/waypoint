"""Phase 1 exit tests (SPEC.md §10 row 1, §6.2): persona generation, normalization, detection."""
from __future__ import annotations

from datetime import date, timedelta

from app.bank import local_loader, persona
from app.models import Transaction
from app.profile import detect
from app.profile.normalize import normalize_merchant

AS_OF = date(2026, 10, 24)


def _txn(i: int, d: date, cents: int, name: str) -> Transaction:
    return Transaction(id=f"t{i}", date=d, amount_cents=cents, raw_name=name, merchant=normalize_merchant(name).label)


def test_persona_is_deterministic_and_relative_to_as_of():
    a = persona.generate(AS_OF)
    b = persona.generate(AS_OF)
    assert a == b
    assert a["as_of"] == "2026-10-24"
    dates = [date.fromisoformat(t["date"]) for t in a["transactions"]]
    assert max(dates) <= AS_OF
    assert min(dates) >= persona.history_start(AS_OF) == date(2026, 6, 1)
    later = persona.generate(AS_OF + timedelta(days=30))
    assert max(date.fromisoformat(t["date"]) for t in later["transactions"]) <= AS_OF + timedelta(days=30)
    # future one-offs per §8
    by_id = {o["id"]: o for o in a["future_one_offs"]}
    assert by_id["oo_tuition"]["date"] == "2027-01-15"
    assert by_id["oo_textbooks"]["date"] == "2027-01-20"
    assert by_id["oo_registration"]["date"] == "2026-11-05"
    assert a["moment"]["auto_insurance"]["registration_deadline"] == "2026-11-23"


def test_plaid_custom_user_shape_and_sign():
    doc = persona.generate(AS_OF)
    cfg = persona.to_plaid_custom_user(doc)
    acct = cfg["override_accounts"][0]
    assert acct["type"] == "depository" and acct["subtype"] == "checking"
    assert acct["starting_balance"] == 1840.0
    assert len(acct["transactions"]) == len(doc["transactions"]) < 250  # Plaid custom-user size limit
    pay = next(t for t in acct["transactions"] if t["description"] == "PENN STATE PAYROLL")
    rent = next(t for t in acct["transactions"] if t["description"].startswith("RENT"))
    assert pay["amount"] == -700.0  # Plaid: negative = money in
    assert rent["amount"] == 850.0  # Plaid: positive = money out
    assert set(pay) == {"date_transacted", "date_posted", "amount", "description", "currency"}


def test_normalize_merchant():
    assert normalize_merchant("GIANT FOOD #6421").label == "Giant Food"
    assert normalize_merchant("AMAZON.COM*2K4PL").key == "AMAZON"
    assert normalize_merchant("PENN STATE PAYROLL").label == "Payroll"
    assert normalize_merchant("RENT - THE META").key == normalize_merchant("RENT   THE META 2").key
    assert normalize_merchant("SOME NEW PLACE 123").label == "Some New Place"


def test_detects_persona_streams_with_high_confidence():
    data = local_loader.load(AS_OF)
    profile = detect.build_profile(
        data.transactions,
        data.balance_cents,
        data.as_of,
        user_one_offs=data.one_offs,
        safety_floor_cents=data.safety_floor_cents,
    )
    inc = {i.label: i for i in profile.income}
    rec = {r.label: r for r in profile.recurring}
    assert set(inc) == {"Payroll", "Family transfer"}
    assert set(rec) == {"Rent", "Phone", "Gym", "Music streaming"}
    assert inc["Payroll"].cadence == "biweekly" and inc["Payroll"].amount_cents == 70000
    assert inc["Payroll"].next_date == date(2026, 11, 6)
    assert inc["Family transfer"].cadence == "monthly" and inc["Family transfer"].next_date == date(2026, 11, 1)
    assert rec["Rent"].amount_cents == -85000 and rec["Rent"].next_date == date(2026, 11, 1)
    assert rec["Gym"].amount_cents == -2499
    assert all(x.confidence > 0.8 for x in [*profile.income, *profile.recurring])
    assert all(x.next_date > AS_OF for x in [*profile.income, *profile.recurring])
    # variable spend ~ $260 +/- $70 over 4 full months (§8, tuned)
    assert profile.variable.months_observed == 4
    assert profile.variable.mean_monthly_cents == 26000
    assert 5000 <= profile.variable.std_monthly_cents <= 9000
    # §8 outcome 1: baseline slack ~ $600
    assert 57000 <= profile.monthly_slack_cents <= 66000
    # large non-recurring debits surface as detected one-offs; user one-offs preserved
    detected = {o.label for o in profile.one_offs if o.source == "detected"}
    assert {"Tuition", "Car down payment"} <= detected
    assert {o.id for o in profile.one_offs if o.source == "user"} == {"oo_registration", "oo_tuition", "oo_textbooks"}


def test_recurring_rules_reject_irregular_groups():
    as_of = date(2026, 10, 24)
    # 3 monthly charges, consistent -> recurring
    good = [_txn(i, date(2026, 7 + i, 10), -1999, "NETFLIX") for i in range(3)]
    # amounts inconsistent -> not recurring
    bad_amount = [_txn(10 + i, date(2026, 7 + i, 10), -(1999 + 700 * i), "HULU") for i in range(3)]
    # gaps irregular -> not recurring
    bad_gap = [_txn(20, date(2026, 7, 1), -1500, "DISNEY"), _txn(21, date(2026, 7, 9), -1500, "DISNEY"), _txn(22, date(2026, 9, 30), -1500, "DISNEY")]
    # only 2 occurrences -> not recurring
    few = [_txn(30, date(2026, 8, 3), -3000, "PELOTON"), _txn(31, date(2026, 9, 3), -3000, "PELOTON")]
    rec = detect.detect_recurring(good + bad_amount + bad_gap + few, as_of)
    assert [r.label for r in rec] == ["Netflix"]
    assert rec[0].cadence == "monthly"
    assert rec[0].next_date == date(2026, 11, 10)  # Oct 10 already passed as_of, rolled forward


def test_cadence_classification_and_slack():
    as_of = date(2026, 10, 24)
    weekly = [_txn(i, date(2026, 9, 1) + timedelta(days=7 * i), 25000, "SIDE GIG LLC") for i in range(6)]
    inc = detect.detect_income(weekly, as_of)
    assert inc and inc[0].cadence == "weekly"
    assert detect.monthly_equivalent(70000, "biweekly") == 151667
    assert detect.monthly_equivalent(25000, "weekly") == 108333
    assert detect.monthly_equivalent(10000, "semimonthly") == 20000
    small = [_txn(100 + i, date(2026, 7 + i, 2), 5000, "VENMO CASHBACK") for i in range(3)]
    assert detect.detect_income(small, as_of) == []  # below the $100 income threshold


def test_declared_fallback_merges_when_detection_is_thin():
    as_of = date(2026, 10, 24)
    txns = [_txn(i, date(2026, 10, 1) - timedelta(days=i), -1200, f"SHOP {i}") for i in range(5)]
    p = detect.build_profile(
        txns,
        50000,
        as_of,
        declared_recurring=[{"raw_name": "RENT - THE META", "amount_cents": -85000, "cadence": "monthly", "day": 1}],
        declared_income=[{"raw_name": "PENN STATE PAYROLL", "amount_cents": 70000, "cadence": "biweekly"}],
    )
    assert [r.label for r in p.recurring] == ["Rent"]
    assert p.recurring[0].next_date == date(2026, 11, 1)
    assert [i.label for i in p.income] == ["Payroll"]
