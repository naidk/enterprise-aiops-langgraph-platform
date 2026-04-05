"""
Execution Service — Stage 4.

Provides safe, auditable command execution with dry-run mode.
In dry_run=True (default): logs commands and returns success WITHOUT executing.
In dry_run=False: uses subprocess.run() to execute real commands with timeout.

Usage:
    from services.execution_service import ExecutionService
    svc = ExecutionService(dry_run=True)
    result = svc.execute("kubectl rollout restart deployment/payment-service -n production")
    print(result.success, result.stdout)
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a single command."""

    command: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    dry_run: bool
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None


class ExecutionService:
    """
    Safe command executor with dry-run mode and full audit trail.

    Args:
        dry_run: If True (default), commands are logged but not executed.
        timeout_seconds: Maximum time to wait for a command to complete.
    """

    def __init__(self, dry_run: bool = True, timeout_seconds: int = 300) -> None:
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        prefix = "[DRY RUN]" if dry_run else "[LIVE]"
        logger.info("%s ExecutionService initialized (timeout=%ds)", prefix, timeout_seconds)

    def execute_ecs(self, action: str, service: str, **kwargs) -> "ExecutionResult":
        """
        Execute an ECS-native service management action.

        In dry_run=True: logs the intended action and returns synthetic success.
        In dry_run=False: calls the real ECS API via ECSExecutionClient.

        Args:
            action: One of "restart", "rollback", "scale".
            service: ECS service name to operate on.
            **kwargs: Additional arguments (e.g. desired_count=3 for scale,
                      task_definition_arn=... for rollback).

        Returns:
            ExecutionResult representing the outcome.
        """
        start = time.monotonic()
        prefix = "[DRY RUN]" if self.dry_run else "[LIVE ECS]"
        command_repr = f"ecs:{action}:{service}"

        if self.dry_run:
            logger.info("%s Would execute ECS action '%s' on service '%s'", prefix, action, service)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            return ExecutionResult(
                command=command_repr,
                success=True,
                stdout=f"[DRY RUN] ECS {action} would be called for service '{service}'",
                stderr="",
                exit_code=0,
                duration_ms=duration_ms,
                dry_run=True,
            )

        # Live ECS path
        logger.info("%s Executing ECS action '%s' on service '%s'", prefix, action, service)
        try:
            from app.config import settings as _settings  # local import
            from services.aws.boto_client import BotoClientFactory  # local import
            from services.aws.ecs_execution import ECSExecutionClient  # local import

            factory = BotoClientFactory(
                region=_settings.aws_region,
                aws_access_key_id=_settings.aws_access_key_id,
                aws_secret_access_key=_settings.aws_secret_access_key,
                aws_session_token=_settings.aws_session_token,
                role_arn=_settings.aws_role_arn,
            )
            ecs_client = ECSExecutionClient(factory, cluster=_settings.aws_ecs_cluster)

            if action == "restart":
                result_data = ecs_client.restart_service(service)
            elif action == "rollback":
                task_def_arn = kwargs.get("task_definition_arn", "")
                result_data = ecs_client.rollback_service(service, task_definition_arn=task_def_arn)
            elif action == "scale":
                desired_count = int(kwargs.get("desired_count", 1))
                result_data = ecs_client.scale_service(service, desired_count)
            else:
                result_data = {"success": False, "error": f"Unknown ECS action: '{action}'"}

            duration_ms = round((time.monotonic() - start) * 1000, 2)
            success = result_data.get("success", False)
            message = result_data.get("message", str(result_data))
            error = result_data.get("error", "")

            if success:
                logger.info("%s ECS action '%s' on '%s' succeeded", prefix, action, service)
            else:
                logger.warning("%s ECS action '%s' on '%s' failed: %s", prefix, action, service, error)

            return ExecutionResult(
                command=command_repr,
                success=success,
                stdout=message,
                stderr=error,
                exit_code=0 if success else 1,
                duration_ms=duration_ms,
                dry_run=False,
                error_message=error if not success else None,
            )

        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            msg = f"ECS action '{action}' failed for '{service}': {exc}"
            logger.error("%s %s", prefix, msg)
            return ExecutionResult(
                command=command_repr,
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=1,
                duration_ms=duration_ms,
                dry_run=False,
                error_message=msg,
            )

    def execute(self, command: str) -> ExecutionResult:
        """
        Execute a single shell command.

        In dry_run mode: logs the command and returns a synthetic success result.
        In live mode: runs via subprocess.run() with configured timeout.

        If the command starts with "kubectl" and CLOUD_PROVIDER=aws is set,
        the command is intercepted and redirected to execute_ecs() so existing
        remediation playbooks work without modification.

        Args:
            command: The shell command string to execute.

        Returns:
            ExecutionResult with full details.
        """
        # Intercept kubectl commands and redirect to ECS API when in AWS mode
        if command.strip().startswith("kubectl"):
            try:
                from app.config import settings as _settings  # local import
                if _settings.using_aws:
                    return self._execute_kubectl_as_ecs(command)
            except Exception as exc:
                logger.warning(
                    "ExecutionService.execute: failed to check AWS mode for kubectl interception — %s", exc
                )

        start = time.monotonic()
        prefix = "[DRY RUN]" if self.dry_run else "[LIVE]"

        if self.dry_run:
            logger.info("%s Would execute: %s", prefix, command)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            return ExecutionResult(
                command=command,
                success=True,
                stdout=f"[DRY RUN] Command would execute: {command}",
                stderr="",
                exit_code=0,
                duration_ms=duration_ms,
                dry_run=True,
            )

        # Live execution path
        logger.info("%s Executing: %s", prefix, command)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            success = proc.returncode == 0

            if success:
                logger.info(
                    "%s Command succeeded (exit=%d, %.0fms): %s",
                    prefix, proc.returncode, duration_ms, command,
                )
            else:
                logger.warning(
                    "%s Command failed (exit=%d, %.0fms): %s | stderr: %s",
                    prefix, proc.returncode, duration_ms, command, proc.stderr[:200],
                )

            return ExecutionResult(
                command=command,
                success=success,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                dry_run=False,
            )

        except subprocess.TimeoutExpired:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            msg = f"Command timed out after {self.timeout_seconds}s: {command}"
            logger.error("%s %s", prefix, msg)
            return ExecutionResult(
                command=command,
                success=False,
                stdout="",
                stderr=msg,
                exit_code=-1,
                duration_ms=duration_ms,
                dry_run=False,
                error_message=msg,
            )

        except FileNotFoundError as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            msg = f"Command not found: {command} — {exc}"
            logger.error("%s %s", prefix, msg)
            return ExecutionResult(
                command=command,
                success=False,
                stdout="",
                stderr=msg,
                exit_code=127,
                duration_ms=duration_ms,
                dry_run=False,
                error_message=msg,
            )

        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            msg = f"Unexpected error executing command: {exc}"
            logger.error("%s %s (command=%s)", prefix, msg, command)
            return ExecutionResult(
                command=command,
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                duration_ms=duration_ms,
                dry_run=False,
                error_message=msg,
            )

    def _execute_kubectl_as_ecs(self, command: str) -> "ExecutionResult":
        """
        Parse a kubectl command and redirect it to the ECS API.

        Supports patterns:
        - kubectl rollout restart deployment/<service> ...  → execute_ecs("restart", ...)
        - kubectl rollout undo deployment/<service> ...     → execute_ecs("rollback", ...)
        - kubectl scale deployment/<service> --replicas=N   → execute_ecs("scale", ...)

        Unknown kubectl commands fall through to execute_ecs("restart", service).
        """
        import re

        parts = command.strip().split()
        action = "restart"
        service = "unknown"
        kwargs: dict = {}

        # Extract service from "deployment/<name>" or "deploy/<name>"
        for part in parts:
            m = re.match(r"(?:deployment|deploy)/(.+)", part)
            if m:
                service = m.group(1)
                break

        # Detect action
        if "undo" in parts:
            action = "rollback"
        elif "scale" in parts:
            action = "scale"
            for part in parts:
                m = re.match(r"--replicas=(\d+)", part)
                if m:
                    kwargs["desired_count"] = int(m.group(1))
                    break
        elif "restart" in parts:
            action = "restart"

        logger.info(
            "ExecutionService._execute_kubectl_as_ecs: intercepted kubectl command → ECS %s on '%s'",
            action, service,
        )
        return self.execute_ecs(action, service, **kwargs)

    def execute_plan(
        self,
        steps: list[dict],
        service: str,
    ) -> list[ExecutionResult]:
        """
        Execute an ordered list of remediation step dicts.

        Each step dict is expected to have a "command" key (optional).
        Stops on the first failure.

        Args:
            steps: List of step dicts (e.g. from RemediationStep.model_dump()).
            service: Service name for logging context.

        Returns:
            List of ExecutionResult, one per step attempted.
        """
        prefix = "[DRY RUN]" if self.dry_run else "[LIVE]"
        logger.info(
            "%s execute_plan: %d steps for service '%s'",
            prefix, len(steps), service,
        )

        results: list[ExecutionResult] = []
        for idx, step in enumerate(steps, start=1):
            command = step.get("command") or ""
            action = step.get("action", f"step_{idx}")

            if not command:
                logger.info(
                    "%s Step %d/%d (%s): no command — skipping execution",
                    prefix, idx, len(steps), action,
                )
                # Produce a synthetic success for no-op steps
                results.append(ExecutionResult(
                    command="",
                    success=True,
                    stdout=f"[NO-OP] Step '{action}' has no command — skipped",
                    stderr="",
                    exit_code=0,
                    duration_ms=0.0,
                    dry_run=self.dry_run,
                ))
                continue

            logger.info(
                "%s Step %d/%d (%s): %s",
                prefix, idx, len(steps), action, command,
            )
            result = self.execute(command)
            results.append(result)

            if not result.success:
                logger.warning(
                    "%s Plan halted at step %d/%d (%s) — command failed",
                    prefix, idx, len(steps), action,
                )
                break

        logger.info(
            "%s execute_plan complete: %d/%d steps attempted for '%s'",
            prefix, len(results), len(steps), service,
        )
        return results
