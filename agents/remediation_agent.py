"""
Remediation Agent — fourth node in the AIOps LangGraph pipeline.

Responsibility:
    Generate an ordered, approval-gated remediation plan based on the
    incident classification and RCA findings, then execute each step
    (with or without human approval depending on AUTO_REMEDIATION setting).

Stage 2 implementation will:
    - Use LLM to generate context-aware remediation steps from a runbook library
    - Integrate with Kubernetes API for pod restarts and rollbacks
    - Call Argo CD / Spinnaker for deployment rollbacks
    - Implement an approval workflow (Slack bot or API gate) before execution
    - Retry failed steps up to MAX_REMEDIATION_RETRIES with backoff
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
        (RemediationActionType.SCALE_UP,           "Scale replicas to absorb traffic during recovery",                   "kubectl scale deployment/{service} --replicas=6 -n production"),
    ],
    FailureType.HIGH_LATENCY.value: [
        (RemediationActionType.CLEAR_CACHE,        "Flush Redis cache to clear stale state",                             "redis-cli FLUSHDB async"),
        (RemediationActionType.SCALE_UP,           "Scale out to reduce per-instance load",                             "kubectl scale deployment/{service} --replicas=5 -n production"),
        (RemediationActionType.NOTIFY_ONCALL,      "Notify on-call if latency persists > 10 min",                       None),
    ],
    FailureType.DB_CONNECTION_FAILURE.value: [
        (RemediationActionType.FAILOVER,           "Trigger DB failover to read replica",                                "rds-cli promote-read-replica --db-instance {service}-replica"),
        (RemediationActionType.RESTART_SERVICE,    "Restart service to reset connection pool",                           "kubectl rollout restart deployment/{service} -n production"),
        (RemediationActionType.NOTIFY_ONCALL,      "Page DBA team",                                                      None),
    ],
    FailureType.FAILED_JOB.value: [
        (RemediationActionType.RERUN_JOB,          "Resubmit failed job with same parameters",                           "job-runner resubmit --job-id {job_id}"),
        (RemediationActionType.CREATE_JIRA_TICKET, "Create Jira ticket for manual investigation",                        None),
    ],
    FailureType.BAD_DEPLOYMENT.value: [
        (RemediationActionType.ROLLBACK_DEPLOYMENT, "Rollback to last known-good deployment",                            "kubectl rollout undo deployment/{service} -n production"),
        (RemediationActionType.NOTIFY_ONCALL,       "Notify release engineer of rollback",                               None),
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


# ── LangGraph node function ────────────────────────────────────────────────────

def remediation_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Remediation Agent.

    Builds an ordered remediation plan and executes it (in mock mode,
    simulates execution). Sets remediation_executed and remediation_success.

    Args:
        state: Current AIOpsWorkflowState.

    Returns:
        Partial state dict with remediation results.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]
    escalate = state.get("escalate", False)

    logger.info("RemediationAgent: building plan for %s [%s]", service, failure_type)

    if escalate:
        # Escalated incidents skip auto-remediation — human must approve
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

    plan = _build_plan(failure_type, service)
    attempts = state.get("remediation_attempts", 0) + 1

    # TODO Stage 2: actually execute each step, check result, retry on failure
    executed = True
    success = True   # stub — assume success in Stage 1

    note = (
        f"RemediationAgent: {len(plan)} steps planned, "
        f"executed={executed}, success={success}, attempt={attempts}"
    )
    audit = (
        f"[{incident_id}] RemediationAgent: "
        f"plan_steps={len(plan)}, executed={executed}, success={success}"
    )

    return {
        "remediation_plan": [s.model_dump(mode="json") for s in plan],
        "remediation_executed": executed,
        "remediation_success": success,
        "remediation_attempts": attempts,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["remediation_agent"],
    }


# ── Agent class ────────────────────────────────────────────────────────────────

class RemediationAgent:
    """
    Reusable remediation agent with injectable execution backend.
    Stage 2 will inject kubectl, Argo CD, and Slack approval clients.
    """

    def __init__(self, executor=None, approval_gate=None) -> None:
        self._executor = executor       # TODO Stage 2
        self._approval_gate = approval_gate  # TODO Stage 2

    def build_plan(self, failure_type: str, service: str) -> list[RemediationStep]:
        return _build_plan(failure_type, service)

    def run_node(self, state: AIOpsWorkflowState) -> dict[str, Any]:
        return remediation_agent(state)
