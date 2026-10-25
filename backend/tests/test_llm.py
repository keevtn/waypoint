"""LLM layer plumbing (SPEC.md §15.5): schemas, FakeLLM, explainer/action pipelines
with a stubbed client, and the guardrail wired into the routes. No network."""
from __future__ import annotations

import json

import pytest

from app import config
from app.decisions import cache
from app.llm import action as llm_action
from app.llm import client as llm_client
from app.llm import explainer, guardrail, payload
from app.llm.client import FakeLLM, load_prompt, output_schema
from app.models import Citation, RagAskResponse

INPUTS = {
    "vehicle_value_cents": 950000,
    "financed": True,
    "loan_payment_cents": 21200,
    "loan_term_months": 48,
    "driver_age": 21,
    "deductible_comfort_cents": 60000,
    "registration_deadline": "2026-11-23",
}


class StubLLM:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def call(self, call_type, payload_, output_type):
        self.calls.append((call_type, payload_))
        return output_type.model_validate(self.responses[call_type])


@pytest.fixture
def evaluation(client) -> cache.Evaluation:
    client.post("/api/bank/connect", json={})
    r = client.post("/api/decisions/auto_insurance/evaluate", json={"inputs": INPUTS})
    assert r.status_code == 200
    ev = cache.get(r.json()["eval_id"])
    assert ev is not None
    return ev


@pytest.fixture
def stub(monkeypatch):
    def install(responses: dict[str, dict]) -> StubLLM:
        s = StubLLM(responses)
        monkeypatch.setattr(llm_client, "_instance", s)
        return s

    yield install
    llm_client.set_llm(None)


# -- schemas and prompts -------------------------------------------------------


