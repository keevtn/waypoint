"""Every fixture in backend/fixtures/ must validate against its §5 model."""
from __future__ import annotations

from pydantic import TypeAdapter

from app import fixtures
from app.models import (
    ActionCard,
    ConnectResponse,
    DecisionSummary,
    EvaluateResponse,
    ExplainResponse,
    Profile,
    ProjectionResult,
    RagAskResponse,
    StressResponse,
    Transaction,
)

CASES = {
    "profile": Profile,
    "baseline": ProjectionResult,
    "decisions": list[DecisionSummary],
    "evaluate_auto": EvaluateResponse,
    "explain_auto": ExplainResponse,
    "stress_auto": StressResponse,
    "action_auto": ActionCard,
    "rag_ask_ok": RagAskResponse,
    "rag_ask_refusal": RagAskResponse,
    "connect": ConnectResponse,
    "transactions": list[Transaction],
}


def test_all_fixtures_validate():
    for name, model in CASES.items():
        TypeAdapter(model).validate_python(fixtures.load(name))


def test_fake_seams_are_offline():
    from app.llm.client import FakeLLM, get_llm
    from app.rag.index import FakeEmbedder, get_embedder

    assert isinstance(get_llm(), FakeLLM)
    emb = get_embedder()
    assert isinstance(emb, FakeEmbedder)
    v = emb.embed(["limited tort pennsylvania"])[0]
    assert len(v) == emb.dim
    assert abs(sum(x * x for x in v) - 1.0) < 1e-6
