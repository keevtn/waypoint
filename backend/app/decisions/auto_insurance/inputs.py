"""AutoInsuranceInputs (SPEC.md §6.4). The JSON schema of this model is what GET /api/decisions returns."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class UserQuote(BaseModel):
    label: str
    monthly_cents: int = Field(ge=0)
    attributes: dict[str, str | int | bool] = Field(default_factory=dict)


class AutoInsuranceInputs(BaseModel):
    state: Literal["PA"] = "PA"
    vehicle_value_cents: int = Field(ge=0)
    financed: bool
    loan_payment_cents: int | None = Field(default=None, ge=0)  # monthly; extra Commitment for all options
    loan_term_months: int | None = Field(default=None, ge=1)
    driver_age: int = Field(ge=16, le=100)
    deductible_comfort_cents: int = Field(ge=0)  # max they could pay on short notice
    registration_deadline: date | None = None
    user_quotes: list[UserQuote] = Field(default_factory=list)
