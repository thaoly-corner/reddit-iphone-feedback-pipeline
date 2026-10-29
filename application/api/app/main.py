"""BrandVoice API - serves the ten Gold marts of the Reddit iPhone VoC pipeline to the web app."""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import latency
from .config import settings
from .db import QueryStats, current_stats, get_engine
from .routers import compare, complaints, emerging, features, issues, meta, pipeline, sentiment, support, volume

app = FastAPI(
    title="BrandVoice API",
    version="1.0.0",
    description="Reddit iPhone customer-feedback analytics (CO5173). Read-only access to the PostgreSQL serving layer.",
    docs_url="/api/docs", openapi_url="/api/openapi.json",
)
PREFIX = "/api/v1"
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"], allow_headers=["*"],
)


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter()
    stats = QueryStats()
    token = current_stats.set(stats)
    try:
        response = await call_next(request)
    finally:
        current_stats.reset(token)
    total_ms = (time.perf_counter() - t0) * 1000
    route = request.scope.get("route")
    path = getattr(route, "path_format", None) or request.url.path
    path = path.removeprefix(PREFIX)
    if request.url.path.startswith(PREFIX) and path != "/pipeline/latency":
        latency.record(path, total_ms, stats.db_ms, stats.queries > 0 and stats.cache_hits == stats.queries)
    response.headers["X-Response-Ms"] = f"{total_ms:.2f}"
    return response


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": type(exc).__name__, "detail": str(exc)[:500]})


for r in (meta, volume, issues, emerging, sentiment, features, complaints, compare, support, pipeline):
    app.include_router(r.router, prefix=PREFIX)


@app.get("/api/health")
def health():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable", "backend": "sqlite" if settings.use_sqlite else "postgres"}
    except Exception as exc:  # pragma: no cover
        return JSONResponse(status_code=503, content={"status": "degraded", "database": str(exc)[:200]})
