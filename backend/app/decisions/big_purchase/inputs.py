"""BigPurchaseInputs (SPEC.md §6.4 module pattern). The JSON schema of this model is what
GET /api/decisions returns for the big_purchase module; Session B builds the form from it."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class Financing(BaseModel):
    apr_bps: int = Field(ge=0, le=10000, description="Annual percentage rate in basis points (2499 = 24.99%). 0 allowed.")
    term_months: int = Field(ge=1, le=84, description="Number of monthly payments")
    down_payment_cents: int = Field(default=0, ge=0, description="Paid upfront on the purchase date, in cents")


class BigPurchaseInputs(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="What you are buying, e.g. 'Laptop'")
    amount_cents: int = Field(gt=0, description="Full price in cents")
    date: dt.date = Field(description="When you would buy it (or when financing would start)")
    financing: Financing | None = Field(default=None, description="Your lender's terms, if you have an offer. Leave empty to see assumed-rate plans.")
