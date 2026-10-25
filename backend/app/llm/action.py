"""Action card (SPEC.md §6.6): the LLM orders and phrases the module's template steps
for this user and may add at most two flag-derived steps. Deadline and
talk_to_human_url come from code/env, never from the model.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from .. import config
from ..decisions.cache import Evaluation
from ..models import ActionCard, Option
from . import guardrail, payload
from .client import get_llm
from .explainer import scrub_markers, used_chunk_ids

MAX_EXTRA_STEPS = 2


class ActionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headline: str
    steps: list[str]
    questions_to_ask: list[str]
    citation_ids: list[str]


def _seed_chunk_ids(ev: Evaluation, option: Option) -> list[str]:
    """Chunks the template steps rely on (quotes, agents, lender, lapse) plus this option's constraint citations."""
    from ..rag import facts

    ids = [facts.GET_THREE_QUOTES, facts.INDEPENDENT_AGENT, facts.PA_LAPSE_SUSPENSION]
    if getattr(ev.inputs, "financed", False):
        ids.append(facts.LENDER_REQUIRES_PHYSICAL_DAMAGE)
    ids += [cid for c in ev.constraints if c.id in option.constraint_ids for cid in c.citation_ids]
    return ids


def build_payload(ev: Evaluation, option: Option, template: dict) -> dict:
    cited = _seed_chunk_ids(ev, option)
    query = f"{template.get('configuration', '')} shopping for quotes independent agent lender requirements proof of insurance registration"
    chunks = payload.merge_chunks(payload.chunks_for_ids(cited), payload.retrieve_chunks(query, ev.module_id))
    return {
        "module": payload.module_view(ev.module_id),
        "option": payload.option_view(option, ev.constraints),
        "template": template,
        "projection": payload.projection_view(ev.projections[option.id]),
        "floor_display": payload.dollars(ev.profile.safety_floor_cents),
        "chunks": chunks,
    }


def action_card(ev: Evaluation, module, option: Option) -> ActionCard:
    template = module.action_template(ev.inputs, option, ev.profile.as_of)
    data = build_payload(ev, option, template)
    out = get_llm().call("action", data, ActionOut)
    out = guardrail.apply(out, guardrail.allowed_numbers(data), where="action")

    chunk_ids = {c["id"] for c in data["chunks"]}
    allowed_c = set(option.constraint_ids)

    def clean(text: str) -> str:
        return payload.replace_option_ids(scrub_markers(text, chunk_ids, allowed_c), ev.options)

    headline = clean(out.headline)
    steps = [s for s in (clean(s) for s in out.steps) if s]
    questions = [q for q in (clean(q) for q in out.questions_to_ask) if q]
    # The model may add at most two steps beyond the template (SPEC §6.6).
    steps = steps[: len(template["steps"]) + MAX_EXTRA_STEPS] or list(template["steps"])
    questions = questions or list(template["questions_to_ask"])

    ids = used_chunk_ids(headline, *steps, *questions) + [c for c in out.citation_ids if c in chunk_ids]
    deadline = template.get("deadline")
    return ActionCard(
        option_id=option.id,
        headline=headline or template["steps"][0],
        steps=steps,
        questions_to_ask=questions,
        deadline=date.fromisoformat(deadline) if deadline else None,
        deadline_reason=template.get("deadline_reason"),
        talk_to_human_url=config.TALK_TO_HUMAN_URL,
        citations=payload.citations_for(ids, chunk_ids),
    )
