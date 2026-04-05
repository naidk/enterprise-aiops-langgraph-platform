"""
Approval Gate — Stage 4.

Controls whether a remediation plan may proceed. Financial/critical services
require human approval and will never be auto-approved. For other services,
the gate can be configured to auto-approve or request Slack approval.

Usage:
    from services.approval_gate import ApprovalGate, ApprovalStatus
    gate = ApprovalGate(auto_approve=True)
    result = gate.request_approval("INC-001", "api-gateway", "high", "2 steps: restart, scale")
    if result.status == ApprovalStatus.AUTO_APPROVED:
        ...  # proceed with remediation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ApprovalResult:
    """Result of an approval request."""

    status: ApprovalStatus
    approver: str
    reason: str
    approved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ApprovalGate:
    """
    Approval workflow for remediation plans.

    Financial/critical services always escalate (TIMEOUT) — never auto-approved.
    Other services follow the auto_approve flag or Slack webhook workflow.

    Args:
        auto_approve: If True and service is not protected, approve automatically.
        slack_webhook_url: Optional Slack incoming webhook URL for notifications.
        approval_timeout_seconds: Timeout before returning TIMEOUT status.
    """

    PROTECTED_SERVICES: frozenset[str] = frozenset({
        "payment-service",
        "billing-service",
        "order-processor",
        "fraud-detection",
        "checkout-service",
        "wallet-service",
    })

    def __init__(
        self,
        auto_approve: bool = True,
        slack_webhook_url: str = "",
        approval_timeout_seconds: int = 300,
    ) -> None:
        self.auto_approve = auto_approve
        self.slack_webhook_url = slack_webhook_url
        self.approval_timeout_seconds = approval_timeout_seconds

    def is_protected(self, service: str) -> bool:
        """Return True if the service is in the protected financial services set."""
        return service in self.PROTECTED_SERVICES

    def request_approval(
        self,
        incident_id: str,
        service: str,
        severity: str,
        plan_summary: str,
    ) -> ApprovalResult:
        """
        Request approval for a remediation plan.

        Decision matrix:
        - PROTECTED service  → always TIMEOUT (never auto-approve financial services)
        - auto_approve=True  → AUTO_APPROVED (after Slack notification)
        - auto_approve=False → Slack notification sent, return TIMEOUT (await human)

        Args:
            incident_id: The incident ID for traceability.
            service: The target service name.
            severity: Incident severity string.
            plan_summary: Human-readable description of the remediation plan.

        Returns:
            ApprovalResult with status, approver, and reason.
        """
        if self.is_protected(service):
            reason = (
                f"Service '{service}' is a protected financial service — "
                "auto-remediation is DISABLED. Human approval required."
            )
            logger.warning(
                "ApprovalGate: BLOCKED — protected service '%s' [incident=%s]",
                service, incident_id,
            )
            self._send_slack_notification(
                incident_id=incident_id,
                service=service,
                severity=severity,
                plan_summary=plan_summary,
                require_approval=True,
            )
            return ApprovalResult(
                status=ApprovalStatus.TIMEOUT,
                approver="system",
                reason=reason,
            )

        if self.auto_approve:
            logger.info(
                "ApprovalGate: AUTO_APPROVED for service '%s' [incident=%s]",
                service, incident_id,
            )
            self._send_slack_notification(
                incident_id=incident_id,
                service=service,
                severity=severity,
                plan_summary=plan_summary,
                require_approval=False,
            )
            return ApprovalResult(
                status=ApprovalStatus.AUTO_APPROVED,
                approver="system",
                reason=f"Auto-approval enabled for non-protected service '{service}'",
            )

        # Manual approval required — notify and await human response
        logger.warning(
            "ApprovalGate: PENDING — manual approval required for '%s' [incident=%s]. "
            "Returning TIMEOUT (safe default).",
            service, incident_id,
        )
        self._send_slack_notification(
            incident_id=incident_id,
            service=service,
            severity=severity,
            plan_summary=plan_summary,
            require_approval=True,
        )
        return ApprovalResult(
            status=ApprovalStatus.TIMEOUT,
            approver="pending",
            reason=(
                f"Manual approval required for '{service}'. "
                f"Slack notification sent. Timeout after {self.approval_timeout_seconds}s."
            ),
        )

    def _send_slack_notification(
        self,
        incident_id: str,
        service: str,
        severity: str,
        plan_summary: str,
        require_approval: bool,
    ) -> None:
        """
        Send a Slack notification for the remediation approval request.

        If slack_webhook_url is configured, POSTs a JSON payload to the webhook.
        If not configured, logs the notification at WARNING level.
        Exceptions are caught and logged — Slack being down must not crash remediation.
        """
        action_label = "⚠️ APPROVAL REQUIRED" if require_approval else "ℹ️ AUTO-APPROVED (notification only)"
        text = (
            f"*AIOps Remediation {action_label}*\n"
            f"• Incident: `{incident_id}`\n"
            f"• Service:  `{service}`\n"
            f"• Severity: `{severity}`\n"
            f"• Plan:     {plan_summary}"
        )
        payload = {"text": text}

        if not self.slack_webhook_url:
            logger.warning(
                "ApprovalGate [Slack]: %s | incident=%s | service=%s | plan=%s",
                action_label, incident_id, service, plan_summary,
            )
            return

        try:
            import requests  # local import to avoid hard dependency at module load
            response = requests.post(
                self.slack_webhook_url,
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(
                    "ApprovalGate: Slack notification sent for incident=%s service=%s",
                    incident_id, service,
                )
            else:
                logger.warning(
                    "ApprovalGate: Slack responded with HTTP %d for incident=%s",
                    response.status_code, incident_id,
                )
        except Exception as exc:
            logger.warning(
                "ApprovalGate: Slack notification failed — %s (continuing without Slack)",
                exc,
            )
