"""Stress-tester plumbing (SPEC.md §6.6, §11): scenario validation against the menu,
deterministic perturbations through project(), critique wiring. No network."""
from __future__ import annotations

import pytest

from app import config
from app.decisions import cache, registry
from app.llm import client as llm_client
from app.llm import payload, stress
from app.models import Scenario

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
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def call(self, call_type, payload_, output_type):
        self.calls.append((call_type, payload_))
        r = self.responses[call_type]
        if isinstance(r, Exception):
            raise r
        return output_type.model_validate(r)


@pytest.fixture
def evaluation(client) -> cache.Evaluation:
    client.post("/api/bank/connect", json={})
    r = client.post("/api/decisions/auto_insurance/evaluate", json={"inputs": INPUTS})
    assert r.status_code == 200
    return cache.get(r.json()["eval_id"])


@pytest.fixture
def stub(monkeypatch):
    def install(responses):
        s = StubLLM(responses)
        monkeypatch.setattr(llm_client, "_instance", s)
        return s

    yield install
    llm_client.set_llm(None)


@pytest.fixture
def menu(evaluation):
    return registry.get("auto_insurance").scenario_menu(evaluation.inputs, evaluation.profile)


CRITIQUE = {
    "case_against": ["In the deductible_claim scenario the $1,000 deductible drives January negative [c:c_deductible_comfort]."],
    "case_for": ["It is the cheaper monthly premium among the options your lender allows."],
    "recommendation_shift": "reconsider",
    "summary": "Reconsider: a single claim breaks the plan [s:naic-deductibles#2].",
    "citation_ids": ["naic-deductibles#2"],
}


# -- selection -------------------------------------------------------------------


def test_normalize_clamps_and_drops_unknown_params(menu):
    t = next(t for t in menu if t.id == "shock_expense")
    s = stress.normalize_scenario(t, {"amount_cents": 9_000_000, "month": 0, "pct": 99}, " why ")
    assert s.params == {"amount_cents": 150000, "month": 1}
    assert s.rationale == "why"
    t = next(t for t in menu if t.id == "deductible_claim")
    assert stress.normalize_scenario(t, {}, "x").params == {"month": 2}  # default from the schema


def test_select_keeps_model_picks_and_forces_deductible_claim(evaluation, menu, stub):
    s = stub(
        {
            "select": {
                "scenarios": [
                    {"template_id": "shock_expense", "params": {"amount_cents": 60000, "month": 2}, "rationale": "December has no buffer."},
                    {"template_id": "shock_expense", "params": {"amount_cents": 60000, "month": 3}, "rationale": "duplicate"},
                    {"template_id": "made_up", "params": {}, "rationale": "nope"},
                    {"template_id": "income_gap", "params": {"months": 9, "start_month": 2}, "rationale": "One payroll stream."},
                ]
            }
        }
    )
    picked = stress.select_scenarios(evaluation, menu, "std_limited_1000")
    assert s.calls[0][0] == "select"
    assert s.calls[0][1]["preferred_option_id"] == "std_limited_1000"
    assert [p.template_id for p in picked] == ["deductible_claim", "shock_expense", "income_gap"]
    assert picked[2].params == {"months": 3, "start_month": 2}  # clamped to the menu's maximum
    assert len({p.template_id for p in picked}) == 3


def test_select_falls_back_to_defaults_on_llm_error(evaluation, menu, stub):
    stub({"select": llm_client.LLMError("boom")})
    picked = stress.select_scenarios(evaluation, menu, "std_limited_1000")
    assert len(picked) == 3 and picked[0].template_id == "deductible_claim"
    assert all(p.rationale for p in picked)


# -- perturbations -------------------------------------------------------------------


def test_deductible_claim_hits_option_not_baseline(evaluation):
    sc = Scenario(template_id="deductible_claim", params={"month": 3}, rationale="r")
    res = stress.run_scenario(evaluation, sc)
    assert "pa_min_limited" not in res.results  # disallowed options are not run
    base, lim, full = res.results["baseline"], res.results["std_limited_1000"], res.results["std_full_500"]
    assert base == evaluation.projections["baseline"]  # no deductible on the baseline
    unstressed = evaluation.projections["std_limited_1000"]
    assert lim.min_balance_cents <= unstressed.min_balance_cents - 100000 + 1  # a $1,000 claim
    # §8/§11: the $1,000 deductible option fails harder than the $500 one under the same claim
    assert lim.min_balance_cents < full.min_balance_cents or lim.months_negative


def test_income_gap_and_hours_cut_reduce_inflows(evaluation):
    base = evaluation.projections["baseline"]
    gap = stress.run_scenario(evaluation, Scenario(template_id="income_gap", params={"months": 1, "start_month": 2}, rationale="r")).results["baseline"]
    assert gap.series[1].inflow_cents < base.series[1].inflow_cents
    assert gap.series[0].inflow_cents == base.series[0].inflow_cents
    cut = stress.run_scenario(evaluation, Scenario(template_id="hours_cut", params={"pct": 50, "from_month": 1}, rationale="r")).results["baseline"]
    assert all(c.inflow_cents < b.inflow_cents for c, b in zip(cut.series, base.series))


