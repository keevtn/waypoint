"""LLM client seam (SPEC.md §6.6, §15.5).

Phase 0 provides the protocol and `FakeLLM`. The real Anthropic-backed client
is Phase 6 (Session A, Wave 2). Every LLM call in the app must go through
`get_llm()` so the guardrail and logging apply uniformly and so CI (LLM_FAKE=1)
never touches the network.

Call types and the Pydantic model each returns:
  "explain"  -> list[Explanation]
  "select"   -> list[Scenario]
  "critique" -> Critique
  "action"   -> ActionCard
  "rag"      -> RagAskResponse
"""
from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, TypeAdapter

from .. import config, fixtures
from ..models import ActionCard, Critique, Explanation, RagAskResponse, Scenario

T = TypeVar("T")


class LLM(Protocol):
    def call(self, call_type: str, payload: dict[str, Any], output_type: type[T]) -> T:
        """Return an instance of `output_type` for the given call type and payload."""
        ...


class FakeLLM:
    """Returns canned objects from fixtures. Ignores the payload."""

    _sources = {
        "explain": ("explain_auto", "explanations"),
        "select": ("stress_auto", "scenarios"),
        "critique": ("stress_auto", "critique"),
        "action": ("action_auto", None),
        "rag": ("rag_ask_ok", None),
    }

    def call(self, call_type: str, payload: dict[str, Any], output_type: type[T]) -> T:
        try:
            fixture, key = self._sources[call_type]
        except KeyError as e:
            raise ValueError(f"FakeLLM: unknown call type {call_type!r}") from e
        data = fixtures.load(fixture)
        if key is not None:
            data = data[key]
        if call_type == "select":
            data = [s["scenario"] for s in data]
        return TypeAdapter(output_type).validate_python(data)


class AnthropicLLM:
    """Real client. Implemented in Phase 6; raises until then."""

    def call(self, call_type: str, payload: dict[str, Any], output_type: type[T]) -> T:
        raise NotImplementedError("AnthropicLLM lands in Phase 6 (llm/client.py)")


_instance: LLM | None = None


def get_llm() -> LLM:
    global _instance
    if _instance is None:
        _instance = FakeLLM() if config.LLM_FAKE else AnthropicLLM()
    return _instance


__all__ = [
    "LLM",
    "FakeLLM",
    "AnthropicLLM",
    "get_llm",
    "ActionCard",
    "Critique",
    "Explanation",
    "RagAskResponse",
    "Scenario",
    "BaseModel",
]
