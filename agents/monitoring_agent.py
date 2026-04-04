"""
Monitoring Agent — first node in the AIOps LangGraph pipeline.

Responsibility:
    Receive a raw PipelineEvent, confirm it represents a real failure,
    enrich it with context (service health, recent deployment state),
    and produce a structured event summary for downstream agents.

Stage 2 implementation will:
    - Call health_service.check(service) to verify the alert is still active
    - Query metrics_service for CPU / memory / error-rate snapshots
    - Use LLM to generate a natural-language event summary
    - Implement duplicate detection to suppress flapping alerts
"""
from __future__ import annotations

import logging
from typing import Any

from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)


# ── LangGraph node function ────────────────────────────────────────────────────

def monitoring_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Monitoring Agent.

    Validates the incoming pipeline event and enriches the workflow state
    with a confirmation flag and a plain-English summary.

    Args:
        state: Current AIOpsWorkflowState from the previous node (or seed).

    Returns:
        Partial state dict — only modified fields are returned.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]
    raw_event = state["raw_event"]

    logger.info("MonitoringAgent: processing event for %s [%s]", service, failure_type)

    # TODO Stage 2: call health_service and metrics_service
    # health = health_service.check(service)
    # metrics = metrics_service.snapshot(service)
    # confirmed = health.status != "healthy"

    # Stub: always confirm the event for now
    confirmed = True
    summary = (
        f"[MONITORING] Event confirmed on '{service}': "
        f"failure_type={failure_type}, "
        f"event_id={raw_event.get('event_id', 'N/A')}. "
        f"Service health check: DEGRADED."
    )

    note = f"MonitoringAgent completed — event_detected={confirmed}"
    audit = f"[{incident_id}] MonitoringAgent: confirmed={confirmed}, service={service}"

    return {
        "event_detected": confirmed,
        "event_summary": summary,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["monitoring_agent"],
    }


# ── Standalone helper (used by health_service) ────────────────────────────────

class MonitoringAgent:
    """
    Reusable monitoring agent class.
    Wraps the LangGraph node function with additional orchestration methods.
    Stage 2 will add real health check polling, alerting thresholds, and
    integration with Prometheus / Datadog / CloudWatch.
    """

    def __init__(self, health_svc=None, metrics_svc=None) -> None:
        # TODO Stage 2: inject real services
        self._health_svc = health_svc
        self._metrics_svc = metrics_svc

    def check_service(self, service: str) -> dict[str, Any]:
        """
        Poll service health and return a status snapshot.

        TODO Stage 2: implement real HTTP health check + metrics pull.
        """
        logger.debug("MonitoringAgent.check_service: %s", service)
        return {
            "service": service,
            "status": "degraded",   # stub
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "error_rate": 0.0,
        }

    def is_duplicate(self, incident_id: str, service: str) -> bool:
        """
        Check whether an open incident already exists for this service+failure.

        TODO Stage 2: query incident_service for open incidents on the same service.
        """
        return False  # stub — no deduplication yet

    def run_node(self, state: AIOpsWorkflowState) -> dict[str, Any]:
        """Delegate to the module-level LangGraph node function."""
        return monitoring_agent(state)
