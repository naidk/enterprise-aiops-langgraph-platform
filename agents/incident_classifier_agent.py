"""
Incident Classifier Agent — third node in the AIOps LangGraph pipeline.

Responsibility:
    Analyse the enriched incident state (event summary + RCA findings + error patterns)
    to determine:
      - Severity (CRITICAL / HIGH / MEDIUM / LOW)
      - Refined failure category
      - Confidence score
      - Escalation decision (page human vs. attempt auto-remediation)

Stage 2 implementation will:
    - Pass the full incident context to an LLM for classification
    - Use a fine-tuned classification model trained on historical incidents
    - Apply business rules (SLO breach, VIP customer impact) to bump severity
    - Implement duplicate/flapping detection to suppress noise
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas import FailureType, Severity
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)


# ── Severity rules (Stage 1: rule-based; Stage 2: LLM-scored) ─────────────────

_FAILURE_SEVERITY_MAP: dict[str, Severity] = {
    FailureType.SERVICE_CRASH.value:         Severity.CRITICAL,
    FailureType.DB_CONNECTION_FAILURE.value: Severity.CRITICAL,
    FailureType.BAD_DEPLOYMENT.value:        Severity.HIGH,
    FailureType.HIGH_LATENCY.value:          Severity.HIGH,
    FailureType.FAILED_JOB.value:            Severity.MEDIUM,
    FailureType.UNKNOWN.value:               Severity.LOW,
}

_AUTO_REMEDIATE_SEVERITIES = {Severity.HIGH, Severity.MEDIUM, Severity.LOW}
_ESCALATE_SEVERITIES = {Severity.CRITICAL}


def _determine_severity(failure_type: str, error_patterns: list[str]) -> tuple[Severity, float]:
    """
    Rule-based severity classification with confidence scoring.
    Stage 2 replaces this with an LLM call.
    """
    base_severity = _FAILURE_SEVERITY_MAP.get(failure_type, Severity.UNKNOWN)
    confidence = 0.80  # base confidence for rule-based classification

    # Boost severity if multiple high-impact patterns found
    critical_patterns = {"Memory exhaustion", "Database deadlock", "Deployment regression"}
    if any(p in error_patterns for p in critical_patterns):
        if base_severity == Severity.HIGH:
            base_severity = Severity.CRITICAL
            confidence = 0.90

    return base_severity, confidence


# ── LangGraph node function ────────────────────────────────────────────────────

def incident_classifier_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Incident Classifier Agent.

    Classifies the incident severity and determines whether to auto-remediate
    or escalate to an on-call engineer.

    Args:
        state: Current AIOpsWorkflowState.

    Returns:
        Partial state dict with classification results.
    """
    incident_id = state["incident_id"]
    failure_type = state["failure_type"]
    error_patterns = state.get("error_patterns", [])
    rca_findings = state.get("rca_findings", [])

    logger.info("IncidentClassifierAgent: classifying incident %s", incident_id)

    severity, confidence = _determine_severity(failure_type, error_patterns)

    # Escalation decision
    should_escalate = severity in _ESCALATE_SEVERITIES

    note = (
        f"IncidentClassifierAgent: severity={severity.value}, "
        f"confidence={confidence:.0%}, escalate={should_escalate}"
    )
    audit = (
        f"[{incident_id}] IncidentClassifierAgent: "
        f"severity={severity.value}, failure_type={failure_type}, "
        f"escalate={should_escalate}, patterns={error_patterns}"
    )

    return {
        "severity": severity.value,
        "failure_category": failure_type,
        "classification_confidence": confidence,
        "escalate": should_escalate,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["incident_classifier_agent"],
    }


# ── Agent class ────────────────────────────────────────────────────────────────

class IncidentClassifierAgent:
    """
    Reusable classifier with pluggable LLM backend.
    Stage 2 will inject a LangChain ChatModel for LLM-based classification.
    """

    def __init__(self, llm=None) -> None:
        self._llm = llm  # TODO Stage 2

    def classify(self, failure_type: str, error_patterns: list[str]) -> tuple[str, float]:
        """Return (severity_value, confidence). Delegates to rule engine in Stage 1."""
        severity, confidence = _determine_severity(failure_type, error_patterns)
        return severity.value, confidence

    def run_node(self, state: AIOpsWorkflowState) -> dict[str, Any]:
        return incident_classifier_agent(state)
