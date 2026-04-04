"""
Enterprise AIOps LangGraph Platform — FastAPI entry point.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Interactive API docs:
    http://localhost:8000/docs      (Swagger UI)
    http://localhost:8000/redoc     (ReDoc)
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config.settings import settings

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks."""
    logger.info("─" * 60)
    logger.info("  %s  v%s", settings.app_name, settings.app_version)
    logger.info("  LLM provider : %s", settings.llm_provider)
    logger.info("  Auto-remediation: %s", settings.auto_remediation_enabled)
    logger.info("  API: http://%s:%s/docs", settings.api_host, settings.api_port)
    logger.info("─" * 60)

    # Eagerly import the graph to surface any import errors at startup
    from app.agents.graph import aiops_graph  # noqa: F401
    logger.info("LangGraph pipeline compiled successfully.")

    yield

    logger.info("%s shutting down.", settings.app_name)


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Enterprise AIOps platform powered by LangGraph. "
        "Ingests monitoring alerts, runs a multi-node agent pipeline "
        "(triage → RCA → remediation), and returns structured incident reports."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
