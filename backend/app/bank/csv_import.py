"""CSV bank-export import (POST /bank/import_csv). Pure parsing: bytes in, Transactions +
warnings out; the route swaps them into the single-user store and rebuilds the profile.

- Header auto-detection by name: date (date / posted / transaction date), description
  (description / memo / name / payee / details), amount, or a debit + credit pair; an optional
  `mapping` {"date": ..., "description": ..., "amount": ... | "debit": ..., "credit": ...}
  overrides it by header name.
- Date format auto-detected over the whole column (ISO, M/D/Y, D/M/Y when unambiguous, Mon D YYYY).
- Sign normalized to ours (inflow positive): a debit column is an outflow; an amount column keeps
  its sign (bank exports write outflows negative); parentheses mean negative.
- Dedupe by (date, amount, normalized name). Row contents are never logged.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from ..models import Transaction
from ..profile.normalize import normalize_merchant

MAX_BYTES = 2 * 1024 * 1024
MIN_HISTORY_DAYS = 60

DATE_NAMES = ("transaction date", "posted date", "posting date", "date", "posted")
DESC_NAMES = ("description", "memo", "name", "payee", "details", "transaction description")
AMOUNT_NAMES = ("amount", "transaction amount")
DEBIT_NAMES = ("debit", "withdrawal", "withdrawals", "money out")
CREDIT_NAMES = ("credit", "deposit", "deposits", "money in")

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d", "%b %d %Y", "%b %d, %Y", "%d %b %Y", "%m-%d-%Y")


class CsvImportError(ValueError):
    pass


@dataclass
class Parsed:
    transactions: list[Transaction]
    skipped: int
    warnings: list[str] = field(default_factory=list)


def decode(data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise CsvImportError("File is larger than 2 MB")
    if not data.strip():
        raise CsvImportError("File is empty")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    if "\x00" in text:
        raise CsvImportError("File does not look like text")
    return text


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().strip('"').lower())


def _find(headers: list[str], names: tuple[str, ...], warnings: list[str], what: str) -> str | None:
    normed = {_norm(h): h for h in headers}
    hits = [normed[n] for n in names if n in normed]
    if not hits:
        hits = [h for h in headers if any(n in _norm(h) for n in names)]
    if len(hits) > 1:
        warnings.append(f"Several columns could be the {what} ({', '.join(hits)}); used {hits[0]!r}")
    return hits[0] if hits else None


def detect_columns(headers: list[str], mapping: dict[str, str] | None, warnings: list[str]) -> dict[str, str]:
    mapping = {k: v for k, v in (mapping or {}).items() if v}
    for k, v in mapping.items():
        if v not in headers:
            raise CsvImportError(f"Mapping column {v!r} for {k!r} is not in the file header")
    cols: dict[str, str] = {}
    cols["date"] = mapping.get("date") or _find(headers, DATE_NAMES, warnings, "date") or ""
    cols["description"] = mapping.get("description") or _find(headers, DESC_NAMES, warnings, "description") or ""
    if "amount" in mapping:
        cols["amount"] = mapping["amount"]
    elif "debit" in mapping or "credit" in mapping:
        cols["debit"], cols["credit"] = mapping.get("debit", ""), mapping.get("credit", "")
    else:
        amount = _find(headers, AMOUNT_NAMES, warnings, "amount")
        debit = _find(headers, DEBIT_NAMES, warnings, "debit")
        credit = _find(headers, CREDIT_NAMES, warnings, "credit")
        if debit or credit:
            cols["debit"], cols["credit"] = debit or "", credit or ""
            if amount:
                warnings.append(f"Both an amount column ({amount!r}) and debit/credit columns were found; used debit/credit")
        elif amount:
            cols["amount"] = amount
    if not cols["date"] or not cols["description"] or not (cols.get("amount") or cols.get("debit") or cols.get("credit")):
        raise CsvImportError("Could not find date, description and amount (or debit/credit) columns in the header")
    return cols


def parse_money(raw: str) -> int | None:
    s = raw.strip().replace(",", "").replace("$", "").replace("USD", "").strip()
    if not s or s in {"-", "--"}:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("-"):
        neg, s = not neg, s[1:]
    if not re.fullmatch(r"\d+(\.\d{1,2})?|\.\d{1,2}", s):
        return None
    cents = int(round(float(s) * 100))
    return -cents if neg else cents


def detect_date_format(values: list[str]) -> str | None:
    sample = [v.strip() for v in values if v.strip()][:200]
    best: tuple[int, str] | None = None
    for fmt in DATE_FORMATS:
        ok = 0
        for v in sample:
            try:
                datetime.strptime(v, fmt)
                ok += 1
            except ValueError:
                pass
        if ok and (best is None or ok > best[0]):
            best = (ok, fmt)
    return best[1] if best else None


def parse(text: str, mapping: dict[str, str] | None = None) -> Parsed:
    warnings: list[str] = []
    head = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(head, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel  # type: ignore[assignment]
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise CsvImportError("File has no data rows")
    headers = [h.strip() for h in rows[0]]
    if len(set(_norm(h) for h in headers if h)) < 2:
        raise CsvImportError("First row does not look like a CSV header")
    cols = detect_columns(headers, mapping, warnings)
    idx = {h: i for i, h in enumerate(headers)}

    def cell(row: list[str], col: str) -> str:
        i = idx.get(col)
        return row[i] if col and i is not None and i < len(row) else ""

    fmt = detect_date_format([cell(r, cols["date"]) for r in rows[1:]])
    if fmt is None:
        raise CsvImportError("Could not recognise the date format")
    if fmt == "%d/%m/%Y":
        warnings.append("Dates read as day/month/year")

    out: list[Transaction] = []
    seen: set[tuple[date, int, str]] = set()
    skipped = 0
    for n, row in enumerate(rows[1:], start=2):
        try:
            d = datetime.strptime(cell(row, cols["date"]).strip(), fmt).date()
        except ValueError:
            skipped += 1
            continue
        if "amount" in cols:
            amt = parse_money(cell(row, cols["amount"]))
        else:
            debit = parse_money(cell(row, cols.get("debit", "")))
            credit = parse_money(cell(row, cols.get("credit", "")))
            if debit is None and credit is None:
                amt = None
            else:
                amt = (abs(credit) if credit else 0) - (abs(debit) if debit else 0)
        name = cell(row, cols["description"]).strip()
        if amt is None or not name:
            skipped += 1
            continue
        merchant = normalize_merchant(name).label
        key = (d, amt, merchant.lower())
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        out.append(Transaction(id=f"csv_{len(out) + 1:05d}", date=d, amount_cents=amt, raw_name=name, merchant=merchant, category=None))
    if not out:
        raise CsvImportError("No rows could be parsed")
    if skipped:
        warnings.append(f"{skipped} row(s) could not be parsed or were duplicates and were skipped")
    span = (max(t.date for t in out) - min(t.date for t in out)).days
    if span < MIN_HISTORY_DAYS:
        warnings.append(f"Only {span} days of history; recurring detection needs at least {MIN_HISTORY_DAYS}")
    out.sort(key=lambda t: t.date, reverse=True)
    return Parsed(transactions=out, skipped=skipped, warnings=warnings)
