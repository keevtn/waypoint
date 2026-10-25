"""LLM client seam (SPEC.md §6.6, §15.5).

Every LLM call in the app goes through `get_llm().call(call_type, payload, output_type)`
so logging, forced-JSON parsing and retries apply uniformly, and so CI (LLM_FAKE=1)
never touches the network. The numeric guardrail (`guardrail.py`) is applied by the
callers in `explainer.py` / `stress.py` / `action.py`, which know which payload the
numbers must come from.

Call types, their prompt file in `prompts/`, and the Pydantic model each returns:
  "explain"  -> explainer.txt -> explainer.ExplainOut   (list of per-option explanations)
  "select"   -> select.txt    -> stress.SelectOut       (exactly 3 scenarios)
  "critique" -> critique.txt  -> stress.CritiqueOut
  "action"   -> action.txt    -> action.ActionOut
  "rag"      -> rag.txt       -> RagAskResponse         (rag/answer.py rebuilds citations)

FakeLLM returns canned objects shaped like the fixtures so the whole pipeline runs
offline; the real client forces JSON with structured outputs
(`output_config.format = json_schema`, the model's JSON schema with
additionalProperties=false everywhere) and validates with Pydantic, retrying once
with the validation error appended. [VERIFIED 2026-10-24 against the claude-api
reference: forced `tool_choice` ("any"/"tool") returns 400 on claude-sonnet-5-5, so
structured outputs replace the tool-use trick SPEC §6.6 describes.]
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from .. import config, fixtures
from ..models import ActionCard, Critique, Explanation, RagAskResponse, Scenario

log = logging.getLogger(__name__)

T = TypeVar("T")

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# SPEC §6.6: Sonnet for explainer/stress/critique/action; Haiku for small classifiers.
MODEL_MAIN = "claude-sonnet-5-5"
MODEL_SMALL = "claude-haiku-5-5"
TIMEOUT_SECONDS = 30.0
MAX_TOKENS = 4096

_CALL_MODEL = {
    "explain": MODEL_MAIN,
    "select": MODEL_MAIN,
    "critique": MODEL_MAIN,
    "action": MODEL_MAIN,
    "rag": MODEL_MAIN,
}
# Effort trades latency for depth; the chart must already be on screen when these run.
_CALL_EFFORT = {"explain": "medium", "select": "low", "critique": "medium", "action": "low", "rag": "low"}


class LLMError(RuntimeError):
    """The model could not produce a valid response (network, refusal, or schema failure)."""


class LLM(Protocol):
    def call(self, call_type: str, payload: dict[str, Any], output_type: type[T]) -> T:
        """Return an instance of `output_type` for the given call type and payload."""
        ...


def load_prompt(call_type: str) -> str:
    path = PROMPTS_DIR / f"{_PROMPT_FILES.get(call_type, call_type)}.txt"
    return path.read_text(encoding="utf-8").strip()


_PROMPT_FILES = {"explain": "explainer", "select": "select", "critique": "critique", "action": "action", "rag": "rag"}


# ---------------------------------------------------------------------------
# Fake client (CI, offline demo fallback)
# ---------------------------------------------------------------------------


class FakeLLM:
    """Returns canned objects derived from the fixtures. Ignores the payload text but
    keeps option ids consistent with it where that matters for the pipeline."""

    def call(self, call_type: str, payload: dict[str, Any], output_type: type[T]) -> T:
        if call_type == "explain":
            data = fixtures.load("explain_auto")["explanations"]
            data = {
                "explanations": [
                    {
                        "option_id": e["option_id"],
                        "verdict": e["verdict"],
                        "pros": e["pros"],
                        "cons": e["cons"],
                        "tight_months": e["tight_months"],
                        "citation_ids": [c["chunk_id"] for c in e["citations"]],
                    }
                    for e in data
                ]
            }
        elif call_type == "select":
            data = {"scenarios": [s["scenario"] for s in fixtures.load("stress_auto")["scenarios"]]}
        elif call_type == "critique":
            c = fixtures.load("stress_auto")["critique"]
            data = {
                "case_against": c["case_against"],
                "case_for": c["case_for"],
                "recommendation_shift": c["recommendation_shift"],
                "citation_ids": [x["chunk_id"] for x in c["citations"]],
            }
        elif call_type == "action":
            a = fixtures.load("action_auto")
            data = {
                "headline": a["headline"],
                "steps": a["steps"],
                "questions_to_ask": a["questions_to_ask"],
                "citation_ids": [x["chunk_id"] for x in a["citations"]],
            }
        elif call_type == "rag":
            data = fixtures.load("rag_ask_ok")
        else:
            raise ValueError(f"FakeLLM: unknown call type {call_type!r}")
        return _validate(output_type, data)


# ---------------------------------------------------------------------------
# Real client
# ---------------------------------------------------------------------------


def _validate(output_type: type[T], data: Any) -> T:
    return TypeAdapter(output_type).validate_python(data)


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a JSON schema acceptable to structured outputs: every object closed and
    every property required (optional fields are declared nullable instead)."""

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            node = {k: walk(v) for k, v in node.items() if k not in {"default", "title"}}
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            return node
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def output_schema(output_type: type) -> dict[str, Any]:
    return _strict(TypeAdapter(output_type).json_schema())


