"""
Root Cause Agent — the diagnostic core of Stage 3.

Responsibility:
    - Aggregate signals from logs, repo inspection, and test results.
    - Predict the specific root cause and affected module using LLM inference (Groq/Claude).
    - Determine incident severity and provide high-confidence remediation advice.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas import RootCauseAnalysis, Severity
from app.state import AIOpsWorkflowState
from app.llm_factory import get_llm
from app.config import settings

logger = logging.getLogger(__name__)


def root_cause_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Root Cause Agent.
    
    Combines all diagnostic signals into a single high-confidence analysis using 
    real LLM inference. Supports Groq for demo and Claude for production.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]
    repo_findings = state.get("repo_findings", [])
    test_results = state.get("test_results", [])
    log_entries = state.get("log_entries", [])
    
    logger.info("RootCauseAgent: determining root cause for %s (LLM: %s)", service, settings.llm_provider)

    # If not using real LLM, fallback to simulation (Stage 3 logic)
    if not settings.using_real_llm:
        return _simulate_root_cause(state)

    try:
        # ── LLM REASONING LOOP ────────────────────────────────────────────────
        llm = get_llm()
        
        system_prompt = (
            "You are a Principal SRE Agent at an Enterprise AIOps platform. "
            "Analyze diagnostic signals to determine the definitive root cause. "
            "Be precise, technical, and provide high-confidence remediation advice. "
            "Reflect uncertainty in your confidence score (0.0 to 1.0)."
        )
        
        context = f"""
        Incident Context:
        - Incident ID: {incident_id}
        - Service: {service}
        - Initial Failure Type: {failure_type}
        
        Log Findings (sampled):
        {chr(10).join(f"- {l.get('message', '')}" for l in log_entries[:10])}
        
        Repository Findings:
        {chr(10).join(f"- [{r.get('severity', 'high')}] {r.get('description', '')}" for r in repo_findings)}
        
        Test Results:
        {chr(10).join(f"- {t.get('test_name', '')}: {t.get('status', '')}" for t in test_results)}
        """

        # Call LLM with structured output
        try:
            structured_llm = llm.with_structured_output(RootCauseAnalysis)
            analysis = structured_llm.invoke([
                ("system", system_prompt),
                ("human", context)
            ])
        except Exception as e:
            logger.warning("RootCauseAgent: structured output failed, falling back to simulation: %s", e)
            return _simulate_root_cause(state)

        severity = analysis.severity
        confidence = analysis.confidence
        predicted_cause = analysis.predicted_root_cause
        affected_module = analysis.affected_module

    except Exception as e:
        logger.error("RootCauseAgent: LLM inference failed: %s", e)
        return _simulate_root_cause(state)

    # Escalation decision
    should_escalate = severity == Severity.CRITICAL or confidence < 0.6

    note = (
        f"RootCauseAgent: LLM RCA complete ({settings.llm_provider}). "
        f"confidence={confidence:.0%}, severity={severity.value}, escalate={should_escalate}"
    )
    audit = (
        f"[{incident_id}] RootCauseAgent: Root cause identified via {settings.llm_provider} as '{predicted_cause}'. "
        f"Affected module: {affected_module}."
    )
    
    return {
        "root_cause": analysis.model_dump(mode="json"),
        "severity": severity.value,
        "classification_confidence": confidence,
        "escalate": should_escalate,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["root_cause_agent"],
    }


# ── Severity mapping by failure type (simulation) ─────────────────────────────
# CRITICAL → auto-escalate to human; HIGH/below → attempt auto-remediation
_FAILURE_SEVERITY_MAP: dict[str, Severity] = {
    "service_crash":         Severity.CRITICAL,  # pod OOMKill / crash → immediate escalation
    "db_connection_failure": Severity.CRITICAL,  # data-layer outage → high blast radius
    "bad_deployment":        Severity.HIGH,
    "high_latency":          Severity.HIGH,
    "repo_bug":              Severity.HIGH,
    "failed_job":            Severity.MEDIUM,
    "unknown":               Severity.LOW,
}

# Confidence levels by failure type — unknown types warrant lower confidence
_FAILURE_CONFIDENCE_MAP: dict[str, float] = {
    "service_crash":         0.92,
    "db_connection_failure": 0.90,
    "bad_deployment":        0.88,
    "high_latency":          0.85,
    "repo_bug":              0.87,
    "failed_job":            0.80,
    "unknown":               0.50,  # below 0.6 → triggers safety escalation in remediation_agent
}

# Suggested remediation by failure type
_FAILURE_REMEDIATION_MAP: dict[str, str] = {
    "service_crash":         "Rolling restart pods and scale replicas; investigate OOM limits.",
    "db_connection_failure": "Trigger DB failover, restart service to reset connection pool.",
    "bad_deployment":        "Rollback to last known-good deployment via kubectl rollout undo.",
    "high_latency":          "Flush Redis cache and scale out service replicas.",
    "repo_bug":              "Revert offending commit, fix broken import, redeploy.",
    "failed_job":            "Resubmit job with same parameters; check input data integrity.",
    "unknown":               "Manual investigation required — insufficient signal for auto-remediation.",
}


def _simulate_root_cause(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    Fallback simulation logic when LLM is not available.

    Uses curated failure-type → severity/confidence maps so that the simulated
    RCA produces realistic, test-consistent outputs without an LLM call.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]
    repo_findings = state.get("repo_findings", [])
    test_results = state.get("test_results", [])
    log_entries = state.get("log_entries", [])

    # Defaults from failure-type maps
    severity = _FAILURE_SEVERITY_MAP.get(failure_type, Severity.HIGH)
    confidence = _FAILURE_CONFIDENCE_MAP.get(failure_type, 0.85)
    predicted_cause = f"Failure in {service} due to {failure_type.replace('_', ' ')}."
    affected_module = service
    suggested_fix = _FAILURE_REMEDIATION_MAP.get(failure_type, "Consult runbook.")

    # Repo findings override: strongest signal — specific file/module identified
    if repo_findings:
        first_finding = repo_findings[0]
        predicted_cause = f"Repo Issue: {first_finding['description']}"
        affected_module = first_finding.get("module") or service
        # Repo finding severity overrides the default if it is worse
        finding_sev = first_finding.get("severity", "high")
        repo_severity = Severity.CRITICAL if finding_sev == "critical" else Severity.HIGH
        if list(Severity).index(repo_severity) < list(Severity).index(severity):
            severity = repo_severity
        confidence = 0.95  # very high — file + issue type identified
        suggested_fix = f"Fix {first_finding['issue_type']} issue in {first_finding['file_path']}."

    analysis = RootCauseAnalysis(
        predicted_root_cause=predicted_cause,
        affected_module=affected_module,
        severity=severity,
        confidence=confidence,
        suggested_remediation=suggested_fix,
        evidence_ids=(
            [l.get("log_id", "unknown") for l in log_entries]
            + [t.get("test_id", "unknown") for t in test_results]
        ),
    )

    # Escalate only on CRITICAL severity.
    # Low-confidence safety check is handled inside remediation_agent so that
    # the remediation node appears in the execution_path with executed=False.
    should_escalate = severity == Severity.CRITICAL

    return {
        "root_cause": analysis.model_dump(mode="json"),
        "severity": severity.value,
        "classification_confidence": confidence,
        "escalate": should_escalate,
        "agent_notes": [
            f"RootCauseAgent: RCA complete (Simulated). "
            f"severity={severity.value}, confidence={confidence:.0%}, escalate={should_escalate}"
        ],
        "audit_trail": [
            f"[{incident_id}] RootCauseAgent: Root cause identified (Simulated) — "
            f"'{predicted_cause}'. Affected: {affected_module}."
        ],
        "execution_path": ["root_cause_agent"],
    }
