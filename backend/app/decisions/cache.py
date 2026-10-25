"""eval_id -> Evaluation cache (SPEC.md §7: TTL 1h).

Two layers: a process-local dict for speed, and a sqlite table (`config.DB_PATH`) written
through on every `put` and read back on a miss, so a restart or redeploy between
/evaluate and /explain|/stress|/action does not lose the evaluation. explain/stress/action
read the cached evaluation instead of recomputing or re-sending inputs.

Rows store pydantic JSON dumps; `inputs` is rehydrated through the module's InputModel from
the registry. If the database is unavailable (read-only disk), the cache degrades to memory
only and logs once.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..models import Commitment, Constraint, Option, Profile, ProjectionResult, Suggestion

log = logging.getLogger(__name__)

TTL_SECONDS = 3600
_TABLE = "evaluations"


@dataclass
class Evaluation:
    eval_id: str
    module_id: str
    inputs: Any  # the module's InputModel instance
    profile: Profile
    options: list[Option]
    constraints: list[Constraint]
    extra_commitments: list[Commitment]
    projections: dict[str, ProjectionResult]
    created: float = field(default_factory=time.time)
    suggestions: list[Suggestion] = field(default_factory=list)


_store: dict[str, Evaluation] = {}
_lock = threading.Lock()
_db_ready = False
_db_failed = False


def new_id() -> str:
    return f"eval_{uuid.uuid4().hex[:12]}"


def put(ev: Evaluation) -> None:
    with _lock:
        _evict()
        _store[ev.eval_id] = ev
        _db_put(ev)


def get(eval_id: str) -> Evaluation | None:
    with _lock:
        _evict()
        ev = _store.get(eval_id)
        if ev is None:
            ev = _db_get(eval_id)
            if ev is not None:
                _store[eval_id] = ev
        return ev


def clear() -> None:
    """Drop both layers (tests)."""
    with _lock:
        _store.clear()
        con = _connect()
        if con is not None:
            with con:
                con.execute(f"DELETE FROM {_TABLE}")
            con.close()


def forget_memory() -> None:
    """Drop only the in-process layer, simulating a restart (tests)."""
    with _lock:
        _store.clear()


def _evict() -> None:
    cutoff = time.time() - TTL_SECONDS
    for k in [k for k, v in _store.items() if v.created < cutoff]:
        del _store[k]
    con = _connect()
    if con is not None:
        try:
            with con:
                con.execute(f"DELETE FROM {_TABLE} WHERE created < ?", (cutoff,))
        except sqlite3.Error as e:  # pragma: no cover - disk trouble
            log.warning("eval cache: evict failed: %s", e)
        finally:
            con.close()


# -- sqlite layer ---------------------------------------------------------------------


def _connect() -> sqlite3.Connection | None:
    global _db_ready, _db_failed
    if _db_failed:
        return None
    try:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(config.DB_PATH, timeout=5)
        if not _db_ready:
            with con:
                con.execute(
                    f"CREATE TABLE IF NOT EXISTS {_TABLE} (eval_id TEXT PRIMARY KEY, module_id TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL)"
                )
                con.execute(f"CREATE INDEX IF NOT EXISTS {_TABLE}_created ON {_TABLE}(created)")
            _db_ready = True
        return con
    except (sqlite3.Error, OSError) as e:
        _db_failed = True
        log.warning("eval cache: sqlite unavailable at %s (%s); memory only", config.DB_PATH, e)
        return None


def _dump(ev: Evaluation) -> str:
    return json.dumps(
        {
            "inputs": ev.inputs.model_dump(mode="json"),
            "profile": ev.profile.model_dump(mode="json"),
            "options": [o.model_dump(mode="json") for o in ev.options],
            "constraints": [c.model_dump(mode="json") for c in ev.constraints],
            "extra_commitments": [c.model_dump(mode="json") for c in ev.extra_commitments],
            "projections": {k: p.model_dump(mode="json") for k, p in ev.projections.items()},
            "suggestions": [s.model_dump(mode="json") for s in ev.suggestions],
        },
        separators=(",", ":"),
    )


def _load(eval_id: str, module_id: str, created: float, payload: str) -> Evaluation | None:
    from . import registry

    module = registry.get(module_id)
    if module is None:
        return None
    d = json.loads(payload)
    return Evaluation(
        eval_id=eval_id,
        module_id=module_id,
        inputs=module.InputModel.model_validate(d["inputs"]),
        profile=Profile.model_validate(d["profile"]),
        options=[Option.model_validate(o) for o in d["options"]],
        constraints=[Constraint.model_validate(c) for c in d["constraints"]],
        extra_commitments=[Commitment.model_validate(c) for c in d["extra_commitments"]],
        projections={k: ProjectionResult.model_validate(p) for k, p in d["projections"].items()},
        created=created,
        suggestions=[Suggestion.model_validate(s) for s in d.get("suggestions", [])],
    )


def _db_put(ev: Evaluation) -> None:
    con = _connect()
    if con is None:
        return
    try:
        with con:
            con.execute(
                f"INSERT OR REPLACE INTO {_TABLE} (eval_id, module_id, created, payload) VALUES (?, ?, ?, ?)",
                (ev.eval_id, ev.module_id, ev.created, _dump(ev)),
            )
    except sqlite3.Error as e:
        log.warning("eval cache: write failed for %s: %s", ev.eval_id, e)
    finally:
        con.close()


def _db_get(eval_id: str) -> Evaluation | None:
    con = _connect()
    if con is None:
        return None
    try:
        row = con.execute(f"SELECT module_id, created, payload FROM {_TABLE} WHERE eval_id = ?", (eval_id,)).fetchone()
    except sqlite3.Error as e:
        log.warning("eval cache: read failed for %s: %s", eval_id, e)
        return None
    finally:
        con.close()
    if row is None or row[1] < time.time() - TTL_SECONDS:
        return None
    try:
        return _load(eval_id, row[0], row[1], row[2])
    except Exception as e:  # a contract change since the row was written
        log.warning("eval cache: could not rehydrate %s: %s", eval_id, e)
        return None