def test_shock_and_rent_increase_add_outflows(evaluation):
    base = evaluation.projections["baseline"]
    shock = stress.run_scenario(evaluation, Scenario(template_id="shock_expense", params={"amount_cents": 60000, "month": 2}, rationale="r")).results["baseline"]
    assert shock.series[1].outflow_cents == base.series[1].outflow_cents + 60000
    rent = stress.run_scenario(evaluation, Scenario(template_id="rent_increase", params={"pct": 10, "from_month": 1}, rationale="r")).results["baseline"]
    assert all(r.outflow_cents > b.outflow_cents for r, b in zip(rent.series, base.series))
    assert rent.series[-1].end_balance_cents < base.series[-1].end_balance_cents


# -- route + critique -------------------------------------------------------------------


def test_stress_route_runs_scenarios_and_critique(client, evaluation, stub):
    s = stub(
        {
            "select": {"scenarios": [{"template_id": "deductible_claim", "params": {"month": 3}, "rationale": "Tuition installment in January."}]},
            "critique": CRITIQUE,
        }
    )
    r = client.post("/api/decisions/auto_insurance/stress", json={"eval_id": evaluation.eval_id, "preferred_option_id": "std_limited_1000"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [c[0] for c in s.calls] == ["select", "critique"]
    assert len(body["scenarios"]) == 3
    assert body["scenarios"][0]["scenario"]["template_id"] == "deductible_claim"
    for sr in body["scenarios"]:
        assert set(sr["results"]) == {"baseline", "std_limited_1000", "std_full_500"}
        assert all(len(p["series"]) == 12 for p in sr["results"].values())
    crit = body["critique"]
    assert crit["preferred_option_id"] == "std_limited_1000"
    assert crit["recommendation_shift"] == "reconsider"
    assert [c["chunk_id"] for c in crit["citations"]] == ["naic-deductibles#2"]
    assert any("[s:naic-deductibles#2]" in x for x in crit["case_against"])  # summary folded into the case
    # the critique payload carried the scenario results, not just the scenario list
    payload_ = s.calls[1][1]
    assert payload_["scenarios"][0]["results"]["std_limited_1000"]["months_negative"] is not None
    assert payload_["inputs"]["deductible_comfort_display"] == "$600"
    # scenario labels travel with the payload (select and critique), like option_labels
    assert payload_["scenario_labels"]["deductible_claim"] == "You have to pay the deductible after a claim"
    assert payload_["scenarios"][0]["label"] == "You have to pay the deductible after a claim"
    assert s.calls[0][1]["scenario_labels"] == payload_["scenario_labels"]


def test_scenario_ids_in_prose_become_labels(client, evaluation, stub, menu):
    labels = {t.id: t.label for t in menu}
    out = payload.replace_scenario_ids("Under shock_expense and hours_cut it fails [c:c_deductible_comfort].", menu)
    assert out == f"Under {labels['shock_expense']} and {labels['hours_cut']} it fails [c:c_deductible_comfort]."
    assert payload.replace_scenario_ids("shock_expenses", menu) == "shock_expenses"  # partial match untouched
    crit = {**CRITIQUE, "case_against": ["In the deductible_claim scenario std_limited_1000 goes negative. [s:naic-deductibles#2]"], "summary": "Reconsider: income_gap breaks it."}
    stub({"select": {"scenarios": [{"template_id": "income_gap", "params": {"months": 1, "start_month": 2}, "rationale": "income_gap because payroll is the only income."}]}, "critique": crit})
    r = client.post("/api/decisions/auto_insurance/stress", json={"eval_id": evaluation.eval_id, "preferred_option_id": "std_limited_1000"})
    assert r.status_code == 200, r.text
    body = r.json()
    prose = body["critique"]["case_against"] + body["critique"]["case_for"] + [s["scenario"]["rationale"] for s in body["scenarios"]]
    for text in prose:
        for tid in labels:
            assert tid not in text.replace("[c:", "").split("[s:")[0] or f"[c:{tid}]" in text, text
    assert any(labels["deductible_claim"] in x for x in body["critique"]["case_against"])
    assert any(labels["income_gap"] in x for x in body["critique"]["case_against"])
    gap = next(s for s in body["scenarios"] if s["scenario"]["template_id"] == "income_gap")
    assert gap["scenario"]["rationale"].startswith(labels["income_gap"])


def test_stress_route_guardrail_rejects_invented_number(client, evaluation, stub, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", True)
    bad = dict(CRITIQUE, case_against=["You would need $4,242 in reserve."])
    stub({"select": llm_client.LLMError("skip"), "critique": bad})
    r = client.post("/api/decisions/auto_insurance/stress", json={"eval_id": evaluation.eval_id, "preferred_option_id": "std_limited_1000"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "guardrail_violation"


def test_stress_unknown_option_is_404(client, evaluation):
    r = client.post("/api/decisions/auto_insurance/stress", json={"eval_id": evaluation.eval_id, "preferred_option_id": "nope"})
    assert r.status_code == 404
