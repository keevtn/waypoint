"""Product lookup route (Session A): POST /api/products/lookup reads a product page server-side
(products/lookup.py: SSRF-guarded fetch, JSON-LD > Open Graph > <title> parse) so the big-purchase
form can prefill name and price. Errors use the §7 envelope: 400 invalid_url / blocked_url,
502 fetch_failed / unreachable."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import ProductLookupRequest, ProductLookupResponse
from ..products import lookup

router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("/lookup", response_model=ProductLookupResponse)
def product_lookup(body: ProductLookupRequest) -> ProductLookupResponse:
    try:
        return lookup.lookup(body.url)
    except lookup.ProductLookupError as e:
        status = 400 if e.code in ("invalid_url", "blocked_url") else 502
        raise HTTPException(status_code=status, detail={"code": e.code, "message": str(e)})
