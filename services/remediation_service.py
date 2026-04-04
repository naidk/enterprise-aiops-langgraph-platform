"""
Remediation Service.

Executes individual remediation steps against live infrastructure.
Called by the remediation_agent node to actually apply fixes.

Stage 2 will:
    - Implement kubectl / k8s Python client calls for pod operations
    - Implement Argo CD / Spinnaker API calls for deployment rollbacks
    - Add Redis FLUSHDB for cache invalidation
    - Add Slack-based approval workflow before executing high-risk steps
    - Record execution results in audit_log.json with timing and output
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.schemas import RemediationActionType, RemediationStep

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single remediation step."""

    action: str
    success: bool
    output: str
    duration_ms: float
    error: Optional[str] = None


class RemediationService:
    """
    Executes remediation steps against real infrastructure.

    Usage:
        svc = RemediationService()
        result = svc.execute_step(step, service="payment-service")
    """

    def __init__(self, k8s_client=None, argo_client=None, redis_client=None) -> None:
        # TODO Stage 2: inject real infrastructure clients
        self._k8s = k8s_client
        self._argo = argo_client
        self._redis = redis_client

    def execute_step(self, step: RemediationStep, service: str) -> StepResult:
        """
        Execute a single remediation step.

        Dispatches to the appropriate backend based on step.action.
        TODO Stage 2: implement each action handler below.
        """
        logger.info("RemediationService: executing %s for %s", step.action.value, service)
        start = time.monotonic()

        try:
            output = self._dispatch(step, service)
            success = True
            error = None
        except Exception as exc:
            output = ""
            success = False
            error = str(exc)
            logger.error("RemediationService: step failed — %s", exc)

        duration_ms = (time.monotonic() - start) * 1000
        return StepResult(
            action=step.action.value,
            success=success,
            output=output,
            duration_ms=round(duration_ms, 2),
            error=error,
        )

    def _dispatch(self, step: RemediationStep, service: str) -> str:
        """Route step to the correct executor method."""
        handlers = {
            RemediationActionType.RESTART_SERVICE:     self._restart_service,
            RemediationActionType.ROLLBACK_DEPLOYMENT: self._rollback_deployment,
            RemediationActionType.SCALE_UP:            self._scale_up,
            RemediationActionType.CLEAR_CACHE:         self._clear_cache,
            RemediationActionType.FAILOVER:            self._failover,
            RemediationActionType.RERUN_JOB:           self._rerun_job,
            RemediationActionType.NOTIFY_ONCALL:       self._notify_oncall,
            RemediationActionType.CREATE_JIRA_TICKET:  self._create_jira_ticket,
            RemediationActionType.NO_ACTION:           lambda s: "No action taken.",
        }
        handler = handlers.get(step.action, lambda s: f"Unknown action: {step.action}")
        return handler(service)

    # ── Action handlers (TODO Stage 2: implement) ──────────────────────────────

    def _restart_service(self, service: str) -> str:
        # TODO: self._k8s.rollout_restart(deployment=service, namespace="production")
        logger.debug("STUB: restart_service(%s)", service)
        return f"[STUB] Rolling restart triggered for {service}."

    def _rollback_deployment(self, service: str) -> str:
        # TODO: self._argo.rollback(app=service)
        logger.debug("STUB: rollback_deployment(%s)", service)
        return f"[STUB] Deployment rollback initiated for {service}."

    def _scale_up(self, service: str) -> str:
        # TODO: self._k8s.scale(deployment=service, replicas=6)
        logger.debug("STUB: scale_up(%s)", service)
        return f"[STUB] Scaled {service} to 6 replicas."

    def _clear_cache(self, service: str) -> str:
        # TODO: self._redis.flushdb()
        logger.debug("STUB: clear_cache(%s)", service)
        return f"[STUB] Redis cache flushed for {service}."

    def _failover(self, service: str) -> str:
        # TODO: call cloud provider failover API
        logger.debug("STUB: failover(%s)", service)
        return f"[STUB] Failover triggered for {service}."

    def _rerun_job(self, service: str) -> str:
        # TODO: call job scheduler resubmit API
        logger.debug("STUB: rerun_job(%s)", service)
        return f"[STUB] Job resubmitted for {service}."

    def _notify_oncall(self, service: str) -> str:
        # TODO: call PagerDuty / OpsGenie API
        logger.debug("STUB: notify_oncall(%s)", service)
        return f"[STUB] On-call engineer notified for {service}."

    def _create_jira_ticket(self, service: str) -> str:
        # TODO: delegate to JiraService
        logger.debug("STUB: create_jira_ticket(%s)", service)
        return f"[STUB] Jira ticket created for {service}."

    def execute_plan(self, steps: list[RemediationStep], service: str) -> list[StepResult]:
        """Execute all steps in order. Stops on first failure unless continue_on_error=True."""
        results: list[StepResult] = []
        for step in sorted(steps, key=lambda s: s.priority):
            result = self.execute_step(step, service)
            results.append(result)
            if not result.success:
                logger.warning("RemediationService: stopping plan — step %s failed", step.action.value)
                break
        return results
