"""In-memory state for the single demo user (SPEC.md §2: no auth, one user).

`connect()` ingests (local persona now; Session D plugs Plaid in behind the
same functions) and builds the Profile. `get_profile()` lazily connects in
local mode so GET /profile works even if /bank/connect was skipped.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .. import config
from ..bank import local_loader
from ..models import Profile, Transaction
from . import detect


@dataclass
class State:
    item_id: str = ""
    institution: str = ""
    as_of: date | None = None
    balance_cents: int = 0
    transactions: list[Transaction] = field(default_factory=list)
    profile: Profile | None = None
    moment: dict[str, Any] = field(default_factory=dict)


_state = State()
_lock = threading.Lock()


def connect_local(as_of: date | None = None) -> State:
    data = local_loader.load(as_of)
    profile = detect.build_profile(
        data.transactions,
        data.balance_cents,
        data.as_of,
        user_one_offs=data.one_offs,
        safety_floor_cents=data.safety_floor_cents,
        declared_income=data.declared_income,
        declared_recurring=data.declared_recurring,
    )
    with _lock:
        _state.item_id = data.item_id
        _state.institution = data.institution
        _state.as_of = data.as_of
        _state.balance_cents = data.balance_cents
        _state.transactions = sorted(data.transactions, key=lambda t: t.date, reverse=True)
        _state.profile = profile
        _state.moment = data.moment
    return _state


def connect() -> State:
    """Ingest for the configured DATA_MODE. Plaid mode falls back to local until Phase 8 lands."""
    if config.DATA_MODE == "plaid":
        try:
            from ..bank import plaid_client  # type: ignore[attr-defined]  # Phase 8 (Session D)

            return plaid_client.connect(_state)  # pragma: no cover
        except ImportError:
            pass
    return connect_local()


def get_profile() -> Profile:
    if _state.profile is None:
        connect()
    assert _state.profile is not None
    return _state.profile


def get_transactions(limit: int = 50) -> list[Transaction]:
    if _state.profile is None:
        connect()
    return _state.transactions[:limit]


EDITABLE_FIELDS = ("balance_cents", "income", "recurring", "one_offs", "safety_floor_cents")


def update_profile(patch: dict[str, Any]) -> Profile:
    """PUT /profile: a partial Profile body. `balance_cents`, `income`, `recurring`, `one_offs`
    (each list replaced whole) and `safety_floor_cents` are user-editable; everything else in the
    body (unknown keys, `as_of`, `variable`, the computed `monthly_slack_cents`) is ignored. The
    merged profile is validated by the Profile model (pydantic.ValidationError on bad input),
    slack is recomputed, and the result persists in the single-user store so /projection/baseline
    and every later /evaluate see it. POST /bank/connect rebuilds from the persona and discards edits."""
    base = get_profile()
    data = base.model_dump()
    for key in EDITABLE_FIELDS:
        if key in patch:
            data[key] = patch[key]
    new = Profile.model_validate(data)
    new = new.model_copy(update={"monthly_slack_cents": detect.compute_slack(new.income, new.recurring, new.variable)})
    with _lock:
        _state.profile = new
    return new


def set_profile(profile: Profile) -> None:
    with _lock:
        _state.profile = profile


def reset() -> None:
    """Tests only."""
    global _state
    with _lock:
        _state = State()
