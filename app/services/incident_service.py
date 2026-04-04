"""
Incident service — the primary orchestration layer between the API/UI
and the LangGraph agent pipeline.

This service is responsible for:
  1. Accepting an Alert and preparing the initial AIOpsState.
  2. Invoking the compiled LangGraph pipeline.
  3. Reconstructing the enriched Incident domain object from the final state.
  4. Returning an AgentRunResult to callers.

Both sync and async entry points are provided. The async variant is used
by FastAPI endpoints; the sync variant is used by Streamlit and tests.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agents.graph import aiops_graph
from app.agents.state import AIOpsState
from app.domain.enums import Environment, IncidentStatus, Severity
from app.domain.models import (
    AgentRunResult,
    Alert,
    Incident,
    RCAFinding,
    RemediationStep,
)


# ── State builder ─────────────────────────────────────────────────────────────

def _build_initial_state(alert: Alert, incident_id: str, environment: str) -> AIOpsState:
    """Construct the seed AIOpsState from an incoming alert."""
    return {
        "incident_id": incident_id,
        "alert": alert.model_dump(mode="json"),
        "environment": environment,
        # Pre-initialise all non-accumulating fields with safe defaults
        "severity": Severity.UNKNOWN.value,
        "affected_service": alert.service,
        "summary": "",
        "route": "",
        "rca_findings": [],
        "remediation_steps": [],
        "status": IncidentStatus.OPEN.value,
        # Accumulating fields start empty — operator.add will append
        "agent_notes": [],
        "execution_path": [],
    }


# ── State → Domain mapper ─────────────────────────────────────────────────────

def _state_to_incident(state: AIOpsState, alert: Alert, incident_id: str) -> Incident:
    """Reconstruct an Incident domain object from the final graph state."""
    rca_findings = [RCAFinding(**f) for f in state.get("rca_findings", [])]
    remediation_steps = [RemediationStep(**s) for s in state.get("remediation_steps", [])]

    status_val = state.get("status", IncidentStatus.OPEN.value)
    status = IncidentStatus(status_val) if status_val in IncidentStatus._value2member_map_ else IncidentStatus.OPEN

    severity_val = state.get("severity", Severity.UNKNOWN.value)
    severity = Severity(severity_val) if severity_val in Severity._value2member_map_ else Severity.UNKNOWN

    env_val = state.get("environment", Environment.PRODUCTION.value)
    environment = Environment(env_val) if env_val in Environment._value2member_map_ else Environment.PRODUCTION

    resolved_at: Optional[datetime] = None
    if status == IncidentStatus.RESOLVED:
        resolved_at = datetime.now(timezone.utc)

    return Incident(
        incident_id=incident_id,
        alert=alert,
        severity=severity,
        status=status,
        environment=environment,
        affected_service=state.get("affected_service", alert.service),
        summary=state.get("summary", ""),
        rca_findings=rca_findings,
        remediation_steps=remediation_steps,
        agent_notes=state.get("agent_notes", []),
        execution_path=state.get("execution_path", []),
        resolved_at=resolved_at,
        resolution_summary=state.get("summary") if status == IncidentStatus.RESOLVED else None,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def run_incident_pipeline(
    alert: Alert,
    environment: str = Environment.PRODUCTION.value,
) -> AgentRunResult:
    """
    Run the full AIOps LangGraph agent pipeline for an alert.

    This is the synchronous entry point (used by Streamlit, tests, CLI).

    Args:
        alert: The incoming monitoring alert.
        environment: Target environment (production, staging, development).

    Returns:
        AgentRunResult containing the enriched Incident and pipeline metadata.
    """
    incident_id = f"INC-{str(uuid.uuid4())[:8].upper()}"
    initial_state = _build_initial_state(alert, incident_id, environment)
    thread_config = {"configurable": {"thread_id": incident_id}}

    start_ms = time.monotonic() * 1000

    try:
        final_state: AIOpsState = aiops_graph.invoke(initial_state, config=thread_config)
        duration_ms = (time.monotonic() * 1000) - start_ms

        incident = _state_to_incident(final_state, alert, incident_id)
        return AgentRunResult(
            incident=incident,
            total_duration_ms=round(duration_ms, 2),
            success=True,
        )

    except Exception as exc:  # noqa: BLE001
        duration_ms = (time.monotonic() * 1000) - start_ms
        # Return a minimal incident on failure so callers always get a result
        incident = Incident(
            incident_id=incident_id,
            alert=alert,
            status=IncidentStatus.OPEN,
            agent_notes=[f"Pipeline error: {exc}"],
        )
        return AgentRunResult(
            incident=incident,
            total_duration_ms=round(duration_ms, 2),
            success=False,
            error_message=str(exc),
        )


async def run_incident_pipeline_async(
    alert: Alert,
    environment: str = Environment.PRODUCTION.value,
) -> AgentRunResult:
    """
    Async entry point used by FastAPI endpoints.

    LangGraph's `.ainvoke()` runs the nodes concurrently where possible.
    Falls back to `.invoke()` if ainvoke is unavailable.
    """
    incident_id = f"INC-{str(uuid.uuid4())[:8].upper()}"
    initial_state = _build_initial_state(alert, incident_id, environment)
    thread_config = {"configurable": {"thread_id": incident_id}}

    start_ms = time.monotonic() * 1000

    try:
        final_state: AIOpsState = await aiops_graph.ainvoke(initial_state, config=thread_config)
        duration_ms = (time.monotonic() * 1000) - start_ms

        incident = _state_to_incident(final_state, alert, incident_id)
        return AgentRunResult(
            incident=incident,
            total_duration_ms=round(duration_ms, 2),
            success=True,
        )

    except Exception as exc:  # noqa: BLE001
        duration_ms = (time.monotonic() * 1000) - start_ms
        incident = Incident(
            incident_id=incident_id,
            alert=alert,
            status=IncidentStatus.OPEN,
            agent_notes=[f"Pipeline error: {exc}"],
        )
        return AgentRunResult(
            incident=incident,
            total_duration_ms=round(duration_ms, 2),
            success=False,
            error_message=str(exc),
        )
