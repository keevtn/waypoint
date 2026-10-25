"""POST /bank/import_csv: Chase-style and Bank of America-style exports (debit/credit split and a
single signed amount), the store swap + profile rebuild, mapping override, and a garbage file. No network."""
from __future__ import annotations

import json
from datetime import date, timedelta

from app.bank import csv_import

TODAY = date.today()


def _rows(months: int = 4):
    """Biweekly payroll, monthly rent on the 1st, and some spend across `months` months."""
    out = []
    start = TODAY - timedelta(days=30 * months)
    d = start
    while d <= TODAY:
        out.append((d, "ACH DEPOSIT PENN STATE PAYROLL", 70000))
        d += timedelta(days=14)
    d = date(start.year, start.month, 1)
    while d <= TODAY:
        if d >= start:
            out.append((d, "CHECK 1012 RIVERSIDE APTS RENT", -85000))
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    for i in range(0, (TODAY - start).days, 3):
        out.append((start + timedelta(days=i), f"WEGMANS #{i} STATE COLLEGE PA", -(1800 + (i % 7) * 350)))
    return sorted(out)


def chase_csv() -> str:
    lines = ["Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #"]
    for d, name, amt in _rows():
        lines.append(f"{'CREDIT' if amt > 0 else 'DEBIT'},{d:%m/%d/%Y},{name},{amt / 100:.2f},{'ACH_CREDIT' if amt > 0 else 'DEBIT_CARD'},1000.00,")
    lines.append("DEBIT,13/45/2026,BROKEN ROW,abc,DEBIT_CARD,,")  # unparsable
    lines.append(lines[1])  # duplicate
    return "\n".join(lines) + "\n"


def bofa_csv() -> str:
    lines = ["Date,Description,Debit,Credit,Running Bal."]
    for d, name, amt in _rows():
        debit = f"{-amt / 100:,.2f}" if amt < 0 else ""
        credit = f"{amt / 100:,.2f}" if amt > 0 else ""
        lines.append(f'{d:%m/%d/%Y},"{name}",{debit},{credit},"1,000.00"')
    return "\r\n".join(lines) + "\r\n"


def test_chase_style_amount_column_parses():
    p = csv_import.parse(chase_csv())
    assert p.skipped == 2 and len(p.transactions) == len(_rows())
    pay = [t for t in p.transactions if "payroll" in t.raw_name.lower()]
    assert all(t.amount_cents == 70000 for t in pay)
    rent = [t for t in p.transactions if "rent" in t.raw_name.lower()]
    assert all(t.amount_cents == -85000 and t.date.day == 1 for t in rent)
    assert p.transactions == sorted(p.transactions, key=lambda t: t.date, reverse=True)
    assert any("skipped" in w for w in p.warnings)


def test_bofa_style_debit_credit_split_parses():
    p = csv_import.parse(bofa_csv())
    assert p.skipped == 0 and len(p.transactions) == len(_rows())
    assert {t.amount_cents for t in p.transactions if t.amount_cents > 0} == {70000}
    assert min(t.amount_cents for t in p.transactions) == -85000
    assert not any("Several columns" in w for w in p.warnings)


def test_mapping_override_and_short_history_warning():
    text = "When,What,In,Out\n2026-10-01,Pay,500.00,\n2026-10-03,Coffee,,4.50\n2026-10-20,Pay,500.00,\n"
    p = csv_import.parse(text, {"date": "When", "description": "What", "credit": "In", "debit": "Out"})
    assert [t.amount_cents for t in p.transactions] == [50000, -450, 50000]
    assert any("days of history" in w for w in p.warnings)


def test_money_and_date_parsing():
    assert csv_import.parse_money("(12.50)") == -1250 and csv_money("$1,234.00") == 123400 and csv_import.parse_money("abc") is None
    assert csv_import.detect_date_format(["2026-01-02", "2026-03-04"]) == "%Y-%m-%d"
    assert csv_import.detect_date_format(["01/02/2026", "11/30/2026"]) == "%m/%d/%Y"
    assert csv_import.detect_date_format(["25/01/2026", "30/11/2026"]) == "%d/%m/%Y"


def csv_money(s: str) -> int | None:
    return csv_import.parse_money(s)


def test_import_route_replaces_store_and_rebuilds_profile(client):
    client.post("/api/bank/connect", json={})
    persona = client.get("/api/profile").json()
    files = {"file": ("chase.csv", chase_csv().encode(), "text/csv")}
    r = client.post("/api/bank/import_csv", files=files, data={"balance_cents": "250000"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == len(_rows()) and body["skipped"] == 2
    prof = body["profile"]
    assert prof["balance_cents"] == 250000 and prof["as_of"] == TODAY.isoformat()
    assert any(i["amount_cents"] == 70000 and i["cadence"] == "biweekly" for i in prof["income"])
    assert any(x["amount_cents"] == -85000 and x["cadence"] == "monthly" for x in prof["recurring"])
    assert client.get("/api/profile").json() == prof  # persisted
    txns = client.get("/api/profile/transactions?limit=500").json()
    assert len(txns) == len(_rows()) and all(t["id"].startswith("csv_") for t in txns)
    assert client.get("/api/projection/baseline").json()["monthly_slack_cents"] == prof["monthly_slack_cents"]
    # no balance given: unchanged and warned
    r = client.post("/api/bank/import_csv", files={"file": ("b.csv", bofa_csv().encode("latin-1"), "text/csv")})
    assert r.status_code == 200 and r.json()["profile"]["balance_cents"] == 250000
    assert any("balance" in w.lower() for w in r.json()["warnings"])
    # mapping as a JSON form field
    r = client.post("/api/bank/import_csv", files={"file": ("b.csv", bofa_csv().encode(), "text/csv")}, data={"mapping": json.dumps({"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit"})})
    assert r.status_code == 200, r.text
    # connect is still the reset
    client.post("/api/bank/connect", json={})
    assert client.get("/api/profile").json() == persona


def test_garbage_file_is_400_with_error_envelope(client):
    r = client.post("/api/bank/import_csv", files={"file": ("x.bin", b"\x00\x01\x02 not a csv \xff\xfe", "application/octet-stream")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_csv"
    r = client.post("/api/bank/import_csv", files={"file": ("x.csv", b"just one line of prose with no commas", "text/csv")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_csv"
    r = client.post("/api/bank/import_csv", files={"file": ("x.csv", b"a,b,c\n1,2,3\n", "text/csv")})
    assert r.status_code == 400 and "column" in r.json()["error"]["message"]
    r = client.post("/api/bank/import_csv", files={"file": ("big.csv", b"0" * (csv_import.MAX_BYTES + 1), "text/csv")})
    assert r.status_code == 400
    r = client.post("/api/bank/import_csv", files={"file": ("x.csv", chase_csv().encode(), "text/csv")}, data={"mapping": "{not json"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_mapping"
