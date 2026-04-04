"""
FastAPI dependency injection providers.

All service dependencies are defined here and injected via FastAPI's
Depends() mechanism. This keeps endpoints thin and testable — tests
can override these dependencies without modifying business logic.

Usage in a route:
    from app.dependencies import get_incident_service
    from fastapi import Depends

    @router.get("/incidents")
    async def list_incidents(svc = Depends(get_incident_service)):
        return await svc.list_all()

Stage 2 will wire these to real service implementations.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import Settings, settings


# ── Configuration ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the application settings singleton.
    lru_cache ensures only one instance exists per process.
    Override in tests with app.dependency_overrides[get_settings].
    """
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── Storage / Persistence ──────────────────────────────────────────────────────

def get_incident_service():
    """
    Provide an IncidentService instance.
    TODO Stage 2: import and return real IncidentService(storage_path=settings.incidents_file)
    """
    # from services.incident_service import IncidentService
    # return IncidentService(storage_path=settings.incidents_file)
    raise NotImplementedError("IncidentService not yet implemented — Stage 2")


def get_metrics_service():
    """
    Provide a MetricsService instance.
    TODO Stage 2: import and return real MetricsService()
    """
    raise NotImplementedError("MetricsService not yet implemented — Stage 2")


def get_jira_service():
    """
    Provide a JiraService instance (mock or real based on JIRA_ENABLED).
    TODO Stage 2: return MockJiraService() or RealJiraService() based on settings.
    """
    raise NotImplementedError("JiraService not yet implemented — Stage 2")


def get_audit_service():
    """
    Provide an AuditService instance.
    TODO Stage 2: return AuditService(log_path=settings.audit_log_file)
    """
    raise NotImplementedError("AuditService not yet implemented — Stage 2")


# ── LangGraph Pipeline ─────────────────────────────────────────────────────────

def get_aiops_graph():
    """
    Provide the compiled LangGraph AIOps workflow.
    TODO Stage 2: from graph.workflow import aiops_graph; return aiops_graph
    """
    raise NotImplementedError("AIOps graph not yet wired — Stage 2")


# ── Type aliases for clean route signatures ────────────────────────────────────
# TODO Stage 2: uncomment as services are implemented
#
# IncidentServiceDep = Annotated[IncidentService, Depends(get_incident_service)]
# MetricsServiceDep  = Annotated[MetricsService,  Depends(get_metrics_service)]
# JiraServiceDep     = Annotated[JiraService,      Depends(get_jira_service)]
