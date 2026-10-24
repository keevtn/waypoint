"""eval_id -> evaluation payload cache (SPEC.md §7: in-memory, TTL 1h).

explain/stress/action (Wave 2) read the cached evaluation instead of recomputing
or re-sending inputs.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..models import Commitment, Constraint, Option, Profile, ProjectionResult

TTL_SECONDS = 3600


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


_store: dict[str, Evaluation] = {}
_lock = threading.Lock()


def new_id() -> str:
    return f"eval_{uuid.uuid4().hex[:12]}"


def put(ev: Evaluation) -> None:
    with _lock:
        _evict()
        _store[ev.eval_id] = ev


def get(eval_id: str) -> Evaluation | None:
    with _lock:
        _evict()
        return _store.get(eval_id)


def _evict() -> None:
    cutoff = time.time() - TTL_SECONDS
    for k in [k for k, v in _store.items() if v.created < cutoff]:
        del _store[k]


def clear() -> None:
    with _lock:
        _store.clear()
