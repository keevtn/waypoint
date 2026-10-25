"""Numeric guardrail (SPEC.md §3.2, §11): a planted bad number is caught."""
from __future__ import annotations

import pytest

from app.llm import guardrail
from app.llm.explainer import ExplainOut
from app.models import Explanation

PAYLOAD = {
    "inputs": {"deductible_comfort_cents": 60000, "deductible_comfort_display": "$600", "vehicle_value_cents": 950000},
    "options": [{"id": "std_limited_1000", "price": {"monthly_cents": 16100, "display": "$161/month"}, "attributes": {"deductible": 1000}}],
    "projections": {"std_limited_1000": {"min_balance_display": "-$1,418", "min_balance_date": "2027-01-20", "months_below_floor": ["2027-01"]}},
    "chunks": [{"id": "pa-auto-insurance-guide#0", "text": "The minimum limits are $15,000/$30,000 bodily injury and $5,000 property damage, with $5,000 medical benefits. 15/30/5."}],
}


def test_numbers_in_handles_formats():
    vals = dict(guardrail.numbers_in("Pay $1,250 or 12.5% or 1.2k; limits 15/30/5 on 2027-01-15."))
    assert vals["$1,250"] == 1250
    assert vals["12.5%"] == 12.5
    assert vals["1.2k"] == 1200
    assert {15, 30, 5, 2027, 1} <= set(vals.values())


def test_allowed_numbers_include_cents_dollars_and_string_numbers():
    allowed = guardrail.allowed_numbers(PAYLOAD)
    assert 60000 in allowed and 600 in allowed  # cents -> dollars
    assert 1418 in allowed  # from a display string
    assert 15000 in allowed and 150 in allowed  # from chunk text
    assert 161 in allowed


def test_check_passes_payload_numbers_and_small_ints():
    allowed = guardrail.allowed_numbers(PAYLOAD)
    text = "A claim costs $1,000, above your $600 comfort. Three months in 2027 are tight; the premium is $161 a month and January 20 is the low point."
    assert guardrail.check(text, allowed) == []


def test_check_catches_planted_number():
    allowed = guardrail.allowed_numbers(PAYLOAD)
    assert guardrail.check("Set aside $1,337 before January.", allowed) == ["$1,337"]
    assert guardrail.check("About 2.5k is enough.", allowed) == ["2.5k"]


def test_tolerance_one_percent():
    allowed = {1418.0}
    assert guardrail.check("$1,410", allowed) == []  # within 1%
    assert guardrail.check("$1,400", allowed) == ["$1,400"]  # 1.3% off


def test_apply_raises_in_dev_mode():
    allowed = guardrail.allowed_numbers(PAYLOAD)
    bad = ExplainOut.model_validate(
        {"explanations": [{"option_id": "std_limited_1000", "verdict": "Fine.", "pros": ["Move $1,337 to savings."], "cons": [], "tight_months": [], "citation_ids": []}]}
    )
    with pytest.raises(guardrail.GuardrailViolation) as exc:
        guardrail.apply(bad, allowed, raise_in_dev=True)
    assert exc.value.offending == ["$1,337"]


def test_apply_strips_sentence_in_prod_mode():
    allowed = guardrail.allowed_numbers(PAYLOAD)
    exp = Explanation(
        option_id="std_limited_1000",
        verdict="Your deductible is $1,000. You should keep $1,337 handy. That is above your $600 comfort.",
        pros=["Move $1,337 to savings."],
        cons=["Premium is $161/month."],
        tight_months=[{"month": "2027-01", "why": "Balance falls to -$1,418 after a $99 surprise."}],
        citations=[],
    )
    cleaned = guardrail.apply(exp, allowed, raise_in_dev=False)
    assert cleaned.verdict == "Your deductible is $1,000. That is above your $600 comfort."
    assert cleaned.pros == []  # the only sentence was stripped, so the item is dropped
    assert cleaned.cons == ["Premium is $161/month."]
    assert cleaned.tight_months[0]["why"] == ""