def test_output_schemas_are_closed_and_fully_required():
    for model in (explainer.ExplainOut, llm_action.ActionOut, RagAskResponse):
        schema = output_schema(model)

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    assert node["additionalProperties"] is False
                    assert set(node["required"]) == set(node["properties"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(schema)
        json.dumps(schema)  # serialisable


def test_prompts_exist_and_forbid_new_numbers():
    for call_type in ("explain", "select", "critique", "action", "rag"):
        text = load_prompt(call_type)
        assert "number" in text.lower()
        assert "JSON" in text
    assert "[s:" in load_prompt("explain") and "[c:" in load_prompt("explain")


def test_fake_llm_returns_typed_objects():
    fake = FakeLLM()
    out = fake.call("explain", {}, explainer.ExplainOut)
    assert {e.option_id for e in out.explanations} == {"std_limited_1000", "std_full_500"}
    act = fake.call("action", {}, llm_action.ActionOut)
    assert act.steps and act.citation_ids
    rag = fake.call("rag", {}, RagAskResponse)
    assert rag.answer
    with pytest.raises(ValueError):
        fake.call("nope", {}, RagAskResponse)


# -- payload --------------------------------------------------------------------


def test_dollars_formatting():
    assert payload.dollars(100000) == "$1,000"
    assert payload.dollars(-141800) == "-$1,418"
    assert payload.dollars(2499) == "$24.99"
    assert payload.dollars(None) is None


def test_explain_payload_is_compact_and_grounded(evaluation):
    data = explainer.build_payload(evaluation)
    assert data["option_ids"] == [o.id for o in evaluation.options]
    assert data["inputs"]["deductible_comfort_display"] == "$600"
    ids = {c["id"] for c in data["chunks"]}
    # every constraint citation is handed to the model so it can ground the rules
    for c in evaluation.constraints:
        assert set(c.citation_ids) <= ids
    assert "series" not in json.dumps(data)  # compact view, no 12x daily detail
    assert all("$" in o["price"]["display"] for o in data["options"])


# -- explainer -------------------------------------------------------------------


def _explain_response(ev: cache.Evaluation, chunk_id: str, planted: str | None = None) -> dict:
    exps = []
    for o in ev.options:
        cons = [f"Limited tort waives most pain-and-suffering claims [s:{chunk_id}] [s:not-a-chunk#7]."]
        if planted:
            cons.append(f"Set aside {planted} before January.")
        exps.append(
            {
                "option_id": o.id,
                "verdict": "Meets the state minimum [c:c_pa_minimum] [c:c_made_up].",
                "pros": ["Monthly premium is " + payload.dollars(o.price.cents) + "."],
                "cons": cons,
                "tight_months": [{"month": "2027-01", "why": "Tuition installment and Textbooks land in the same week as the premium."}],
                "citation_ids": [chunk_id, "not-a-chunk#7"],
            }
        )
    return {"explanations": exps}


def test_explain_builds_citations_and_scrubs_unknown_markers(evaluation, stub):
    from app.rag import facts

    s = stub({"explain": _explain_response(evaluation, facts.PA_TORT)})
    out = explainer.explain(evaluation)
    assert s.calls[0][0] == "explain"
    assert [e.option_id for e in out] == [o.id for o in evaluation.options]
    e = next(x for x in out if x.option_id == "std_limited_1000")
    assert "[s:not-a-chunk#7]" not in e.cons[0] and f"[s:{facts.PA_TORT}]" in e.cons[0]
    assert "[c:c_made_up]" not in e.verdict and "[c:c_pa_minimum]" in e.verdict
    assert [c.chunk_id for c in e.citations] == [facts.PA_TORT]
    assert all(isinstance(c, Citation) and c.url for c in e.citations)
    assert e.tight_months == [{"month": "2027-01", "why": "Tuition installment and Textbooks land in the same week as the premium."}]


def test_explain_route_rejects_planted_number_in_dev(client, evaluation, stub, monkeypatch):
    from app.rag import facts

    monkeypatch.setattr(config, "DEV_MODE", True)
    stub({"explain": _explain_response(evaluation, facts.PA_TORT, planted="$1,337")})
    r = client.post("/api/decisions/auto_insurance/explain", json={"eval_id": evaluation.eval_id})
    assert r.status_code == 502
    body = r.json()["error"]
    assert body["code"] == "guardrail_violation" and "$1,337" in body["message"]


def test_explain_route_strips_planted_number_in_prod(client, evaluation, stub, monkeypatch):
    from app.rag import facts

    monkeypatch.setattr(config, "DEV_MODE", False)
    stub({"explain": _explain_response(evaluation, facts.PA_TORT, planted="$1,337")})
    r = client.post("/api/decisions/auto_insurance/explain", json={"eval_id": evaluation.eval_id})
    assert r.status_code == 200
    text = json.dumps(r.json())
    assert "1,337" not in text
    assert "Limited tort" in text  # the good sentence survived


def test_explain_unknown_eval_is_404(client):
    r = client.post("/api/decisions/auto_insurance/explain", json={"eval_id": "eval_nope"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "unknown_eval"


def test_llm_error_is_502(client, evaluation, monkeypatch):
    class Broken:
        def call(self, *a, **k):
            raise llm_client.LLMError("explain: timed out after 30s")

    monkeypatch.setattr(llm_client, "_instance", Broken())
    try:
        r = client.post("/api/decisions/auto_insurance/explain", json={"eval_id": evaluation.eval_id})
    finally:
        llm_client.set_llm(None)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "llm_unavailable"


# -- action card -------------------------------------------------------------------


def test_action_card_uses_code_deadline_and_caps_extra_steps(client, evaluation, stub, monkeypatch):
    from app.rag import facts

    monkeypatch.setattr(config, "TALK_TO_HUMAN_URL", None)
    template_steps = 5
    s = stub(
        {
            "action": {
                "headline": "Get three quotes for a 100/300/50, full tort, $500-deductible policy before your registration deadline.",
                "steps": [f"Step {i} [s:{facts.GET_THREE_QUOTES}]." for i in range(1, template_steps + 5)],
                "questions_to_ask": ["Is the quoted premium six-month or annual?"],
                "citation_ids": [facts.GET_THREE_QUOTES, "bogus#1"],
            }
        }
    )
    r = client.post("/api/decisions/auto_insurance/action", json={"eval_id": evaluation.eval_id, "option_id": "std_full_500"})
    assert r.status_code == 200, r.text
    card = r.json()
    assert s.calls[0][0] == "action"
    assert s.calls[0][1]["template"]["deadline"] == "2026-11-23"
    assert card["option_id"] == "std_full_500"
    assert card["deadline"] == "2026-11-23" and "registration" in card["deadline_reason"].lower()
    assert len(card["steps"]) == template_steps + llm_action.MAX_EXTRA_STEPS
    assert card["talk_to_human_url"] is None
    assert [c["chunk_id"] for c in card["citations"]] == [facts.GET_THREE_QUOTES]


def test_action_unknown_option_is_404(client, evaluation):
    r = client.post("/api/decisions/auto_insurance/action", json={"eval_id": evaluation.eval_id, "option_id": "nope"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "unknown_option"


def test_guardrail_allows_every_number_the_fake_explainer_uses(evaluation):
    """The fixture-shaped FakeLLM output must pass the guardrail against a real payload
    (otherwise LLM_FAKE=1 demos would 502)."""
    data = explainer.build_payload(evaluation)
    out = FakeLLM().call("explain", data, explainer.ExplainOut)
    guardrail.apply(out, guardrail.allowed_numbers(data), raise_in_dev=True)
