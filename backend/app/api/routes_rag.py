"""RAG routes (SPEC.md §6.5, §7). Logic lives in app/rag/answer.py."""
from __future__ import annotations

from fastapi import APIRouter

from .. import config
from ..models import RagAskRequest, RagAskResponse
from ..rag import answer
from ..rag.index import warm_in_background

router = APIRouter(prefix="/api/rag", tags=["rag"])

# Kept as module attributes for anything that imported them from the Phase 0 stub.
INVESTING_REFUSAL = answer.INVESTING_REFUSAL
NO_SOURCE_REFUSAL = answer.NO_SOURCE_REFUSAL
is_investing_question = answer.is_investing_question

# Load the real embedding model + index off the request path at startup.
if not config.LLM_FAKE:
    warm_in_background()


@router.post("/ask", response_model=RagAskResponse)
def ask(body: RagAskRequest) -> RagAskResponse:
    return answer.ask(body.question, body.module)
