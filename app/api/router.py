"""
FastAPI router — all /api/v1/* endpoints.

Endpoints:
  GET  /api/v1/health                  → liveness + configuration info
  POST /api/v1/incidents               → ingest alert, run agent pipeline
  POST /api/v1/incidents/demo          → run a canned demo scenario
  GET  /api/v1/scenarios               → list available mock alert scenarios
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.agents.graph import aiops_graph
from app.api.schemas import (
    AgentRunResponse,
    AlertIngestRequest,
    HealthResponse,
    IncidentResponse,
    RCAFindingResponse,
    RemediationStepResponse,
    ScenarioListResponse,
)
from app.config.settings import settings
from app.domain.models import Alert
from app.services.incident_service import run_incident_pipeline_async
from app.services.mock_data import generate_alert, get_all_scenarios

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["AIOps"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_incident_response(result) -> AgentRunResponse:
    """Map AgentRunResult → AgentRunResponse."""
    inc = result.incident
    return AgentRunResponse(
        incident=IncidentResponse(
            incident_id=inc.incident_id,
            severity=inc.severity,
            status=inc.status,
            environment=inc.environment,
            affected_service=inc.affected_service,
            summary=inc.summary,
            rca_findings=[
                RCAFindingResponse(
                    component=f.component,
                    finding=f.finding,
                    confidence=f.confidence,
                    evidence=f.evidence,
                )
                for f in inc.rca_findings
            ],
            remediation_steps=[
                RemediationStepResponse(
                    action=s.action.value,
                    description=s.description,
                    command=s.command,
                    estimated_duration_seconds=s.estimated_duration_seconds,
                    requires_approval=s.requires_approval,
                    priority=s.priority,
                )
                for s in inc.remediation_steps
            ],
            agent_notes=inc.agent_notes,
            execution_path=inc.execution_path,
            created_at=inc.created_at,
            resolved_at=inc.resolved_at,
        ),
        total_duration_ms=result.total_duration_ms,
        success=result.success,
        error_message=result.error_message,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, summary="Platform health check")
async def health() -> HealthResponse:
    """
    Returns platform liveness status and configuration metadata.
    Use this to verify the API is reachable and to inspect the active LLM provider.
    """
    graph_nodes = list(aiops_graph.nodes.keys())
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        llm_provider=settings.llm_provider,
        graph_nodes=graph_nodes,
    )


@router.post(
    "/incidents",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest alert and run AIOps agent pipeline",
)
async def ingest_alert(payload: AlertIngestRequest) -> AgentRunResponse:
    """
    Accept a monitoring alert, run the full LangGraph AIOps pipeline,
    and return the enriched incident with RCA findings and remediation plan.

    The pipeline runs: ingest → triage → (rca) → (remediation) → finalize
    """
    logger.info("Received alert: service=%s type=%s", payload.service, payload.alert_type)

    alert = Alert(
        source=payload.source,
        service=payload.service,
        alert_type=payload.alert_type,
        title=payload.title,
        description=payload.description,
        metric_value=payload.metric_value,
        threshold_value=payload.threshold_value,
        labels=payload.labels,
    )

    result = await run_incident_pipeline_async(alert, environment=payload.environment.value)

    if not result.success:
        logger.error("Pipeline failed for %s: %s", alert.service, result.error_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent pipeline failed: {result.error_message}",
        )

    logger.info(
        "Incident %s created — severity=%s status=%s duration=%.1fms",
        result.incident.incident_id,
        result.incident.severity.value,
        result.incident.status.value,
        result.total_duration_ms,
    )

    return _to_incident_response(result)


@router.post(
    "/incidents/demo",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a pre-built demo scenario",
)
async def run_demo_scenario(
    scenario_index: int = Query(default=0, ge=0, le=7, description="Scenario index 0–7"),
) -> AgentRunResponse:
    """
    Trigger a pre-built alert scenario through the full pipeline.
    Useful for demos, integration tests, and Streamlit walkthroughs.
    """
    alert = generate_alert(scenario_index=scenario_index)
    result = await run_incident_pipeline_async(alert)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Demo pipeline failed: {result.error_message}",
        )

    return _to_incident_response(result)


@router.get(
    "/scenarios",
    response_model=ScenarioListResponse,
    summary="List available demo alert scenarios",
)
async def list_scenarios() -> ScenarioListResponse:
    """Return metadata for all built-in demo alert scenarios."""
    scenarios = get_all_scenarios()
    return ScenarioListResponse(scenarios=scenarios, total=len(scenarios))
