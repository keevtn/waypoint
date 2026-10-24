"""Phase 3 exit tests (SPEC.md §10 row 3, §6.4, §8 outcomes 2-4) on the generated persona."""
from __future__ import annotations

from datetime import date

import pytest

from app.bank import local_loader, persona
from app.decisions import cache, registry
from app.decisions.auto_insurance import AutoInsuranceInputs
from app.decisions.auto_insurance.options import price_for, pricing
from app.decisions.base import resolve_statuses
from app.decisions.evaluate import InvalidInputs, evaluate
from app.profile import detect

AS_OF = date(2026, 10, 24)


@pytest.fixture(scope="module")
def profile():
    data = local_loader.load(AS_OF)
    return detect.build_profile(data.transactions, data.balance_cents, data.as_of, user_one_offs=data.one_offs)


@pytest.fixture(scope="module")
def demo_inputs():
    return dict(persona.MOMENT_AUTO_INSURANCE, registration_deadline="2026-11-23")


def test_registry_and_schema():
    assert registry.get("auto_insurance") is not None and registry.get("nope") is None
    s = registry.summaries()[0]
    assert s.id == "auto_insurance"
    assert {"vehicle_value_cents", "financed", "driver_age", "deductible_comfort_cents"} <= set(s.input_schema["required"])
    assert "user_quotes" in s.input_schema["properties"]


def test_pricing_is_sourced():
    p = pricing()
    for oid in ("pa_min_limited", "std_limited_1000", "std_full_500"):
        pe = price_for(oid)
        assert pe.kind == "estimate" and pe.cents > 0
        assert pe.source_url and pe.source_url.startswith("https://") and pe.source_title and pe.retrieved
    assert "all ages" in price_for("std_full_500").source_title  # UI shows the caveat (§6.4)
    assert price_for("std_full_500").cents - price_for("std_limited_1000").cents in range(2000, 4001)  # ~$35/mo (§8.3)
    assert p["retrieved"]


def test_demo_outcomes_2_to_4(profile, demo_inputs):
    ev = evaluate(registry.get("auto_insurance"), demo_inputs, profile)
    by_id = {o.id: o for o in ev.options}
    cons = {c.id: c for c in ev.constraints}
    assert set(by_id) == {"pa_min_limited", "std_limited_1000", "std_full_500"}

    # §8.2 state minimum disallowed by the lender rule, which is cited
    assert by_id["pa_min_limited"].status == "disallowed"
    assert cons["c_lender_comp_coll"].kind == "disallowed" and cons["c_lender_comp_coll"].citation_ids
    assert "c_lender_comp_coll" in by_id["pa_min_limited"].constraint_ids
    assert by_id["std_limited_1000"].status == "flagged"
    assert {"c_deductible_comfort", "c_limited_tort"} <= set(by_id["std_limited_1000"].constraint_ids)
    assert by_id["std_full_500"].status == "allowed"
    assert all(c.citation_ids for c in ev.constraints)
    assert cons["c_pa_minimum"].kind == "required" and set(cons["c_pa_minimum"].applies_to) == set(by_id)

    # commitments: deductible is the risk exposure; loan applied to every option
    assert by_id["std_limited_1000"].commitment.risk_exposure_cents == 100000
    assert by_id["std_full_500"].commitment.risk_exposure_cents == 50000
    assert by_id["pa_min_limited"].commitment.risk_exposure_cents == 0
    assert set(ev.projections) == {"baseline", *by_id}
    base = ev.projections["baseline"]
    assert 36000 <= base.monthly_slack_cents <= 45000  # §8.1 after the car loan ~$390
    assert base.months_negative == []

    # §8.3 both standard options flag January, std_full_500 dips lower (it costs more per month)
    lim, full = ev.projections["std_limited_1000"], ev.projections["std_full_500"]
    assert "2027-01" in lim.months_below_floor and "2027-01" in full.months_below_floor
    jan_lim = next(p for p in lim.series if p.month == "2027-01")
    jan_full = next(p for p in full.series if p.month == "2027-01")
    assert jan_full.min_balance_cents < jan_lim.min_balance_cents < profile.safety_floor_cents
    jan_flag = next(f for f in lim.flags if f.code == "below_floor" and f.month == "2027-01")
    assert "Tuition installment" in {c["label"] for c in jan_flag.detail["contributors"]}
    assert {"Tuition installment", "Textbooks", "Rent"} <= {c["label"] for c in jan_flag.detail["largest_outflows"]}
    assert lim.months_negative == [] and full.months_negative == []

    # §8.4 deductible stress: $1,000 fails, $500 passes
    d_lim = next(f for f in lim.flags if f.code.startswith("deductible"))
    d_full = next(f for f in full.flags if f.code.startswith("deductible"))
    assert d_lim.code == "deductible_unaffordable" and d_lim.severity == "danger"
    assert d_lim.detail["min_balance_cents"] < profile.safety_floor_cents and d_lim.detail["deductible_cents"] == 100000
    assert d_full.code == "deductible_ok" and d_full.detail["min_balance_cents"] >= profile.safety_floor_cents
    assert not any(f.code.startswith("deductible") for f in ev.projections["pa_min_limited"].flags)

    # cached for explain/stress/action
    cached = cache.get(ev.eval_id)
    assert cached is not None and cached.module_id == "auto_insurance" and cached.inputs.financed is True
    assert set(cached.projections) == set(ev.projections)


