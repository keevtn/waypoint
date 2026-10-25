"""Rent module (SPEC.md §6.4 "Rent module (stretch)"): constraints, commitments as the change
in housing cost, scenario menu, and the generic pipeline + fake LLM path end to end. No network."""
from __future__ import annotations

import pytest

from app.decisions import registry
from app.decisions.rent import rules
from app.rag import facts

UNITS = [
    {"label": "Studio on Beaver Ave", "rent_cents": 75000, "deposit_cents": 75000, "utilities_est_cents": 9000, "lease_months": 12, "start_date": "2027-01-01"},
    {"label": "Shared house on Garner St", "rent_cents": 55000, "deposit_cents": 55000, "utilities_est_cents": 6000, "lease_months": 12, "start_date": "2027-01-01"},
    {"label": "1BR downtown", "rent_cents": 120000, "deposit_cents": 120000, "utilities_est_cents": 10000, "lease_months": 12, "start_date": "2027-01-01"},
]


@pytest.fixture
def body(client):
    client.post("/api/bank/connect", json={})
    r = client.post("/api/decisions/rent/evaluate", json={"inputs": {"units": UNITS}})
    assert r.status_code == 200, r.text
    return r.json()


def test_rent_is_listed_with_its_input_schema(client):
    r = client.get("/api/decisions")
    rent = next(d for d in r.json() if d["id"] == "rent")
    props = rent["input_schema"]["properties"]
    assert "units" in props and props["units"]["maxItems"] == 4 and props["units"]["minItems"] == 2
    unit = rent["input_schema"]["$defs"]["RentUnit"]["properties"]
    assert {"label", "rent_cents", "deposit_cents", "utilities_est_cents", "lease_months", "start_date"} <= set(unit)


def test_inputs_need_two_to_four_units(client):
    client.post("/api/bank/connect", json={})
    assert client.post("/api/decisions/rent/evaluate", json={"inputs": {"units": UNITS[:1]}}).status_code == 422
    assert client.post("/api/decisions/rent/evaluate", json={"inputs": {"units": UNITS * 2}}).status_code == 422


def test_constraints_follow_the_30_and_45_percent_rules(body):
    # persona income: $700 biweekly + $300 monthly = $1,816.67/month -> 30% = $545, 45% = $817.50
    status = {o["id"]: o["status"] for o in body["options"]}
    assert status == {"unit_1": "disallowed", "unit_2": "flagged", "unit_3": "disallowed"}
    by_id = {c["id"]: c for c in body["constraints"]}
    assert by_id["c_housing_45pct"]["kind"] == "disallowed" and set(by_id["c_housing_45pct"]["applies_to"]) == {"unit_1", "unit_3"}
    assert by_id["c_rent_30pct"]["kind"] == "flag" and by_id["c_rent_30pct"]["applies_to"] == ["unit_2"]
    assert by_id["c_move_in_cash"]["applies_to"] == ["unit_3"]  # $2,400 move-in > $1,240 balance - $200 floor
    for c in body["constraints"]:
        assert c["citation_ids"], c["id"]
    assert facts.RENT_30_PERCENT in by_id["c_rent_30pct"]["citation_ids"]
    assert facts.RENT_30_PERCENT in by_id["c_housing_45pct"]["citation_ids"]


def test_commitment_is_the_change_in_housing_cost(body):
    opts = {o["id"]: o for o in body["options"]}
    # persona rent is $850; the shared house ($550 + $60 utilities) saves $240/month, the studio ($750 + $90) costs $10 less
    assert opts["unit_2"]["commitment"]["recurring_cents"] == 24000
    assert opts["unit_1"]["commitment"]["recurring_cents"] == 1000
    assert opts["unit_3"]["commitment"]["recurring_cents"] == -45000
    assert opts["unit_3"]["commitment"]["upfront_cents"] == 120000
    assert opts["unit_3"]["commitment"]["start_date"] == "2027-01-01"
    assert opts["unit_2"]["price"]["kind"] == "user_quote" and opts["unit_2"]["price"]["cents"] == 61000
    proj = body["projections"]
    # the deposit lands in January so the minimum can dip, but a $240/month saving beats a $550 deposit over the year
    assert proj["unit_2"]["series"][-1]["end_balance_cents"] > proj["baseline"]["series"][-1]["end_balance_cents"]
    assert proj["unit_3"]["months_negative"]  # the deposit alone exceeds the balance


def test_explicit_current_rent_overrides_the_detected_one(client):
    client.post("/api/bank/connect", json={})
    r = client.post("/api/decisions/rent/evaluate", json={"inputs": {"units": UNITS[:2], "current_rent_cents": 0}})
    assert r.status_code == 200
    opts = {o["id"]: o for o in r.json()["options"]}
    assert opts["unit_2"]["commitment"]["recurring_cents"] == -61000


def test_monthly_income_uses_cadence(body, client):
    from app.decisions import cache

    ev = cache.get(body["eval_id"])
    assert 180000 <= rules.monthly_income_cents(ev.profile) <= 183000


def test_scenario_menu_has_summer_gap(body):
    from app.decisions import cache

    ev = cache.get(body["eval_id"])
    menu = registry.get("rent").scenario_menu(ev.inputs, ev.profile)
    assert [t.id for t in menu] == ["income_gap", "shock_expense", "rent_increase", "spending_up"]
    gap = menu[0].params_schema["properties"]
    assert gap["months"]["maximum"] == 3 and gap["months"]["default"] == 2
    assert "summer" in menu[0].label.lower() or "summer" in gap["months"]["description"].lower()


def test_explain_stress_action_work_on_the_fake_path(client, body):
    eid = body["eval_id"]
    r = client.post("/api/decisions/rent/explain", json={"eval_id": eid})
    assert r.status_code == 200, r.text
    ex = {e["option_id"]: e for e in r.json()["explanations"]}
    assert set(ex) == {"unit_1", "unit_2", "unit_3"}
    assert any("[c:c_rent_30pct]" in c for c in ex["unit_2"]["cons"])
    assert ex["unit_2"]["citations"] and ex["unit_2"]["citations"][0]["chunk_id"] == facts.RENT_30_PERCENT

    r = client.post("/api/decisions/rent/stress", json={"eval_id": eid, "preferred_option_id": "unit_2"})
    assert r.status_code == 200, r.text
    s = r.json()
    assert len(s["scenarios"]) == 3
    tids = {x["scenario"]["template_id"] for x in s["scenarios"]}
    assert tids <= {"income_gap", "shock_expense", "rent_increase", "spending_up"} and "income_gap" in tids
    for x in s["scenarios"]:
        assert set(x["results"]) == {"baseline", "unit_2"}  # disallowed units are not run
    inc = next(x for x in s["scenarios"] if x["scenario"]["template_id"] == "rent_increase")
    # the increase scales the unit's own rent, so the option ends lower than its unstressed projection
    assert inc["results"]["unit_2"]["series"][-1]["end_balance_cents"] < body["projections"]["unit_2"]["series"][-1]["end_balance_cents"]
    assert s["critique"]["preferred_option_id"] == "unit_2"

    r = client.post("/api/decisions/rent/action", json={"eval_id": eid, "option_id": "unit_2"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["deadline"] == "2027-01-01" and a["steps"] and a["questions_to_ask"]
