"""Action-card seeds for a chosen unit (SPEC.md §6.4). Landlord-agnostic; the LLM may rephrase
but not add numbers. Deadline = the unit's lease start (deposit and first month are due then)."""
from __future__ import annotations

from datetime import date
from typing import Any

from ...models import Option
from .inputs import RentInputs


def _dollars(cents: Any) -> str:
    return f"${int(cents or 0) // 100:,}"


def action_template(inputs: RentInputs, option: Option, as_of: date) -> dict[str, Any]:
    a = option.attributes
    config = (
        f"{option.label}: {_dollars(a.get('rent_cents'))} rent plus about {_dollars(a.get('utilities_est_cents'))} utilities a month, "
        f"{_dollars(a.get('deposit_cents'))} deposit, {a.get('lease_months')}-month lease starting {a.get('start_date')}"
    )
    steps = [
        "Get the full lease in writing and read it before paying anything; confirm the rent, deposit, lease length and which utilities are included.",
        "Confirm in writing what the deposit covers, when it is returned, and what can be deducted at move-out.",
        "Ask for an itemized list of move-in costs (deposit, first month, fees) and the exact date each is due.",
        "Give written notice on your current place in time so you are not paying two rents.",
        "Set up rent autopay from checking on a date a few days after payday, not the 1st.",
    ]
    questions = [
        "Which utilities are included in the rent, and what did last year's tenants typically pay for the rest?",
        "Is subletting or a lease takeover allowed if I leave for the summer?",
        "How much notice is required before the lease ends, and how are renewals and rent increases handled?",
        "Is the deposit held separately, and when is it returned after move-out?",
    ]
    return {
        "option_id": option.id,
        "configuration": config,
        "steps": steps,
        "questions_to_ask": questions,
        "deadline": str(a.get("start_date")),
        "deadline_reason": "Lease start: deposit and first month's rent are due",
    }
