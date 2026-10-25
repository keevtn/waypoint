"""RentInputs (SPEC.md §6.4 "Rent module (stretch)"). The JSON schema of this model is what
GET /api/decisions returns for the rent module; Session B builds the form from it."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RentUnit(BaseModel):
    label: str = Field(description="How you refer to this unit, e.g. 'Studio on Beaver Ave'")
    rent_cents: int = Field(ge=0, description="Monthly rent in cents")
    deposit_cents: int = Field(default=0, ge=0, description="Security deposit due at signing, in cents")
    utilities_est_cents: int = Field(default=0, ge=0, description="Estimated monthly utilities not included in rent, in cents")
    lease_months: int = Field(default=12, ge=1, le=36)
    start_date: date = Field(description="Lease start; first month's rent and the deposit are due then")


class RentInputs(BaseModel):
    units: list[RentUnit] = Field(min_length=2, max_length=4, description="2 to 4 candidate units to compare")
    current_rent_cents: int | None = Field(
        default=None,
        ge=0,
        description="What you pay now, in cents. Leave empty to use the rent detected in your transactions; 0 if you pay no rent today.",
    )
