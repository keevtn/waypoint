"""Merchant normalization (SPEC.md §6.2).

Uppercase, strip digits / `#` / `*` / trailing store codes, collapse whitespace,
keep the first 2-3 tokens, then map a small alias table to friendly labels.
Everything downstream (detection, labels in flags and explanations) keys on
`NormalizedMerchant.key`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_STRIP = re.compile(r"[\d#*]+|[^A-Z\s]")
_WS = re.compile(r"\s+")
_NOISE = {"COM", "INC", "LLC", "THE", "FROM", "TRIP"}

# key (first tokens after cleanup) -> (label, category)
ALIASES: dict[str, tuple[str, str | None]] = {
    "PENN STATE PAYROLL": ("Payroll", "income"),
    "PAYROLL": ("Payroll", "income"),
    "ZELLE MOM": ("Family transfer", "income"),
    "ZELLE": ("Family transfer", "income"),
    "RENT META": ("Rent", "housing"),
    "RENT": ("Rent", "housing"),
    "VERIZON WIRELESS": ("Phone", "utilities"),
    "VERIZON": ("Phone", "utilities"),
    "PLANET FITNESS": ("Gym", "subscriptions"),
    "SPOTIFY": ("Music streaming", "subscriptions"),
    "CARMAX DOWN PAYMENT": ("Car down payment", "auto"),
    "PENN STATE BURSAR": ("Tuition", "education"),
    "GIANT FOOD": ("Giant Food", "groceries"),
    "SHEETZ": ("Sheetz", "gas"),
    "CHIPOTLE": ("Chipotle", "dining"),
    "AMAZON": ("Amazon", "shopping"),
    "UBER": ("Uber", "transport"),
    "TARGET T": ("Target", "shopping"),
    "TARGET": ("Target", "shopping"),
    "MCLANAHANS DOWNTOWN": ("McLanahan's", "groceries"),
    "MCLANAHANS": ("McLanahan's", "groceries"),
}


@dataclass(frozen=True)
class NormalizedMerchant:
    key: str  # grouping key, e.g. "PENN STATE PAYROLL"
    label: str  # display label, e.g. "Payroll"
    category: str | None


def normalize_key(raw_name: str) -> str:
    s = raw_name.upper()
    s = s.replace("-", " ").replace("_", " ").replace(".", " ")
    s = _STRIP.sub(" ", s)
    tokens = [t for t in _WS.split(s.strip()) if t and t not in _NOISE]
    return " ".join(tokens[:3])


def normalize_merchant(raw_name: str) -> NormalizedMerchant:
    key = normalize_key(raw_name)
    for cand in (key, " ".join(key.split()[:2]), " ".join(key.split()[:1])):
        if cand in ALIASES:
            label, category = ALIASES[cand]
            return NormalizedMerchant(key=cand, label=label, category=category)
    label = key.title() if key else raw_name.strip()[:40]
    return NormalizedMerchant(key=key or label.upper(), label=label, category=None)


def slug(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
