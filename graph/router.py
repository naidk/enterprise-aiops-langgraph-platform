"""
LangGraph conditional edge router for the AIOps pipeline.

All routing functions live here to keep graph/workflow.py clean and
make the branching logic independently testable.

Router contract:
    Each function receives the full AIOpsWorkflowState and returns a
    string key that maps to the next node name in add_conditional_edges().
"""
from __future__ import annotations

import logging

from app.schemas import Severity
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)


def route_after_classification(state: AIOpsWorkflowState) -> str:
    """
    Route after incident_classifier_agent.

    Rules:
        - If escalate=True  → skip auto-remediation, jump to jira_reporting_agent
        - If escalate=False → proceed to remediation_agent

    Returns:
        Node name string matching a key in the conditional_edges mapping.
    """
    escalate = state.get("escalate", False)
    severity = state.get("severity", Severity.UNKNOWN.value)

    logger.debug(
        "Router: route_after_classification — severity=%s, escalate=%s",
        severity, escalate,
    )

    if escalate:
        logger.info("Incident ESCALATED (severity=%s) — routing to jira_reporting_agent", severity)
        return "jira_reporting_agent"

    logger.info("Incident severity=%s — routing to remediation_agent", severity)
    return "remediation_agent"


def route_after_validation(state: AIOpsWorkflowState) -> str:
    """
    Route after validation_agent.

    Rules:
        - If validation_passed=True  → proceed to jira_reporting_agent
        - If validation_passed=False and attempts < MAX_RETRIES → loop back to remediation_agent
        - Otherwise → jira_reporting_agent (with ESCALATED status)

    NOTE: This router is not wired in Stage 1 — the graph uses a linear
    remediation → validation → jira edge. Stage 2 will add the loopback.

    Returns:
        Node name string.
    """
    from app.config import settings  # avoid circular at module level

    passed = state.get("validation_passed", False)
    attempts = state.get("remediation_attempts", 0)
    max_retries = settings.max_remediation_retries

    logger.debug(
        "Router: route_after_validation — passed=%s, attempts=%d/%d",
        passed, attempts, max_retries,
    )

    if not passed and attempts < max_retries:
        logger.info("Validation FAILED (attempt %d/%d) — routing back to remediation_agent", attempts, max_retries)
        return "remediation_agent"

    return "jira_reporting_agent"
