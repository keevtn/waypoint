"""RAG routes (SPEC.md §7). Phase 0: fixture-backed stub. Phase 5 (Session C) makes it real.

The investing refusal is kept here even in the stub because it is a hard rule (CLAUDE.md #4).
"""
from __future__ import annotations

from fastapi import APIRouter

from .. import fixtures
from ..models import RagAskRequest, RagAskResponse

router = APIRouter(prefix="/api/rag", tags=["rag"])

INVESTING_KEYWORDS = ("invest", "stock", "crypto", "fund", "etf", "portfolio", "bitcoin")
INVESTING_REFUSAL = "Investing is outside what this tool covers."


def is_investing_question(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in INVESTING_KEYWORDS)


@router.post("/ask", response_model=RagAskResponse)
def ask(body: RagAskRequest) -> RagAskResponse:
    if is_investing_question(body.question):
        return RagAskResponse(answer=None, refusal=INVESTING_REFUSAL, citations=[])
    if "tort" in body.question.lower():
        return RagAskResponse.model_validate(fixtures.load("rag_ask_ok"))
    return RagAskResponse.model_validate(fixtures.load("rag_ask_refusal"))
