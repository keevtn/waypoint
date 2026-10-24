"""`/api/rag/ask` logic (SPEC.md §6.5): investing guard -> retrieve -> grounding
check -> answer with citations, or a refusal.

Answers come from the LLM ("rag" call type, see llm/client.py) when a real
client is available. Under LLM_FAKE=1, or if the LLM call fails or returns no
valid citation, the answer is extractive: the best-matching source sentences,
quoted verbatim, each followed by its [s:<chunk_id>] marker. Either way every
citation returned is a chunk that retrieval actually produced.
"""
from __future__ import annotations

import logging
import re

from .. import config
from ..models import RagAskResponse
from .retrieve import Hit, coverage, retrieve, term_weights, to_citation
from .text import content_terms, sentences

log = logging.getLogger(__name__)

NO_SOURCE_REFUSAL = "I don't have a trusted source for that, so I won't guess."
INVESTING_REFUSAL = "Investing is outside what this tool covers."

# Word-boundary patterns so "emergency fund" or "fundamentals" don't trip it.
_INVESTING = re.compile(
    r"\binvest|\bstocks?\b|\bcrypto|\bbitcoin\b|\bethereum\b|\betfs?\b|"
    r"\b(index|mutual|hedge)\s+funds?\b|\bportfolio|\bbrokerage\b|\b401\s?\(?k\)?|"
    r"\broth\b|\biras?\b|\bdividends?\b|\bday\s?trad|\boptions\s+trading\b",
    re.IGNORECASE,
)

ANSWER_K = 3  # chunks handed to the answerer
MIN_COVERAGE = 0.6  # idf-weighted share of question terms the top chunks must contain
MAX_SENTENCES = 2

_CITE = re.compile(r"\s*\[s:([^\]\s]+)\]")


def is_investing_question(question: str) -> bool:
    return bool(_INVESTING.search(question))


def _refuse(msg: str) -> RagAskResponse:
    return RagAskResponse(answer=None, refusal=msg, citations=[])


def ask(question: str, module: str | None = None) -> RagAskResponse:
    question = question.strip()
    if not question:
        return _refuse(NO_SOURCE_REFUSAL)
    if is_investing_question(question):
        return _refuse(INVESTING_REFUSAL)

    hits = retrieve(question, module=module)[:ANSWER_K]
    if not hits or coverage(question, hits) < MIN_COVERAGE:
        return _refuse(NO_SOURCE_REFUSAL)

    if not config.LLM_FAKE:
        resp = _llm_answer(question, hits)
        if resp is not None:
            return resp
    return _extractive_answer(question, hits)


# -- LLM path -----------------------------------------------------------------


def llm_payload(question: str, hits: list[Hit]) -> dict:
    """What the "rag" LLM call receives. The prompt (llm/prompts/rag.txt) must say:
    answer only from these chunks, end every sentence with [s:<chunk id>], and
    return answer=null with a refusal if the chunks don't answer the question."""
    return {
        "question": question,
        "chunks": [
            {"id": h.chunk.id, "title": h.chunk.title, "publisher": h.chunk.publisher, "text": h.chunk.text}
            for h in hits
        ],
    }


def _llm_answer(question: str, hits: list[Hit]) -> RagAskResponse | None:
    from ..llm.client import get_llm  # Session A's seam; imported lazily

    try:
        out = get_llm().call("rag", llm_payload(question, hits), RagAskResponse)
    except Exception:
        log.exception("rag: LLM answer failed; falling back to extractive")
        return None
    if not out.answer:
        return _refuse(out.refusal or NO_SOURCE_REFUSAL)

    by_id = {h.chunk.id: h.chunk for h in hits}
    cited = [cid for cid in dict.fromkeys(_CITE.findall(out.answer)) if cid in by_id]
    if not cited:
        log.warning("rag: LLM answer cited no retrieved chunk; falling back to extractive")
        return None
    # Drop any marker pointing at a chunk we didn't provide.
    answer = _CITE.sub(lambda m: m.group(0) if m.group(1) in by_id else "", out.answer).strip()
    return RagAskResponse(answer=answer, refusal=None, citations=[to_citation(by_id[c]) for c in cited])


# -- extractive path ----------------------------------------------------------


def _extractive_answer(question: str, hits: list[Hit]) -> RagAskResponse:
    weights = term_weights(question)
    scored: list[tuple[float, int, str, Hit]] = []
    order = 0
    for h in hits:
        for sent in sentences(h.chunk.text):
            terms = set(content_terms(sent))
            s = sum(w for t, w in weights.items() if t in terms)
            if s > 0:
                # Prefer the better chunk, then the earlier sentence, on ties.
                scored.append((s + h.score, -order, sent, h))
            order += 1
    if not scored:
        return _refuse(NO_SOURCE_REFUSAL)

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best = scored[0][0]
    picked = [x for x in scored if x[0] >= 0.6 * best][:MAX_SENTENCES]

    parts, cited = [], []
    for _, _, sent, h in picked:
        parts.append(f"{sent} [s:{h.chunk.id}]")
        if h.chunk.id not in cited:
            cited.append(h.chunk.id)
    by_id = {h.chunk.id: h.chunk for h in hits}
    return RagAskResponse(answer=" ".join(parts), refusal=None, citations=[to_citation(by_id[c]) for c in cited])