class AnthropicLLM:
    """Anthropic Messages API behind the seam. One request per call; JSON forced via
    structured outputs; Pydantic-validated; one retry with the error appended."""

    def __init__(self, api_key: str | None = None):
        import anthropic  # imported lazily so CI never needs the SDK configured

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY, timeout=TIMEOUT_SECONDS, max_retries=1)

    def call(self, call_type: str, payload: dict[str, Any], output_type: type[T]) -> T:
        system = load_prompt(call_type)
        schema = output_schema(output_type)
        user = json.dumps(payload, ensure_ascii=False, default=str)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        last_error: Exception | None = None
        for attempt in range(2):
            text = self._request(call_type, system, messages, schema)
            try:
                return _validate(output_type, json.loads(text))
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                log.warning("llm %s: invalid JSON/schema on attempt %d: %s", call_type, attempt + 1, str(e)[:300])
                messages = [
                    *messages,
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": "Your previous reply did not match the required schema. "
                        f"Validation error:\n{str(e)[:1500]}\n\nReply again with only the corrected JSON object.",
                    },
                ]
        raise LLMError(f"{call_type}: response failed validation twice: {last_error}")

    def _request(self, call_type: str, system: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> str:
        a = self._anthropic
        t0 = time.perf_counter()
        try:
            resp = self._client.messages.create(
                model=_CALL_MODEL.get(call_type, MODEL_MAIN),
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
                output_config={
                    "effort": _CALL_EFFORT.get(call_type, "medium"),
                    "format": {"type": "json_schema", "schema": schema},
                },
            )
        except a.APITimeoutError as e:
            raise LLMError(f"{call_type}: timed out after {TIMEOUT_SECONDS:.0f}s") from e
        except a.RateLimitError as e:
            raise LLMError(f"{call_type}: rate limited") from e
        except a.APIStatusError as e:
            raise LLMError(f"{call_type}: API error {e.status_code}: {e.message}") from e
        except a.APIConnectionError as e:
            raise LLMError(f"{call_type}: connection error") from e
        elapsed = time.perf_counter() - t0
        usage = getattr(resp, "usage", None)
        log.info(
            "llm %s: %s stop=%s in=%s out=%s %.1fs",
            call_type,
            resp.model,
            resp.stop_reason,
            getattr(usage, "input_tokens", "?"),
            getattr(usage, "output_tokens", "?"),
            elapsed,
        )
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            raise LLMError(f"{call_type}: model refused ({getattr(details, 'category', None)})")
        if resp.stop_reason == "max_tokens":
            raise LLMError(f"{call_type}: output truncated at {MAX_TOKENS} tokens")
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        if not text.strip():
            raise LLMError(f"{call_type}: empty response")
        return text


_instance: LLM | None = None


def get_llm() -> LLM:
    global _instance
    if _instance is None:
        _instance = FakeLLM() if config.LLM_FAKE else AnthropicLLM()
    return _instance


def set_llm(llm: LLM | None) -> None:
    """Test hook: inject a client (None resets to the config default)."""
    global _instance
    _instance = llm


__all__ = [
    "LLM",
    "LLMError",
    "FakeLLM",
    "AnthropicLLM",
    "get_llm",
    "set_llm",
    "load_prompt",
    "output_schema",
    "ActionCard",
    "Critique",
    "Explanation",
    "RagAskResponse",
    "Scenario",
    "BaseModel",
]
