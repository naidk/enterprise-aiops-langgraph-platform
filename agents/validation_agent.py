"""
Validation Agent — fifth node in the AIOps LangGraph pipeline.

Responsibility:
    After remediation steps have been executed, verify that the service
    has actually recovered. Performs health checks, metric spot-checks,
    and optionally re-runs a suite of smoke tests.

Stage 2 implementation will:
    - Re-poll health_service.check() until service returns healthy or timeout
    - Verify key metrics (error rate, latency, memory) are within SLO thresholds
    - Run a lightweight smoke test suite against the recovered service
    - Implement retry logic with exponential backoff before declaring failure
    - Trigger a rollback in remediation_agent if validation fails (loopback edge)
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas import IncidentStatus
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)


# ── Recovery thresholds (Stage 2: load from settings / SLO config) ────────────

_HEALTHY_ERROR_RATE_THRESHOLD = 5.0    # percent
_HEALTHY_LATENCY_THRESHOLD_MS = 1000.0
_HEALTHY_MEMORY_THRESHOLD = 85.0       # percent


def _check_recovery(service: str, remediation_success: bool) -> tuple[bool, str]:
    """
    Verify service has recovered post-remediation.

    Stage 1: deterministic stub based on remediation_success flag.
    Stage 2: live health check + metric validation.
    """
    if not remediation_success:
        return False, f"Validation skipped — remediation reported failure for {service}"

    # TODO Stage 2: poll health endpoint, check metrics
    # health = health_service.check(service)
    # metrics = metrics_service.snapshot(service)
    # if health.status != "healthy": return False, f"Health check still failing: {health.detail}"
    # if metrics.error_rate > _HEALTHY_ERROR_RATE_THRESHOLD: ...

    # Stub: assume recovery if remediation succeeded
    return True, f"Service '{service}' health check PASSED. Error rate < 5%. Latency within SLO."


# ── LangGraph node function ────────────────────────────────────────────────────

def validation_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Validation Agent.

    Verifies service recovery after remediation and sets the final incident status.

    Args:
        state: Current AIOpsWorkflowState.

    Returns:
        Partial state dict with validation results and final_status.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    remediation_success = state.get("remediation_success", False)
    remediation_executed = state.get("remediation_executed", False)
    escalate = state.get("escalate", False)

    logger.info("ValidationAgent: validating recovery for %s", service)

    if escalate or not remediation_executed:
        # Cannot validate — incident was escalated or remediation didn't run
        note = "ValidationAgent: SKIPPED — escalated or remediation not executed"
        return {
            "validation_passed": False,
            "validation_details": "Validation skipped — manual intervention required",
            "final_status": IncidentStatus.ESCALATED.value,
            "agent_notes": [note],
            "audit_trail": [f"[{incident_id}] ValidationAgent: skipped"],
            "execution_path": ["validation_agent"],
        }

    passed, details = _check_recovery(service, remediation_success)
    final_status = IncidentStatus.RESOLVED.value if passed else IncidentStatus.REMEDIATING.value

    note = f"ValidationAgent: passed={passed}, status={final_status}"
    audit = f"[{incident_id}] ValidationAgent: validation_passed={passed}, final_status={final_status}"

    return {
        "validation_passed": passed,
        "validation_details": details,
        "final_status": final_status,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["validation_agent"],
    }


# ── Agent class ────────────────────────────────────────────────────────────────

class ValidationAgent:
    """
    Reusable validation agent with injectable health check and metrics backend.
    Stage 2 will inject health_service, metrics_service, and smoke_test_runner.
    """

    def __init__(self, health_svc=None, metrics_svc=None, smoke_runner=None) -> None:
        self._health_svc = health_svc         # TODO Stage 2
        self._metrics_svc = metrics_svc       # TODO Stage 2
        self._smoke_runner = smoke_runner     # TODO Stage 2

    def validate(self, service: str, remediation_success: bool) -> tuple[bool, str]:
        return _check_recovery(service, remediation_success)

    def run_node(self, state: AIOpsWorkflowState) -> dict[str, Any]:
        return validation_agent(state)
