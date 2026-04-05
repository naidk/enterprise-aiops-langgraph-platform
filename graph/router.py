"""
LangGraph conditional edge router for the AIOps pipeline.

All routing functions live here to keep graph/workflow.py clean and
make the branching logic independently testable.
"""
from __future__ import annotations

import logging

from app.schemas import Severity
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)


def route_after_rca(state: AIOpsWorkflowState) -> str:
    """
    Route after root_cause_agent.

    Rules:
        - If escalate=True  → skip auto-remediation, jump to jira_reporting_agent
        - If escalate=False → proceed to remediation_agent
    """
    escalate = state.get("escalate", False)
    severity = state.get("severity", Severity.UNKNOWN.value)
    confidence = state.get("classification_confidence", 0.0)

    logger.debug(
        "Router: route_after_rca — severity=%s, escalate=%s, confidence=%s",
        severity, escalate, confidence,
    )

    if escalate:
        logger.info("Incident ESCALATED (severity=%s) — routing to jira_reporting_agent", severity)
        return "jira_reporting_agent"

    logger.info("RCA Diagnostic (confidence=%.2f) — routing to remediation_agent", confidence)
    return "remediation_agent"


def route_after_validation(state: AIOpsWorkflowState) -> str:
    """
    Route after validation_agent.

    Rules:
        - If validation_passed=True  → proceed to jira_reporting_agent
        - If validation_passed=False and attempts < MAX_RETRIES → loop back to remediation_agent
        - Otherwise → jira_reporting_agent (with ESCALATED status)
    """
    from app.config import settings  # avoid circular at module level

    passed = state.get("validation_passed", False)
    attempts = state.get("remediation_attempts", 0)
    max_retries = settings.max_remediation_retries

    logger.debug(
        "Router: route_after_validation — passed=%s, attempts=%d/%d",
        passed, attempts, max_retries,
    )

    # If the remediation_agent internally escalated (e.g. low confidence safety check),
    # do not loop back — go straight to Jira for human resolution.
    escalate = state.get("escalate", False)
    if escalate:
        logger.info("Incident escalated during remediation — routing to jira_reporting_agent")
        return "jira_reporting_agent"

    if not passed and attempts < max_retries:
        logger.info("Validation FAILED (attempt %d/%d) — routing back to remediation_agent", attempts, max_retries)
        return "remediation_agent"

    return "jira_reporting_agent"
