"""
Enterprise AIOps Platform — FastAPI application entry point.

This module boots the FastAPI application, registers all routers,
configures middleware, and manages startup/shutdown lifecycle hooks.

Run locally:
    uvicorn app.main:app --reload --port 8000

Docker:
    docker build -t aiops-platform . && docker run -p 8000:8000 aiops-platform
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logger import configure_logging

# ── Logging ───────────────────────────────────────────────────────────────────
configure_logging()
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown hooks for the AIOps platform."""
    logger.info("=" * 60)
    logger.info("  %s  v%s  [%s]", settings.app_name, settings.app_version, settings.environment)
    logger.info("  LLM provider  : %s", settings.llm_provider)
    logger.info("  Storage       : %s", settings.storage_dir)
    logger.info("  Docs          : http://localhost:%s/docs", settings.api_port)
    logger.info("=" * 60)

    # TODO Stage 2: initialise LangGraph graph, warm up agents, load storage indexes
    yield

    logger.info("%s shutting down cleanly.", settings.app_name)


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Self-healing AIOps platform. Multi-agent pipeline: monitoring → "
        "log analysis → incident classification → auto-remediation → validation → Jira reporting."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.router import router as api_router
app.include_router(api_router)

from app.api.aws_router import router as aws_router
app.include_router(aws_router)


# ── Built-in endpoints ────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    return JSONResponse({
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    })


@app.get("/health", tags=["Platform"])
async def health() -> dict:
    """
    Platform liveness probe.
    Returns basic config info — suitable for Kubernetes readiness checks.
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
    }
