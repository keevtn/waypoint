"""FastAPI entrypoint. API routes first, then the static frontend mount (SPEC.md §14)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import routes_bank, routes_decisions, routes_profile, routes_rag
from .models import HealthResponse
from .rag.index import index_chunk_count

app = FastAPI(title="Waypoint", version="0.1.0")

if config.DEV_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    """Errors are {"error": {"code", "message"}} per §7."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        body = {"error": {"code": detail["code"], "message": detail.get("message", "")}}
    else:
        body = {"error": {"code": "http_error", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=body)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, data_mode=config.DATA_MODE, index_chunks=index_chunk_count())


# One include_router line per router file; each session adds only its own (SPEC.md §15.3).
app.include_router(routes_bank.router)
app.include_router(routes_decisions.router)
app.include_router(routes_profile.router)
app.include_router(routes_rag.router)

# Static frontend last so /api/* wins. Absent in dev (vite serves it) and in CI.
if config.FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIST), html=True), name="frontend")
