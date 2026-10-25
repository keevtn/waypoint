"""Big purchase module: amortization, options, constraints, code-generated suggestions and their
guardrails, on the generated persona (as_of 2026-10-24). No network."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.bank import local_loader
from app.decisions import registry
from app.decisions.big_purchase import BigPurchaseInputs
from app.decisions.big_purchase import options as bp_options
from app.decisions.big_purchase import suggest
from app.decisions.evaluate import evaluate
from app.profile import detect
from app.projection import project

AS_OF = date(2026, 10, 24)
LAPTOP = {"name": "Laptop", "amount_cents": 180000, "date": "2026-11-01"}


@pytest.fixture(scope="module")
def profile():
    data = local_loader.load(AS_OF)
    return detect.build_profile(data.transactions, data.balance_cents, data.as_of, user_one_offs=data.one_offs)


@pytest.fixture(scope="module")
def module():
    return registry.get("big_purchase")


def test_registered_with_schema():
    s = next(s for s in registry.summaries() if s.id == "big_purchase")
    assert set(s.input_schema["required"]) == {"name", "amount_cents", "date"}
    assert "financing" in s.input_schema["properties"]
    assert {"apr_bps", "term_months", "down_payment_cents"} <= set(s.input_schema["$defs"]["Financing"]["properties"])


def test_amortization_matches_hand_computed_case():
    # $1,000 at 12% APR over 12 months: 1000 * 0.01 / (1 - 1.01^-12) = 88.8488... -> $88.85
    assert bp_options.monthly_payment_cents(100000, 1200, 12) == 8885
    # $9,500 at 6.5% APR over 48 months: 9500 * (0.065/12) * r / (1 - (1 + r)^-48) with r = 0.065/12 gives $225.29
    assert bp_options.monthly_payment_cents(950000, 650, 48) == 22529
    # 0% APR divides evenly, rounding up so the term covers the principal
    assert bp_options.monthly_payment_cents(180000, 0, 12) == 15000
    assert bp_options.monthly_payment_cents(100000, 0, 3) == 33334
    f = bp_options.plan_figures(180000, 2499, 12, 45000)
    assert f["down_payment_cents"] == 45000 and f["monthly_payment_cents"] == 12830
    assert f["total_cost_cents"] == 45000 + 12830 * 12 and f["interest_cents"] == f["total_cost_cents"] - 180000


def test_options_cash_plus_standard_terms_assumed_apr(module, profile):
    r = evaluate(module, LAPTOP, profile)
    ids = [o.id for o in r.options]
    assert ids == ["cash_now", "financed_6", "financed_12", "financed_24"]
    cash = r.options[0]
    assert cash.commitment.upfront_cents == -180000 and cash.commitment.recurring_cents == 0
    assert cash.commitment.start_date == date(2026, 11, 1) and cash.price.kind == "user_quote"
    for o in r.options[1:]:
        assert o.price.kind == "estimate" and o.price.source_title == bp_options.ASSUMED_APR_TITLE
        assert o.attributes["apr_bps"] == bp_options.ASSUMED_APR_BPS and o.attributes["apr_assumed"] is True
        assert o.commitment.recurring_cents == -o.attributes["monthly_payment_cents"]
        assert o.commitment.term_months == o.attributes["term_months"] and o.commitment.upfront_cents == 0
        assert o.attributes["interest_cents"] > 0
        assert o.status == "flagged" and f"c_interest_{o.id}" in o.constraint_ids
    assert cash.status == "allowed"  # nothing is disallowed in this module
    assert all(c.citation_ids == [] for c in r.constraints)
    assert set(r.projections) == {"baseline", *ids}


def test_user_financing_is_used_and_adds_its_term(module, profile):
    inputs = {**LAPTOP, "financing": {"apr_bps": 0, "term_months": 3, "down_payment_cents": 45000}}
    r = evaluate(module, inputs, profile)
    assert [o.id for o in r.options] == ["cash_now", "financed_3", "financed_6", "financed_12", "financed_24"]
    f3 = next(o for o in r.options if o.id == "financed_3")
    assert f3.price.kind == "user_quote" and f3.attributes["monthly_payment_cents"] == 45000
    assert f3.attributes["interest_cents"] == 0 and f3.commitment.upfront_cents == -45000


def test_low_slack_flag(module, profile):
    r = evaluate(module, {"name": "Car", "amount_cents": 2000000, "date": "2026-11-01"}, profile)
    low = next(c for c in r.constraints if c.id == "c_low_slack")
    assert set(low.applies_to) == {"financed_6", "financed_12", "financed_24"}
    for oid in low.applies_to:
        assert r.projections[oid].monthly_slack_cents < 15000


def test_earliest_safe_date_is_the_first_safe_day(module, profile):
    r = evaluate(module, LAPTOP, profile)
    assert r.projections["cash_now"].months_negative  # $1,800 against a $1,840 balance
    by_type = {s.type: s for s in r.suggestions}
    s = by_type["earliest_safe_date"]
    d = date.fromisoformat(s.patch["date"])
    assert set(s.patch) == {"date"} and d > date(2026, 11, 1)
    floor = profile.safety_floor_cents
    inputs = BigPurchaseInputs.model_validate(LAPTOP)

    def cash_min(on: date):
        res = project(profile, [bp_options.cash_option(inputs, on, AS_OF).commitment], derive_flags=False)
        return res.min_balance_cents, res.months_below_floor

    assert cash_min(d)[0] >= floor and cash_min(d)[1] == []
    prev_min, prev_below = cash_min(d - timedelta(days=1))
    assert prev_min < floor or prev_below  # the day before is not safe, so this is the first
    assert s.projected["option_id"] == "cash_now" and s.projected["min_balance_cents"] == cash_min(d)[0]
    assert s.projected["months_below_floor"] == [] and s.projected["total_cost_cents"] == 180000
    # re-submitting the patch makes the cash plan clean
    r2 = evaluate(module, {**LAPTOP, **s.patch}, profile)
    assert r2.projections["cash_now"].months_below_floor == [] and r2.suggestions == []


def test_wait_beyond_horizon_for_an_unaffordable_purchase(module, profile):
    r = evaluate(module, {"name": "Car", "amount_cents": 2000000, "date": "2026-11-01"}, profile)
    types = [s.type for s in r.suggestions]
    assert "wait_beyond_horizon" in types and "earliest_safe_date" not in types
    s = next(s for s in r.suggestions if s.type == "wait_beyond_horizon")
    assert s.patch == {}
    assert s.projected["cash_gap_cents"] == profile.safety_floor_cents - s.projected["min_balance_cents"] > 0
    assert "safest_financing" not in types  # no plan keeps the floor on a $20,000 purchase


def test_safest_financing_never_below_floor_and_is_cheapest(module, profile):
    r = evaluate(module, LAPTOP, profile)
    s = next(s for s in r.suggestions if s.type == "safest_financing")
    floor = profile.safety_floor_cents
    assert s.projected["min_balance_cents"] >= floor and s.projected["months_below_floor"] == []
    assert s.projected["monthly_slack_cents"] >= 0
    fin = s.patch["financing"]
    assert set(s.patch) == {"financing"} and fin["term_months"] in suggest.SCAN_TERMS
    assert fin["down_payment_cents"] in {180000 * p // 100 for p in suggest.SCAN_DOWN_PCTS}
    # cheapest among every scanned plan that stays safe
    inputs = BigPurchaseInputs.model_validate(LAPTOP)
    safe_totals = []
    for term in suggest.SCAN_TERMS:
        for p in suggest.SCAN_DOWN_PCTS:
            f = bp_options.Financing(apr_bps=fin["apr_bps"], term_months=term, down_payment_cents=180000 * p // 100)
            o = bp_options.financed_option(inputs, f, inputs.date, AS_OF, assumed=True)
            res = project(profile, [o.commitment], derive_flags=False)
            if res.min_balance_cents >= floor and not res.months_below_floor and res.monthly_slack_cents >= 0:
                safe_totals.append(o.attributes["total_cost_cents"])
    assert s.projected["total_cost_cents"] == min(safe_totals)
    # applying the patch yields an option with exactly that plan and a clean projection
    r2 = evaluate(module, {**LAPTOP, **s.patch}, profile)
    o = next(o for o in r2.options if o.id == s.projected["option_id"])
    assert o.attributes["total_cost_cents"] == s.projected["total_cost_cents"] and o.price.kind == "user_quote"
    assert r2.projections[o.id].months_below_floor == []


def test_suggestion_guardrails(module, profile):
    for amount in (180000, 400000, 2000000):
        r = evaluate(module, {**LAPTOP, "amount_cents": amount}, profile)
        for s in r.suggestions:
            assert "name" not in s.patch
            assert s.patch.get("amount_cents", amount) <= amount
            if s.type != "wait_beyond_horizon":
                assert s.projected["min_balance_cents"] >= profile.safety_floor_cents
                assert s.projected["months_below_floor"] == []
    # a clean cash plan produces no suggestions at all
    assert evaluate(module, {**LAPTOP, "amount_cents": 60000}, profile).suggestions == []


def test_action_template_deadline_is_the_purchase_date(module, profile):
    r = evaluate(module, LAPTOP, profile)
    inputs = BigPurchaseInputs.model_validate(LAPTOP)
    cash = module.action_template(inputs, r.options[0], AS_OF)
    fin = module.action_template(inputs, r.options[2], AS_OF)
    assert cash["deadline"] == fin["deadline"] == "2026-11-01"
    assert any("bucket" in s for s in cash["steps"]) and any("prepayment" in s.lower() for s in fin["steps"])
    assert any("APR" in s for s in fin["steps"]) and len(fin["steps"]) == 5
    menu = {t.id for t in module.scenario_menu(inputs, profile)}
    assert menu == {"shock_expense", "income_gap", "hours_cut"}


def test_api_evaluate_explain_action_fake_llm(client):
    client.post("/api/bank/connect", json={})
    r = client.post("/api/decisions/big_purchase/evaluate", json={"inputs": LAPTOP})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [o["id"] for o in body["options"]] == ["cash_now", "financed_6", "financed_12", "financed_24"]
    assert {s["type"] for s in body["suggestions"]} == {"earliest_safe_date", "safest_financing"}
    assert all(s["label"] and s["rationale"] and s["projected"]["option_id"] for s in body["suggestions"])
    eval_id = body["eval_id"]
    r = client.post("/api/decisions/big_purchase/explain", json={"eval_id": eval_id})
    assert r.status_code == 200, r.text
    assert {e["option_id"] for e in r.json()["explanations"]} == {o["id"] for o in body["options"]}
    r = client.post("/api/decisions/big_purchase/action", json={"eval_id": eval_id, "option_id": "financed_12"})
    assert r.status_code == 200, r.text
    assert r.json()["deadline"] == "2026-11-01" and r.json()["steps"]
    r = client.post("/api/decisions/big_purchase/stress", json={"eval_id": eval_id, "preferred_option_id": "financed_12"})
    assert r.status_code == 200, r.text
    assert len(r.json()["scenarios"]) == 3
    assert {s["scenario"]["template_id"] for s in r.json()["scenarios"]} <= {"shock_expense", "income_gap", "hours_cut"}
    assert client.post("/api/decisions/big_purchase/evaluate", json={"inputs": {"name": "x", "amount_cents": -5, "date": "2026-11-01"}}).status_code == 422
