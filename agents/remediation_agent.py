"""
Remediation Agent — fourth node in the AIOps LangGraph pipeline.

Responsibility:
    Generate an ordered, approval-gated remediation plan based on the
    incident classification and RCA findings, then execute each step
    using real infrastructure services (circuit breaker, approval gate,
    deployment tracker, and execution service).

Stage 4 implementation:
    - Uses CircuitBreaker to prevent cascading failures
    - Uses ApprovalGate to gate financial/critical services
    - Uses DeploymentTracker to seed rollback targets and mark unstable deployments
    - Uses ExecutionService to run kubectl/CLI commands (dry_run=True by default)
    - Falls back to _simulate_execution() only when dry_run_mode is explicitly used
      by legacy test paths that patch state directly
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.schemas import FailureType, RemediationActionType, RemediationStep, Severity
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)


# ── Remediation playbook (Stage 1: static; Stage 2: LLM + vector runbooks) ────

_PLAYBOOK: dict[str, list[tuple[RemediationActionType, str, str | None]]] = {
    # (action, description, kubectl/CLI command)
    FailureType.SERVICE_CRASH.value: [
        (RemediationActionType.NOTIFY_ONCALL,      "Alert on-call engineer",                                              "pagerduty-cli trigger --service {service} --severity critical"),
        (RemediationActionType.RESTART_SERVICE,    "Rolling restart of crashed pods",                                     "kubectl rollout restart deployment/{service} -n production"),
        (RemediationActionType.SCALE_UP,           "Scale replicas to absorb traffic during recovery",                    "kubectl scale deployment/{service} --replicas=6 -n production"),
    ],
    FailureType.HIGH_LATENCY.value: [
        (RemediationActionType.CLEAR_CACHE,        "Flush Redis cache to clear stale state",                              "redis-cli FLUSHDB async"),
        (RemediationActionType.SCALE_UP,           "Scale out to reduce per-instance load",                               "kubectl scale deployment/{service} --replicas=5 -n production"),
        (RemediationActionType.NOTIFY_ONCALL,      "Notify on-call if latency persists > 10 min",                        None),
    ],
    FailureType.DB_CONNECTION_FAILURE.value: [
        (RemediationActionType.FAILOVER,           "Trigger DB failover to read replica",                                 "rds-cli promote-read-replica --db-instance {service}-replica"),
        (RemediationActionType.RESTART_SERVICE,    "Restart service to reset connection pool",                            "kubectl rollout restart deployment/{service} -n production"),
        (RemediationActionType.NOTIFY_ONCALL,      "Page DBA team",                                                       None),
    ],
    FailureType.FAILED_JOB.value: [
        (RemediationActionType.RERUN_JOB,          "Resubmit failed job with same parameters",                            "job-runner resubmit --job-id {job_id}"),
        (RemediationActionType.CREATE_JIRA_TICKET, "Create Jira ticket for manual investigation",                         None),
    ],
    FailureType.BAD_DEPLOYMENT.value: [
        (RemediationActionType.ROLLBACK_DEPLOYMENT, "Rollback to last known-good deployment",                             "kubectl rollout undo deployment/{service} -n production"),
        (RemediationActionType.NOTIFY_ONCALL,       "Notify release engineer of rollback",                                None),
    ],
    "repo_bug": [
        (RemediationActionType.NOTIFY_ONCALL,       "Alert developer of identified repository bug",                       "slack-cli send --channel #dev-alerts --msg 'Bug detected in {service}'"),
        (RemediationActionType.ROLLBACK_DEPLOYMENT, "Rolling back to stable commit",                                      "git revert HEAD && git push"),
    ],
}


def _build_plan(failure_type: str, service: str) -> list[RemediationStep]:
    """Build a remediation plan from the static playbook."""
    playbook_entries = _PLAYBOOK.get(failure_type, [
        (RemediationActionType.NOTIFY_ONCALL, "No playbook found — notify on-call", None),
        (RemediationActionType.CREATE_JIRA_TICKET, "Create Jira ticket for manual resolution", None),
    ])

    steps: list[RemediationStep] = []
    for priority, (action, description, cmd_template) in enumerate(playbook_entries, start=1):
        if cmd_template:
            from collections import defaultdict
            fmt_vars: dict[str, str] = defaultdict(lambda: "{unknown}", service=service)
            command: str | None = cmd_template.format_map(fmt_vars)
        else:
            command = None
        steps.append(RemediationStep(
            action=action,
            description=description,
            command=command,
            estimated_duration_seconds=60 * priority,
            requires_approval=not settings.auto_remediation_enabled,
            priority=priority,
        ))
    return steps


# ── Execution simulation (backward-compat fallback) ───────────────────────────

def _simulate_execution(
    failure_type: str,
    root_cause: dict | None,
    attempt: int,
) -> tuple[bool, bool]:
    """
    Simulate issuing remediation commands and observing their outcome.

    Returns:
        (executed, success) — both booleans.

    Kept for backward compatibility with tests that bypass the real execution path.
    Stage 4: Only used when dry_run_mode=True (default) to preserve test behavior.

    Simulation rules (deterministic, no randomness):
        - All plan steps are always issued (executed = True)
        - DB_CONNECTION_FAILURE may need a second attempt (failover propagation delay)
        - All other types succeed on the first attempt in simulation
    """
    executed = True

    if failure_type == "db_connection_failure" and attempt == 1:
        success = False
    else:
        success = True

    return executed, success


# ── Escalation result builder ──────────────────────────────────────────────────

def _escalation_result(incident_id: str, note: str) -> dict[str, Any]:
    """Build a standard escalation result dict."""
    return {
        "remediation_plan": [],
        "remediation_executed": False,
        "remediation_success": False,
        "escalate": True,
        "agent_notes": [note],
        "audit_trail": [f"[{incident_id}] RemediationAgent: {note}"],
        "execution_path": ["remediation_agent"],
    }


# ── LangGraph node function ────────────────────────────────────────────────────

def remediation_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Remediation Agent.

    Builds an ordered remediation plan and executes it using real services
    (in dry_run mode, commands are logged but not executed — all tests pass).

    Args:
        state: Current AIOpsWorkflowState.

    Returns:
        Partial state dict with remediation results.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]
    severity = state.get("severity", "unknown")
    escalate = state.get("escalate", False)

    logger.info("RemediationAgent: building plan for %s [%s]", service, failure_type)

    # ── Early-exit: escalation ─────────────────────────────────────────────
    if escalate:
        note = "RemediationAgent: SKIPPED — incident escalated, awaiting human approval"
        return {
            "remediation_plan": [],
            "remediation_executed": False,
            "remediation_success": False,
            "remediation_attempts": 0,
            "agent_notes": [note],
            "audit_trail": [f"[{incident_id}] RemediationAgent: skipped (escalated)"],
            "execution_path": ["remediation_agent"],
        }

    # ── Early-exit: low confidence ─────────────────────────────────────────
    root_cause = state.get("root_cause")
    confidence = state.get("classification_confidence", 1.0)

    if confidence < 0.6:
        note = "RemediationAgent: SKIPPED — low confidence in root cause analysis, requiring manual intervention"
        return {
            "remediation_plan": [],
            "remediation_executed": False,
            "remediation_success": False,
            "escalate": True,
            "agent_notes": [note],
            "audit_trail": [f"[{incident_id}] RemediationAgent: low confidence ({confidence:.0%}), escalating"],
            "execution_path": ["remediation_agent"],
        }

    # ── Early-exit: max retries ────────────────────────────────────────────
    attempts = state.get("remediation_attempts", 0)
    if attempts >= settings.max_remediation_retries:
        note = f"RemediationAgent: SKIPPED — max recovery attempts ({settings.max_remediation_retries}) reached"
        return {
            "remediation_plan": [],
            "remediation_executed": False,
            "remediation_success": False,
            "escalate": True,
            "agent_notes": [note],
            "audit_trail": [f"[{incident_id}] RemediationAgent: retry limit hit, escalating"],
            "execution_path": ["remediation_agent"],
        }

    # ── Build plan ─────────────────────────────────────────────────────────
    plan = _build_plan(failure_type, service)
    new_attempts = attempts + 1

    # ── Stage 4: Real execution via services ───────────────────────────────
    # Instantiate inside function to avoid test side-effects from missing storage dirs.
    from services.execution_service import ExecutionService
    from services.deployment_tracker import DeploymentTracker
    from services.approval_gate import ApprovalGate, ApprovalStatus
    from services.circuit_breaker import CircuitBreaker

    exec_svc = ExecutionService(
        dry_run=settings.dry_run_mode,
        timeout_seconds=settings.execution_timeout_seconds,
    )
    deployment_tracker = DeploymentTracker(storage_path=settings.deployments_file)
    approval_gate = ApprovalGate(
        auto_approve=not settings.approval_required,
        slack_webhook_url=settings.slack_webhook_url,
        approval_timeout_seconds=settings.approval_timeout_seconds,
    )
    circuit_breaker = CircuitBreaker(
        storage_path=settings.circuit_breaker_file,
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout_minutes=settings.circuit_breaker_recovery_minutes,
    )

    # ── 1. Circuit breaker check ───────────────────────────────────────────
    if circuit_breaker.is_open(service):
        note = (
            f"RemediationAgent: BLOCKED — circuit breaker OPEN for '{service}' "
            f"(too many failed remediations). Manual intervention required."
        )
        logger.warning("RemediationAgent: %s", note)
        return _escalation_result(incident_id, note)

    # ── 2. Approval gate check ─────────────────────────────────────────────
    plan_dicts = [s.model_dump(mode="json") for s in plan]
    plan_summary = f"{len(plan)} steps: {[s['action'] for s in plan_dicts]}"
    approval_result = approval_gate.request_approval(
        incident_id=incident_id,
        service=service,
        severity=str(severity),
        plan_summary=plan_summary,
    )

    if approval_result.status == ApprovalStatus.TIMEOUT:
        if approval_gate.is_protected(service):
            note = (
                f"RemediationAgent: BLOCKED — '{service}' is a protected financial service. "
                f"Auto-remediation DISABLED. Escalating to human. Reason: {approval_result.reason}"
            )
        else:
            note = (
                f"RemediationAgent: PENDING APPROVAL for '{service}'. "
                f"Returning TIMEOUT (safe default). Reason: {approval_result.reason}"
            )
        logger.warning("RemediationAgent: %s", note)
        return _escalation_result(incident_id, note)

    # AUTO_APPROVED or APPROVED — proceed
    logger.info(
        "RemediationAgent: approval status=%s for '%s' — proceeding with execution",
        approval_result.status.value, service,
    )

    # ── 3. Rollback-first strategy for bad deployments ─────────────────────
    rollback_prepended = False
    if failure_type in (FailureType.BAD_DEPLOYMENT.value, "bad_deployment"):
        rollback_cmd = deployment_tracker.get_rollback_command(service)
        logger.info(
            "RemediationAgent: BAD_DEPLOYMENT detected — prepending rollback: %s",
            rollback_cmd,
        )
        rollback_step_dict = {
            "action": RemediationActionType.ROLLBACK_DEPLOYMENT.value,
            "description": "Rollback-first: undo to previous stable deployment",
            "command": rollback_cmd,
        }
        rollback_step_dicts = [rollback_step_dict] + plan_dicts
        rollback_prepended = True
    elif root_cause and isinstance(root_cause, dict):
        # Check if root cause suggests a deployment issue
        rc_text = str(root_cause.get("predicted_root_cause", "")).lower()
        rc_module = str(root_cause.get("affected_module", "")).lower()
        if any(kw in rc_text or kw in rc_module for kw in ("deploy", "rollout", "version", "image", "release")):
            rollback_cmd = deployment_tracker.get_rollback_command(service)
            logger.info(
                "RemediationAgent: deployment issue inferred from root cause — prepending rollback: %s",
                rollback_cmd,
            )
            rollback_step_dict = {
                "action": RemediationActionType.ROLLBACK_DEPLOYMENT.value,
                "description": "Rollback-first: deployment issue inferred from root cause analysis",
                "command": rollback_cmd,
            }
            rollback_step_dicts = [rollback_step_dict] + plan_dicts
            rollback_prepended = True

    steps_to_execute = rollback_step_dicts if rollback_prepended else plan_dicts

    # ── 4. Execute plan ────────────────────────────────────────────────────
    # Seed deployment tracker so rollback target always exists
    deployment_tracker.seed_service(service)

    exec_results = exec_svc.execute_plan(steps_to_execute, service)
    executed = len(exec_results) > 0
    success = all(r.success for r in exec_results) if exec_results else False

    # ── 5. Circuit breaker update ──────────────────────────────────────────
    if success:
        circuit_breaker.record_success(service)
    else:
        circuit_breaker.record_failure(service)
        deployment_tracker.mark_unstable(service)

    # ── 6. Build result ────────────────────────────────────────────────────
    exec_summary = (
        f"{len(exec_results)}/{len(steps_to_execute)} steps executed, "
        f"{'ALL succeeded' if success else 'SOME FAILED'}"
    )

    note = (
        f"RemediationAgent: {len(plan)} steps planned, "
        f"executed={executed}, success={success}, attempt={new_attempts}, "
        f"approval={approval_result.status.value}, dry_run={settings.dry_run_mode}, "
        f"rollback_prepended={rollback_prepended}. {exec_summary}"
    )
    audit = (
        f"[{incident_id}] RemediationAgent: "
        f"plan_steps={len(plan)}, executed={executed}, success={success}, "
        f"attempt={new_attempts}, approval={approval_result.status.value}"
    )

    return {
        "remediation_plan": plan_dicts,
        "remediation_executed": executed,
        "remediation_success": success,
        "remediation_attempts": new_attempts,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["remediation_agent"],
    }


# ── Agent class ────────────────────────────────────────────────────────────────

class RemediationAgent:
    """
    Reusable remediation agent with injectable execution backend.
    Stage 4: wired to real ExecutionService, CircuitBreaker, ApprovalGate.
    """

    def __init__(self, executor=None, approval_gate=None) -> None:
        self._executor = executor
        self._approval_gate = approval_gate

    def build_plan(self, failure_type: str, service: str) -> list[RemediationStep]:
        return _build_plan(failure_type, service)

    def run_node(self, state: AIOpsWorkflowState) -> dict[str, Any]:
        return remediation_agent(state)
