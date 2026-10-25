"""Numeric guardrail (SPEC.md §3.2, §6.6).

The LLM may *reference* numbers that are in its input payload; it may never
*generate* new ones. `allowed_numbers(payload)` collects every number in the
payload (numeric values, cents→dollars conversions, and numbers inside strings
such as chunk text, dates and pre-formatted "$1,000" labels). `check(text,
allowed)` returns the number strings in `text` that are not allowed, and
`apply(obj, allowed)` walks every string field of an LLM response and either
raises (DEV_MODE=1) or strips the offending sentence and logs it.

The same tokenizer runs on both sides, so "15/30/5", "$1,250", "12.5%", "1.2k"
and "2027-01-15" behave identically in the payload and in the output.
"""
from __future__ import annotations

import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from .. import config

log = logging.getLogger(__name__)

T = TypeVar("T")

# Whitelist: counting numbers and nearby years.
SMALL_INT_MAX = 12
YEAR_RANGE = range(2020, 2031)
TOLERANCE = 0.01

# $1,250.50 | 1,250 | 12.5% | 1.2k | 1250 — captured with their k/% suffix.
_NUM = re.compile(r"(?<![A-Za-z])\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(k\b|K\b|%)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class GuardrailViolation(ValueError):
    def __init__(self, offending: list[str], where: str = ""):
        self.offending = offending
        self.where = where
        super().__init__(f"LLM output contains numbers not in its input{f' ({where})' if where else ''}: {offending}")


def numbers_in(text: str) -> list[tuple[str, float]]:
    """(matched text, numeric value) for each number token in `text`."""
    out: list[tuple[str, float]] = []
    for m in _NUM.finditer(text):
        whole, frac, suffix = m.group(1), m.group(2) or "", m.group(3)
        try:
            value = float(whole.replace(",", "") + frac)
        except ValueError:
            continue
        if suffix and suffix.lower() == "k":
            value *= 1000
        out.append((m.group(0).strip(), value))
    return out


def allowed_numbers(payload: Any) -> set[float]:
    """Every number in the payload, plus cents→dollars for numeric values."""
    allowed: set[float] = set()

    def visit(x: Any) -> None:
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            v = abs(float(x))
            allowed.update({v, round(v / 100, 2)})
        elif isinstance(x, str):
            for _, v in numbers_in(x):
                allowed.update({v, round(v / 100, 2)})
        elif isinstance(x, dict):
            for k, v in x.items():
                visit(k)
                visit(v)
        elif isinstance(x, (list, tuple, set)):
            for v in x:
                visit(v)
        elif isinstance(x, BaseModel):
            visit(x.model_dump(mode="json"))

    visit(payload)
    return allowed


def _is_allowed(value: float, allowed: set[float]) -> bool:
    if value == int(value) and (0 <= int(value) <= SMALL_INT_MAX or int(value) in YEAR_RANGE):
        return True
    if value in allowed:
        return True
    tol = abs(value) * TOLERANCE
    return any(abs(value - a) <= tol for a in allowed)


def check(text: str, allowed: set[float]) -> list[str]:
    """Number strings in `text` that are not present in `allowed` (±1%)."""
    return [s for s, v in numbers_in(text) if not _is_allowed(v, allowed)]


def strip_violations(text: str, allowed: set[float]) -> tuple[str, list[str]]:
    """Remove every sentence containing a disallowed number. Returns (text, offending)."""
    offending: list[str] = []
    kept: list[str] = []
    for sentence in _SENTENCE.split(text):
        bad = check(sentence, allowed)
        if bad:
            offending.extend(bad)
        else:
            kept.append(sentence)
    return " ".join(kept).strip(), offending


def apply(obj: T, allowed: set[float], *, where: str = "", raise_in_dev: bool | None = None) -> T:
    """Enforce the guardrail on every string field of `obj` (Pydantic model, dict, list or str).

    DEV_MODE=1: raise GuardrailViolation listing every offending number.
    Otherwise: strip the sentences that contain them, log, and return the cleaned object.
    Empty list items left behind by stripping are dropped.
    """
    strict = config.DEV_MODE if raise_in_dev is None else raise_in_dev
    all_offending: list[str] = []

    def clean(x: Any) -> Any:
        if isinstance(x, str):
            new, bad = strip_violations(x, allowed)
            all_offending.extend(bad)
            return new
        if isinstance(x, list):
            items = [clean(v) for v in x]
            return [v for v in items if not (isinstance(v, str) and not v)]
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()}
        return x

    if isinstance(obj, BaseModel):
        cleaned = type(obj).model_validate(clean(obj.model_dump()))
    else:
        cleaned = clean(obj)

    if all_offending:
        if strict:
            raise GuardrailViolation(all_offending, where)
        log.warning("guardrail: stripped numbers not in payload%s: %s", f" ({where})" if where else "", all_offending)
    return cleaned  # type: ignore[return-value]


__all__ = ["GuardrailViolation", "allowed_numbers", "apply", "check", "numbers_in", "strip_violations"]