def test_unfinanced_low_value_car_and_quotes(profile):
    inputs = {
        "vehicle_value_cents": 250000,
        "financed": False,
        "driver_age": 21,
        "deductible_comfort_cents": 150000,
        "user_quotes": [{"label": "Quote from my agent", "monthly_cents": 12000, "attributes": {"deductible": 500, "collision": True, "comprehensive": True, "tort": "full"}}],
    }
    ev = evaluate(registry.get("auto_insurance"), inputs, profile)
    by_id = {o.id: o for o in ev.options}
    cons = {c.id: c for c in ev.constraints}
    assert "c_lender_comp_coll" not in cons
    assert by_id["pa_min_limited"].status == "flagged"  # only the limited-tort flag
    assert set(cons["c_low_value_collision"].applies_to) == {"std_limited_1000", "std_full_500", "quote_1"}
    assert "c_deductible_comfort" not in cons
    q = by_id["quote_1"]
    assert q.price.kind == "user_quote" and q.price.cents == 12000 and q.commitment.recurring_cents == -12000
    assert q.commitment.risk_exposure_cents == 50000 and q.status == "flagged"
    assert ev.projections["baseline"].monthly_slack_cents == profile.monthly_slack_cents  # no loan
    assert "quote_1" in ev.projections


def test_invalid_inputs_raise():
    with pytest.raises(InvalidInputs) as e:
        evaluate(registry.get("auto_insurance"), {"financed": "maybe"}, profile=None)  # type: ignore[arg-type]
    assert any("vehicle_value_cents" in ".".join(map(str, err["loc"])) for err in e.value.errors)


def test_resolve_statuses_precedence():
    from app.models import Commitment, Constraint, Option, PriceEstimate

    def opt(i):
        return Option(id=i, label=i, attributes={}, commitment=Commitment(id=f"c{i}", label=i, start_date=AS_OF), price=PriceEstimate(cents=1, kind="estimate", source_url=None, source_title=None, retrieved=None))

    cons = [
        Constraint(id="d", kind="disallowed", applies_to=["a"], rule="", citation_ids=["x#1"]),
        Constraint(id="f", kind="flag", applies_to=["a", "b"], rule="", citation_ids=["x#1"]),
        Constraint(id="r", kind="required", applies_to=["a", "b", "c"], rule="", citation_ids=["x#1"]),
    ]
    out = {o.id: o for o in resolve_statuses([opt("a"), opt("b"), opt("c")], cons)}
    assert (out["a"].status, out["b"].status, out["c"].status) == ("disallowed", "flagged", "allowed")
    assert out["a"].constraint_ids == ["d", "f", "r"] and out["c"].constraint_ids == ["r"]


def test_scenario_menu_and_action_template(profile, demo_inputs):
    mod = registry.get("auto_insurance")
    inputs = AutoInsuranceInputs.model_validate(demo_inputs)
    menu = {t.id: t for t in mod.scenario_menu(inputs, profile)}
    assert set(menu) == {"deductible_claim", "shock_expense", "income_gap", "hours_cut", "rent_increase"}
    assert menu["shock_expense"].params_schema["properties"]["amount_cents"]["maximum"] == 150000
    option = next(o for o in mod.candidate_options(inputs, profile) if o.id == "std_full_500")
    tpl = mod.action_template(inputs, option, AS_OF)
    assert tpl["deadline"] == "2026-11-23" and "registration" in tpl["deadline_reason"].lower()
    assert any("independent agency" in s for s in tpl["steps"]) and any("lender" in s for s in tpl["steps"])
    assert any("six-month or annual" in q for q in tpl["questions_to_ask"])
    assert "100/300/50" in tpl["configuration"] and "$500" in tpl["configuration"]
    no_deadline = AutoInsuranceInputs.model_validate({**demo_inputs, "registration_deadline": None})
    assert mod.action_template(no_deadline, option, AS_OF)["deadline"] == "2026-11-23"  # as_of + 30
