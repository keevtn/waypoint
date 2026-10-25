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
    assert body["index_chunks"] > 0  # corpus indexed (FakeEmbedder under LLM_FAKE=1)


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
    assert 55000 <= p["monthly_slack_cents"] <= 66000  # §8 outcome 1: ~$600
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



def test_put_profile_balance_reflects_in_baseline(client):
    client.post("/api/bank/connect", json={})
    before = client.get("/api/projection/baseline").json()
    p = client.get("/api/profile").json()
    r = client.put("/api/profile", json={"balance_cents": p["balance_cents"] + 50000, "ignored_key": 1, "monthly_slack_cents": 1, "as_of": "1999-01-01"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["balance_cents"] == p["balance_cents"] + 50000
    assert body["as_of"] == p["as_of"] and body["monthly_slack_cents"] == p["monthly_slack_cents"]  # computed/unknown fields ignored
    after = client.get("/api/projection/baseline").json()
    assert after["min_balance_cents"] == before["min_balance_cents"] + 50000
    assert after["series"][0]["end_balance_cents"] == before["series"][0]["end_balance_cents"] + 50000
    client.post("/api/bank/connect", json={})


def test_put_profile_replaces_lists_and_recomputes_slack(client):
    client.post("/api/bank/connect", json={})
    p = client.get("/api/profile").json()
    # drop every recurring item but rent and halve its amount; add a second income stream; one one-off
    rent = next(r for r in p["recurring"] if "rent" in r["label"].lower())
    rent = {**rent, "amount_cents": rent["amount_cents"] // 2}
    extra = {"id": "inc_tutoring", "label": "Tutoring", "amount_cents": 20000, "cadence": "monthly", "next_date": "2026-11-05", "confidence": 1.0}
    r = client.put("/api/profile", json={"recurring": [rent], "income": [*p["income"], extra], "one_offs": [{"id": "oo_x", "label": "Books", "amount_cents": -5000, "date": "2026-12-01", "source": "user"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["id"] for x in body["recurring"]] == [rent["id"]] and body["recurring"][0]["amount_cents"] == rent["amount_cents"]
    assert [x["id"] for x in body["income"]][-1] == "inc_tutoring" and len(body["income"]) == len(p["income"]) + 1
    assert [x["id"] for x in body["one_offs"]] == ["oo_x"]
    from app.models import Profile
    from app.profile.detect import compute_slack

    prof = Profile.model_validate(body)
    assert body["monthly_slack_cents"] == compute_slack(prof.income, prof.recurring, prof.variable) != p["monthly_slack_cents"]
    monthly_rec = {x["id"]: x for x in p["recurring"] if x["cadence"] == "monthly"}
    if set(monthly_rec) == {x["id"] for x in p["recurring"]}:  # persona: every recurring item is monthly, so the delta is exact
        removed = sum(-x["amount_cents"] for x in p["recurring"]) + rent["amount_cents"]  # rent's new (halved) amount stays
        assert body["monthly_slack_cents"] == p["monthly_slack_cents"] + removed + 20000
    assert client.get("/api/profile").json()["monthly_slack_cents"] == body["monthly_slack_cents"]  # persisted
    # a later /evaluate uses the edited profile
    ev = client.post("/api/decisions/big_purchase/evaluate", json={"inputs": {"name": "Laptop", "amount_cents": 180000, "date": "2026-11-01"}}).json()
    assert ev["projections"]["baseline"]["monthly_slack_cents"] == body["monthly_slack_cents"]
    # bad bodies are 422, and leave the stored profile untouched
    r = client.put("/api/profile", json={"income": [{"id": "bad"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_profile"
    assert client.put("/api/profile", json={"recurring": [{**rent, "cadence": "yearly"}]}).status_code == 422
    assert client.get("/api/profile").json()["monthly_slack_cents"] == body["monthly_slack_cents"]
    client.post("/api/bank/connect", json={})


def test_bank_connect_resets_profile_edits(client):
    client.post("/api/bank/connect", json={})
    persona = client.get("/api/profile").json()
    client.put("/api/profile", json={"balance_cents": 1, "recurring": [], "income": [], "one_offs": [], "safety_floor_cents": 99900})
    edited = client.get("/api/profile").json()
    assert edited["balance_cents"] == 1 and edited["recurring"] == [] and edited["monthly_slack_cents"] != persona["monthly_slack_cents"]
    r = client.post("/api/bank/connect", json={})
    assert r.status_code == 200
    assert client.get("/api/profile").json() == persona
    assert client.get("/api/projection/baseline").json()["monthly_slack_cents"] == persona["monthly_slack_cents"]

def test_baseline_no_negative_months(client):
    """§8 outcome 5: no month goes negative in the baseline."""
    r = client.get("/api/projection/baseline")
    assert r.status_code == 200
    b = r.json()
    assert b["option_id"] is None
    assert len(b["series"]) == 12
    assert b["months_negative"] == []
    assert all(pt["min_balance_cents"] >= 0 for pt in b["series"])
    # Phase 2: computed, not a fixture
    assert b["months_below_floor"] == []
    assert all(pt["min_balance_date"][:7] == pt["month"] for pt in b["series"])
    assert all(pt["inflow_cents"] > 0 and pt["outflow_cents"] > 0 for pt in b["series"])
    assert b["series"][-1]["end_balance_cents"] > b["series"][0]["end_balance_cents"]
    assert 55000 <= b["monthly_slack_cents"] <= 66000
    assert not any(f["code"] in {"below_floor", "negative"} for f in b["flags"])


def test_decisions_list(client):
    r = client.get("/api/decisions")
    assert r.status_code == 200
    ids = {d["id"] for d in r.json()}
    assert "auto_insurance" in ids
    auto = next(d for d in r.json() if d["id"] == "auto_insurance")
    assert "financed" in auto["input_schema"]["properties"]
    assert "rent" in ids  # SPEC §6.4 stretch module, registered
    rent = next(d for d in r.json() if d["id"] == "rent")
    assert "units" in rent["input_schema"]["properties"]
    assert "big_purchase" in ids  # Session A big-purchase module, registered
    bp = next(d for d in r.json() if d["id"] == "big_purchase")
    assert {"name", "amount_cents", "date", "financing"} <= set(bp["input_schema"]["properties"])


def test_evaluate_big_purchase_suggests_alternatives(client):
    """A cash purchase that breaks the floor comes back with code-generated alternatives."""
    inputs = {"name": "Laptop", "amount_cents": 180000, "date": "2026-11-01"}
    r = client.post("/api/decisions/big_purchase/evaluate", json={"inputs": inputs})
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev["eval_id"] and "baseline" in ev["projections"]
    assert {o["id"] for o in ev["options"]} == {"cash_now", "financed_6", "financed_12", "financed_24"}
    assert all(o["status"] != "disallowed" for o in ev["options"])
    assert ev["projections"]["cash_now"]["months_negative"]  # $1,800 against the persona's balance
    types = {s["type"] for s in ev["suggestions"]}
    assert types == {"earliest_safe_date", "safest_financing"}
    floor = client.get("/api/profile").json()["safety_floor_cents"]
    for s in ev["suggestions"]:
        assert s["projected"]["min_balance_cents"] >= floor and s["projected"]["months_below_floor"] == []
        assert "name" not in s["patch"]
    # the auto module is unchanged by the contract: no suggestions there
    assert "suggestions" in ev


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
    # Phase 3: computed by the real pipeline
    lender = next(c for c in ev["constraints"] if c["id"] == "c_lender_comp_coll")
    assert lender["kind"] == "disallowed" and "pa_min_limited" in lender["applies_to"]
    assert by_id["std_limited_1000"]["status"] == "flagged" and by_id["std_full_500"]["status"] == "flagged"  # Jan-Mar below floor
    assert any(c["id"] == "below_floor_std_full_500" and c["kind"] == "flag" for c in ev["constraints"])
    assert all(o["price"]["source_url"] and o["price"]["source_title"] for o in ev["options"])  # never "Unsourced"
    assert ev["projections"]["baseline"]["months_negative"] == []
    # §8 outcome 3: both standard options flag January; the $500/full-tort option dips lower
    lim, full = ev["projections"]["std_limited_1000"], ev["projections"]["std_full_500"]
    assert "2027-01" in lim["months_below_floor"] and "2027-01" in full["months_below_floor"]
    assert full["min_balance_cents"] < lim["min_balance_cents"]
    # §8 outcome 4: $1,000 deductible fails the stress test, $500 passes
    assert any(f["code"] == "deductible_unaffordable" for f in lim["flags"])
    assert any(f["code"] == "deductible_ok" for f in full["flags"])
    assert len(ev["projections"]["std_full_500"]["series"]) == 12


def test_evaluate_rejects_bad_inputs(client):
    r = client.post("/api/decisions/auto_insurance/evaluate", json={"inputs": {"financed": True}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_inputs"


def test_unknown_decision_is_error_envelope(client):
    r = client.post("/api/decisions/nope/evaluate", json={"inputs": {}})
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message"}


def _eval_id(client) -> str:
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
    return r.json()["eval_id"]


def test_explain_stress_action_fake_llm(client):
    eval_id = _eval_id(client)
    r = client.post("/api/decisions/auto_insurance/explain", json={"eval_id": eval_id})
    assert r.status_code == 200
    assert r.json()["explanations"]
    # Phase 6: explanations come from the LLM layer on the cached evaluation, citations rebuilt from the index
    exps = {e["option_id"]: e for e in r.json()["explanations"]}
    assert "std_limited_1000" in exps and "std_full_500" in exps
    assert all(e["verdict"] for e in exps.values())
    assert all(c["url"] and c["publisher"] for e in exps.values() for c in e["citations"])
    assert client.post("/api/decisions/auto_insurance/explain", json={"eval_id": "eval_expired"}).status_code == 404

    r = client.post(
        "/api/decisions/auto_insurance/stress",
        json={"eval_id": eval_id, "preferred_option_id": "std_limited_1000"},
    )
    assert r.status_code == 200
    s = r.json()
    assert len(s["scenarios"]) == 3
    assert s["critique"]["recommendation_shift"] in {"stay", "reconsider", "switch"}

    r = client.post(
        "/api/decisions/auto_insurance/action",
        json={"eval_id": eval_id, "option_id": "std_full_500"},
    )
    assert r.status_code == 200
    assert r.json()["option_id"] == "std_full_500"
    assert r.json()["steps"]
    # Phase 6: deadline and reason come from code (registration deadline), never the model
    card = r.json()
    assert card["deadline"] == "2026-11-23"
    assert card["headline"]
    assert any("quote" in s.lower() for s in card["steps"]) and any("lender" in s.lower() for s in card["steps"])
    assert card["questions_to_ask"]


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


def test_rag_ask_cites_tort_chunk(client):
    """§11: limited tort -> cited answer from the PA Insurance Department chunk."""
    from app.rag.facts import PA_TORT

    r = client.post("/api/rag/ask", json={"question": "What does limited tort mean in Pennsylvania?", "module": "auto_insurance"})
    body = r.json()
    assert body["refusal"] is None
    assert PA_TORT in {c["chunk_id"] for c in body["citations"]}
    assert f"[s:{PA_TORT}]" in body["answer"]
    assert all(c["publisher"] and c["url"] for c in body["citations"])


def test_rag_ask_no_source_refusal(client):
    """§11: off-corpus question -> no-source refusal, no citations."""
    r = client.post("/api/rag/ask", json={"question": "Does PA require insurance on a bicycle?", "module": "auto_insurance"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] is None
    assert body["refusal"] == "I don't have a trusted source for that, so I won't guess."
    assert body["citations"] == []
