"""Action-card seeds for a chosen purchase plan. Lender-agnostic; the LLM may rephrase but
not add numbers. Deadline = the chosen purchase date."""
from __future__ import annotations

from datetime import date
from typing import Any

from ...models import Option
from .inputs import BigPurchaseInputs
from .rules import dollars, pct


def action_template(inputs: BigPurchaseInputs, option: Option, as_of: date) -> dict[str, Any]:
    a = option.attributes
    financed = int(a.get("term_months") or 0) > 0
    when = str(a.get("date") or inputs.date.isoformat())
    down = int(a.get("down_payment_cents") or 0)
    if financed:
        config = (
            f"{inputs.name} for {dollars(inputs.amount_cents)}, financed over {a.get('term_months')} months at "
            f"{pct(int(a.get('apr_bps') or 0))} APR with {dollars(down)} down: "
            f"{dollars(int(a.get('monthly_payment_cents') or 0))} a month, {dollars(int(a.get('total_cost_cents') or 0))} in total, starting {when}"
        )
        bucket = (
            f"Move the {dollars(down)} down payment into a separate savings bucket before {when} so it is not spent."
            if down > 0
            else f"Set up the monthly payment to come out a few days after payday, starting {when}."
        )
        steps = [
            f"Set the purchase date: {when}. Put it on your calendar and do not buy earlier.",
            bucket,
            "Get the APR and the total cost over the full term in writing before you sign, and compare it with paying cash.",
            "Ask whether there is a prepayment penalty, so you can pay the balance off early if your cash flow allows.",
            "Re-check your balance the week before the date; if a tight month is coming, push the date rather than dip below your floor.",
        ]
        questions = [
            "Is the quoted APR fixed for the whole term, and does it change if a payment is late?",
            "Is there a prepayment penalty or any fee for paying the balance off early?",
            "What is the total I will have paid at the end of the term, including fees?",
            "Is there a deferred-interest or promotional period, and what happens when it ends?",
        ]
    else:
        config = f"{inputs.name} for {dollars(inputs.amount_cents)}, paid in cash on {when}"
        steps = [
            f"Set the purchase date: {when}. Put it on your calendar and do not buy earlier.",
            f"Move the {dollars(inputs.amount_cents)} into a separate savings bucket before {when} so it is not spent.",
            "If a financing offer comes up at checkout, get its APR and total cost in writing before deciding; the cash plan is the comparison point.",
            "Ask whether any financing offer carries a prepayment penalty before you consider it.",
            "Re-check your balance the week before the date; if a tight month is coming, push the date rather than dip below your floor.",
        ]
        questions = [
            "Is the price final, or are there delivery, setup or protection-plan charges on top?",
            "What is the return window and restocking fee?",
            "Would a refurbished or last-year model do the same job for less?",
        ]
    return {
        "option_id": option.id,
        "configuration": config,
        "steps": steps,
        "questions_to_ask": questions,
        "deadline": when,
        "deadline_reason": "Your chosen purchase date",
    }
