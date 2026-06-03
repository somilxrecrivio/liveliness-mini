"""FastAPI application entry point.

Mounts all routers under the configured API prefix and wires CORS, logging and
a global exception handler. Run with::

    uvicorn backend.app:app --reload
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.routes import capture, health, identity, liveness, score, verify
from backend.utils.logger import configure_logging, logger

configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Enterprise Liveness & Identity Verification System. "
        "Lightweight, training-free, CPU-only, explainable."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("{} {} -> {} ({:.0f} ms)", request.method, request.url.path,
                response.status_code, elapsed_ms)
    response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.0f}"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on {} {}: {}", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal verification error", "error": str(exc)},
    )


# Mount routers under /api/v1.
for module in (verify, capture, identity, liveness, score, health):
    app.include_router(module.router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("{} v{} started. API prefix: {}",
                settings.app_name, settings.app_version, settings.api_prefix)
