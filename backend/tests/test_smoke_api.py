"""The "is main demoable" gate (SPEC.md §15.5).

Walks the demo flow with TestClient. Extend when an endpoint lands; never remove
an assertion to get green.
"""
from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data_mode"] == "local"
    assert isinstance(body["index_chunks"], int)


def test_connect_then_profile(client):
    r = client.post("/api/bank/connect", json={})
    assert r.status_code == 200
    assert r.json()["transactions"] > 0

    r = client.get("/api/profile")
    assert r.status_code == 200
    p = r.json()
    assert p["balance_cents"] > 0
    assert len(p["income"]) >= 2
    assert len(p["recurring"]) >= 4
    assert all(i["amount_cents"] > 0 for i in p["income"])
    assert all(i["amount_cents"] < 0 for i in p["recurring"])
    # Phase 1: detection on the persona, not a fixture
    assert {r["label"] for r in p["recurring"]} >= {"Rent", "Phone", "Gym", "Music streaming"}
    assert {i["cadence"] for i in p["income"]} == {"biweekly", "monthly"}
    assert all(x["confidence"] > 0.8 for x in p["income"] + p["recurring"])
    assert p["variable"]["months_observed"] >= 3
    assert 50000 <= p["monthly_slack_cents"] <= 70000  # §8 outcome 1: ~$600
    assert {o["id"] for o in p["one_offs"] if o["source"] == "user"} == {"oo_registration", "oo_tuition", "oo_textbooks"}

    r = client.get("/api/profile/transactions?limit=5")
    assert r.status_code == 200
    txns = r.json()
    assert len(txns) == 5
    assert txns == sorted(txns, key=lambda t: t["date"], reverse=True)


def test_put_profile_floor(client):
    r = client.put("/api/profile", json={"safety_floor_cents": 30000})
    assert r.status_code == 200
    assert r.json()["safety_floor_cents"] == 30000
    assert client.get("/api/profile").json()["safety_floor_cents"] == 30000  # persisted
    r = client.put("/api/profile", json={"safety_floor_cents": 20000})
    assert r.json()["safety_floor_cents"] == 20000


def test_baseline_no_negative_months(client):
    """§8 outcome 5: no month goes negative in the baseline."""
    r = client.get("/api/projection/baseline")
    assert r.status_code == 200
    b = r.json()
    assert b["option_id"] is None
    assert len(b["series"]) == 12
    assert b["months_negative"] == []
    assert all(pt["min_balance_cents"] >= 0 for pt in b["series"])


def test_decisions_list(client):
    r = client.get("/api/decisions")
    assert r.status_code == 200
    ids = {d["id"] for d in r.json()}
    assert "auto_insurance" in ids


def test_evaluate_state_minimum_disallowed(client):
    """§8 outcome 2: the state minimum is disallowed because the car is financed."""
    inputs = {
        "vehicle_value_cents": 950000,
        "financed": True,
        "loan_payment_cents": 21200,
        "loan_term_months": 48,
        "driver_age": 21,
        "deductible_comfort_cents": 60000,
        "registration_deadline": "2026-11-23",
    }
    r = client.post("/api/decisions/auto_insurance/evaluate", json={"inputs": inputs})
    assert r.status_code == 200
    ev = r.json()
    assert ev["eval_id"]
    by_id = {o["id"]: o for o in ev["options"]}
    assert by_id["pa_min_limited"]["status"] == "disallowed"
    assert "baseline" in ev["projections"]
    for oid in by_id:
        assert oid in ev["projections"]
    # every constraint carries at least one citation
    assert all(c["citation_ids"] for c in ev["constraints"])


def test_unknown_decision_is_error_envelope(client):
    r = client.post("/api/decisions/nope/evaluate", json={"inputs": {}})
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message"}


def test_explain_stress_action_fake_llm(client):
    r = client.post("/api/decisions/auto_insurance/explain", json={"eval_id": "eval_fixture_auto_0001"})
    assert r.status_code == 200
    assert r.json()["explanations"]

    r = client.post(
        "/api/decisions/auto_insurance/stress",
        json={"eval_id": "eval_fixture_auto_0001", "preferred_option_id": "std_limited_1000"},
    )
    assert r.status_code == 200
    s = r.json()
    assert len(s["scenarios"]) == 3
    assert s["critique"]["recommendation_shift"] in {"stay", "reconsider", "switch"}

    r = client.post(
        "/api/decisions/auto_insurance/action",
        json={"eval_id": "eval_fixture_auto_0001", "option_id": "std_full_500"},
    )
    assert r.status_code == 200
    assert r.json()["option_id"] == "std_full_500"
    assert r.json()["steps"]


def test_rag_ask_refuses_investing(client):
    r = client.post("/api/rag/ask", json={"question": "Should I put my refund in an index fund?", "module": None})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] is None
    assert body["refusal"]
    assert body["citations"] == []


def test_rag_ask_cites(client):
    r = client.post("/api/rag/ask", json={"question": "What does limited tort mean in Pennsylvania?", "module": "auto_insurance"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert body["citations"]
