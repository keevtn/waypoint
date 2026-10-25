"""Explainer (SPEC.md §6.6): one LLM call per evaluate, one Explanation per option.

The model receives the compact payload (inputs, options + constraints, projections,
retrieved chunks) and returns text with [s:chunk] / [c:constraint] markers plus the
chunk ids it used. Code then: enforces the numeric guardrail against that payload,
drops markers pointing at chunks/constraints it was not given, and builds Citation
objects from the index. The model never emits a Citation or a number of its own.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from ..decisions.cache import Evaluation
from ..models import Explanation
from . import guardrail, payload
from .client import get_llm

_S_MARK = re.compile(r"\s*\[s:([^\]\s]+)\]")
_C_MARK = re.compile(r"\s*\[c:([^\]\s]+)\]")


class TightMonthOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str
    why: str


class ExplanationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_id: str
    verdict: str
    pros: list[str]
    cons: list[str]
    tight_months: list[TightMonthOut]
    citation_ids: list[str]


class ExplainOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanations: list[ExplanationOut]


def build_payload(ev: Evaluation) -> dict:
    cited = [cid for c in ev.constraints for cid in c.citation_ids]
    chunks = payload.merge_chunks(payload.chunks_for_ids(cited), payload.retrieve_chunks(payload.evaluation_query(ev), ev.module_id))
    return {
        "module": payload.module_view(ev.module_id),
        **payload.horizon_view(ev),
        "option_ids": [o.id for o in ev.options],
        "option_labels": payload.option_labels(ev.options),
        "inputs": payload.inputs_view(ev.inputs),
        "floor_display": payload.dollars(ev.profile.safety_floor_cents),
        "options": [payload.option_view(o, ev.constraints) for o in ev.options],
        "projections": payload.projections_view(ev.projections, ev.options),
        "suggestions": payload.suggestions_view(ev),
        "chunks": chunks,
    }


def scrub_markers(text: str, chunk_ids: set[str], constraint_ids: set[str]) -> str:
    """Remove [s:]/[c:] markers that point at ids the model was not given."""
    text = _S_MARK.sub(lambda m: m.group(0) if m.group(1) in chunk_ids else "", text)
    text = _C_MARK.sub(lambda m: m.group(0) if m.group(1) in constraint_ids else "", text)
    return text.strip()


def used_chunk_ids(*texts: str) -> list[str]:
    out: list[str] = []
    for t in texts:
        out.extend(_S_MARK.findall(t))
    return list(dict.fromkeys(out))


def explain(ev: Evaluation) -> list[Explanation]:
    data = build_payload(ev)
    out = get_llm().call("explain", data, ExplainOut)
    out = guardrail.apply(out, guardrail.allowed_numbers(data), where="explain")

    chunk_ids = {c["id"] for c in data["chunks"]}
    by_option = {e.option_id: e for e in out.explanations}
    results: list[Explanation] = []
    for o in ev.options:
        e = by_option.get(o.id)
        if e is None:
            continue
        allowed_c = set(o.constraint_ids)

        def clean(text: str) -> str:
            return payload.replace_option_ids(scrub_markers(text, chunk_ids, allowed_c), ev.options)

        verdict = clean(e.verdict)
        pros = [clean(p) for p in e.pros]
        cons = [clean(c) for c in e.cons]
        tight = [{"month": t.month, "why": clean(t.why)} for t in e.tight_months]
        ids = used_chunk_ids(verdict, *pros, *cons, *(t["why"] for t in tight)) + [c for c in e.citation_ids if c in chunk_ids]
        results.append(
            Explanation(
                option_id=o.id,
                verdict=verdict,
                pros=[p for p in pros if p],
                cons=[c for c in cons if c],
                tight_months=tight,
                citations=payload.citations_for(ids, chunk_ids),
            )
        )
    return results
