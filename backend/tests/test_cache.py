"""Evaluation cache persistence: write-through to sqlite on evaluate, read-back on a memory
miss (simulated restart), 1h TTL honoured in both layers. No network."""
from __future__ import annotations

import sqlite3
import time

from app import config
from app.decisions import cache

INPUTS = {
    "vehicle_value_cents": 950000,
    "financed": True,
    "loan_payment_cents": 21200,
    "loan_term_months": 48,
    "driver_age": 21,
    "deductible_comfort_cents": 60000,
    "registration_deadline": "2026-11-23",
}


def _evaluate(client, module="auto_insurance", inputs=INPUTS) -> str:
    client.post("/api/bank/connect", json={})
    r = client.post(f"/api/decisions/{module}/evaluate", json={"inputs": inputs})
    assert r.status_code == 200, r.text
    return r.json()["eval_id"]


def test_db_path_is_isolated_for_tests():
    assert "waypoint-test-" in str(config.DB_PATH)


def test_evaluate_writes_through_and_survives_a_restart(client):
    eid = _evaluate(client)
    before = cache.get(eid)
    assert before is not None
    with sqlite3.connect(config.DB_PATH) as con:
        row = con.execute("SELECT module_id, created FROM evaluations WHERE eval_id = ?", (eid,)).fetchone()
    assert row is not None and row[0] == "auto_insurance" and abs(row[1] - before.created) < 1e-6

    cache.forget_memory()  # "server restarted"
    after = cache.get(eid)
    assert after is not None
    assert after.module_id == "auto_insurance"
    assert after.inputs == before.inputs  # rehydrated through the module's InputModel
    assert after.profile == before.profile
    assert after.options == before.options
    assert after.constraints == before.constraints
    assert after.extra_commitments == before.extra_commitments
    assert after.projections == before.projections


def test_explain_stress_action_work_after_restart(client):
    eid = _evaluate(client)
    cache.forget_memory()
    assert client.post("/api/decisions/auto_insurance/explain", json={"eval_id": eid}).status_code == 200
    cache.forget_memory()
    assert client.post("/api/decisions/auto_insurance/stress", json={"eval_id": eid, "preferred_option_id": "std_limited_1000"}).status_code == 200
    cache.forget_memory()
    assert client.post("/api/decisions/auto_insurance/action", json={"eval_id": eid, "option_id": "std_full_500"}).status_code == 200


def test_rent_evaluations_rehydrate_with_their_own_input_model(client):
    units = [
        {"label": "A", "rent_cents": 55000, "deposit_cents": 55000, "utilities_est_cents": 6000, "lease_months": 12, "start_date": "2027-01-01"},
        {"label": "B", "rent_cents": 75000, "deposit_cents": 75000, "utilities_est_cents": 9000, "lease_months": 12, "start_date": "2027-01-01"},
    ]
    eid = _evaluate(client, "rent", {"units": units})
    cache.forget_memory()
    ev = cache.get(eid)
    assert ev is not None and type(ev.inputs).__name__ == "RentInputs" and len(ev.inputs.units) == 2


def test_ttl_applies_to_both_layers(client):
    eid = _evaluate(client)
    old = time.time() - cache.TTL_SECONDS - 5
    with sqlite3.connect(config.DB_PATH) as con:
        con.execute("UPDATE evaluations SET created = ? WHERE eval_id = ?", (old, eid))
    cache.forget_memory()
    assert cache.get(eid) is None  # expired row is not served
    with sqlite3.connect(config.DB_PATH) as con:
        assert con.execute("SELECT COUNT(*) FROM evaluations WHERE eval_id = ?", (eid,)).fetchone()[0] == 0  # and was evicted
    assert client.post("/api/decisions/auto_insurance/explain", json={"eval_id": eid}).status_code == 404


def test_unknown_or_corrupt_rows_are_a_miss(client):
    with sqlite3.connect(config.DB_PATH) as con:
        con.execute("INSERT OR REPLACE INTO evaluations VALUES (?, ?, ?, ?)", ("eval_corrupt", "auto_insurance", time.time(), "{}"))
        con.execute("INSERT OR REPLACE INTO evaluations VALUES (?, ?, ?, ?)", ("eval_nomodule", "gone", time.time(), "{}"))
    assert cache.get("eval_corrupt") is None
    assert cache.get("eval_nomodule") is None
    assert cache.get("eval_missing") is None


def test_memory_only_when_db_unavailable(client, monkeypatch, tmp_path):
    bad = tmp_path / "not-a-dir.txt"
    bad.write_text("x")
    monkeypatch.setattr(config, "DB_PATH", bad / "waypoint.db")  # parent is a file -> cannot create
    monkeypatch.setattr(cache, "_db_ready", False)
    monkeypatch.setattr(cache, "_db_failed", False)
    eid = _evaluate(client)
    assert cache.get(eid) is not None  # still served from memory
    assert cache._db_failed is True
    cache.forget_memory()
    assert cache.get(eid) is None
    monkeypatch.setattr(cache, "_db_failed", False)
    monkeypatch.setattr(cache, "_db_ready", False)
