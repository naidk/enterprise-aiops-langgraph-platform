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

from app.config import settings
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

    # Simulate detailed detection logic
    confirmed = True
    if failure_type == "repo_bug":
        summary = f"Detected Repo-level bug in {service.upper()} — application module failing to initialize (ImportError)."
    elif failure_type == "service_crash":
        summary = f"Detected service crash in {service.upper()} — 100% of pods unavailable / health check failed."
    elif failure_type == "high_latency":
        summary = f"Detected high latency in {service.upper()} — P99 latency is 4200ms (SLA: 500ms)."
    elif failure_type == "db_connection_failure":
        summary = f"Detected database connection failure for {service.upper()} — connection pool exhausted."
    else:
        summary = f"Detected anomaly in {service.upper()} [Type: {failure_type}]."

    # Stage 4: real health check in live mode
    if not settings.dry_run_mode:
        if settings.using_aws:
            # AWS mode: use ECS service health + CloudWatch alarms
            try:
                from services.aws.boto_client import BotoClientFactory  # local import
                from services.aws.cloudwatch_health import CloudWatchHealthChecker  # local import

                factory = BotoClientFactory(
                    region=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    aws_session_token=settings.aws_session_token,
                    role_arn=settings.aws_role_arn,
                )
                checker = CloudWatchHealthChecker(factory, ecs_cluster=settings.aws_ecs_cluster)

                ecs_health = checker.check_ecs_service_health(service)
                alarm_health = checker.check_service_alarms(service)

                running = ecs_health.get("running_count", 0)
                desired = ecs_health.get("desired_count", 0)
                ecs_healthy = ecs_health.get("healthy", True)
                in_alarm = alarm_health.get("in_alarm", 0)

                if not ecs_healthy:
                    confirmed = True
                    summary += (
                        f" [ECS: running={running}/{desired} — service degraded]"
                    )
                elif in_alarm > 0:
                    confirmed = True
                    alarm_names = [a["name"] for a in alarm_health.get("alarms", []) if a.get("state") == "ALARM"]
                    summary += (
                        f" [CloudWatch: {in_alarm} alarm(s) in ALARM — {', '.join(alarm_names[:3])}]"
                    )
                else:
                    confirmed = False
                    summary += f" [AWS: ECS healthy (running={running}/{desired}), no alarms]"

                logger.info(
                    "MonitoringAgent: AWS health check for '%s' → ecs_healthy=%s in_alarm=%d confirmed=%s",
                    service, ecs_healthy, in_alarm, confirmed,
                )
            except Exception as exc:
                logger.warning(
                    "MonitoringAgent: AWS health check failed for '%s' — %s (using simulated confirmation)",
                    service, exc,
                )
        else:
            # Default: HTTP health check
            try:
                from services.health_service import HealthService  # local import
                real_health = HealthService(
                    base_url_pattern=settings.health_check_base_url,
                    health_path=settings.health_check_path,
                    timeout_seconds=settings.health_check_timeout_seconds,
                ).check(service)
                # A healthy response means the alert may have self-resolved
                confirmed = not real_health.is_healthy
                if real_health.endpoint_url:
                    summary += (
                        f" [Real health check: status={real_health.status}, "
                        f"http={real_health.http_status_code}, "
                        f"url={real_health.endpoint_url}]"
                    )
                logger.info(
                    "MonitoringAgent: real health check for '%s' → status=%s, confirmed=%s",
                    service, real_health.status, confirmed,
                )
            except Exception as exc:
                logger.warning(
                    "MonitoringAgent: real health check failed for '%s' — %s (using simulated confirmation)",
                    service, exc,
                )

    note = f"MonitoringAgent: confirmation={confirmed}, summary='{summary}'"
    audit = f"[{incident_id}] MonitoringAgent: confirmed={confirmed}, service={service}, failure_type={failure_type}"

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
