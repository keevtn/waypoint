"""Action-card seeds (SPEC.md §6.4 "Action template"). Carrier-agnostic; the LLM (Wave 2) may
rephrase but not add numbers. Deadline = registration_deadline or as_of + 30 days."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ...models import Option
from .inputs import AutoInsuranceInputs


def action_template(inputs: AutoInsuranceInputs, option: Option, as_of: date) -> dict[str, Any]:
    a = option.attributes
    config = (
        f"{a.get('bi_per_person', 0) // 1000}/{a.get('bi_per_accident', 0) // 1000}/{a.get('pd', 0) // 1000} liability, "
        f"${a.get('medical', 0):,} medical, {a.get('tort')} tort"
        + (f", collision + comprehensive with a ${a.get('deductible'):,} deductible" if a.get("collision") else ", no collision/comprehensive")
    )
    deadline = inputs.registration_deadline or (as_of + timedelta(days=30))
    reason = "Vehicle registration deadline" if inputs.registration_deadline else "30 days from today (no registration deadline entered)"
    steps = [
        f"Get at least 3 quotes for exactly this configuration ({config}), including at least one from an independent agency.",
        "Ask the lender for its written coverage requirements and confirm each quote meets them." if inputs.financed else "Confirm each quote meets Pennsylvania's minimum liability and first-party medical requirements.",
        "Confirm your tort election (full vs. limited) in writing before the policy is issued.",
        "Set up autopay from checking on a date a few days after payday, not the 1st.",
        "Keep proof of insurance with you for the registration visit.",
    ]
    questions = [
        "Is the quoted premium a six-month or annual figure, and what does it come to per month?",
        "What is the surcharge or process if I switch from limited to full tort later?",
        "Is there a student, good-grade, or telematics discount I qualify for?",
        "Does this policy satisfy my lender's coverage requirements, and will you send proof to them?" if inputs.financed else "Does this policy satisfy the state's requirements for my registration?",
        f"What happens to my premium after a claim that uses the ${a.get('deductible', 0):,} deductible?" if a.get("collision") else "What would adding collision and comprehensive cost on this policy?",
    ]
    return {
        "option_id": option.id,
        "configuration": config,
        "steps": steps,
        "questions_to_ask": questions,
        "deadline": deadline.isoformat(),
        "deadline_reason": reason,
    }
