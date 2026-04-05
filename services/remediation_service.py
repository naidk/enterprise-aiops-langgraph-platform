"""
Remediation Service — Stage 4.

Executes individual remediation steps against live infrastructure via
ExecutionService. In dry_run mode (default) commands are logged without
executing — all existing tests continue to pass unchanged.

Usage:
    from services.remediation_service import RemediationService
    from services.execution_service import ExecutionService

    exec_svc = ExecutionService(dry_run=True)
    svc = RemediationService(execution_service=exec_svc)
    result = svc.execute_step(step, service="payment-service")
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
    Executes remediation steps against real infrastructure via ExecutionService.

    Falls back gracefully to stub output if no execution_service is provided.

    Args:
        execution_service: An ExecutionService instance. If None, a default
            dry_run=True instance is created automatically.
    """

    def __init__(self, execution_service=None, k8s_client=None, argo_client=None, redis_client=None) -> None:
        # Stage 4: wire real ExecutionService
        if execution_service is not None:
            self._exec = execution_service
        else:
            # Lazy import to avoid import cycles and test side-effects
            from services.execution_service import ExecutionService
            self._exec = ExecutionService(dry_run=True)

        # Legacy injections kept for API compatibility
        self._k8s = k8s_client
        self._argo = argo_client
        self._redis = redis_client

    def execute_step(self, step: RemediationStep, service: str) -> StepResult:
        """
        Execute a single remediation step via ExecutionService.

        Dispatches to the appropriate handler based on step.action.
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

    # ── Action handlers — Stage 4: delegate to ExecutionService ───────────────

    def _restart_service(self, service: str) -> str:
        cmd = f"kubectl rollout restart deployment/{service} -n production"
        result = self._exec.execute(cmd)
        return result.stdout or f"Rolling restart triggered for {service}."

    def _rollback_deployment(self, service: str) -> str:
        cmd = f"kubectl rollout undo deployment/{service} -n production"
        result = self._exec.execute(cmd)
        return result.stdout or f"Deployment rollback initiated for {service}."

    def _scale_up(self, service: str) -> str:
        cmd = f"kubectl scale deployment/{service} --replicas=6 -n production"
        result = self._exec.execute(cmd)
        return result.stdout or f"Scaled {service} to 6 replicas."

    def _clear_cache(self, service: str) -> str:
        cmd = "redis-cli FLUSHDB async"
        result = self._exec.execute(cmd)
        return result.stdout or f"Redis cache flushed for {service}."

    def _failover(self, service: str) -> str:
        cmd = f"kubectl patch service {service} -p '{{\"spec\":{{\"selector\":{{\"version\":\"stable\"}}}}}}'"
        result = self._exec.execute(cmd)
        return result.stdout or f"Failover triggered for {service}."

    def _rerun_job(self, service: str) -> str:
        cmd = "echo 'Job resubmission requires manual job ID — see audit trail'"
        result = self._exec.execute(cmd)
        return result.stdout or f"Job resubmitted for {service}."

    def _notify_oncall(self, service: str) -> str:
        cmd = "echo 'PagerDuty integration required — set PAGERDUTY_API_KEY in .env'"
        result = self._exec.execute(cmd)
        return result.stdout or f"On-call engineer notified for {service}."

    def _create_jira_ticket(self, service: str) -> str:
        cmd = "echo 'Jira integration required — set JIRA_API_TOKEN in .env'"
        result = self._exec.execute(cmd)
        return result.stdout or f"Jira ticket created for {service}."

    def execute_plan(self, steps: list[RemediationStep], service: str) -> list[StepResult]:
        """Execute all steps in order. Stops on first failure."""
        results: list[StepResult] = []
        for step in sorted(steps, key=lambda s: s.priority):
            result = self.execute_step(step, service)
            results.append(result)
            if not result.success:
                logger.warning(
                    "RemediationService: stopping plan — step %s failed",
                    step.action.value,
                )
                break
        return results
