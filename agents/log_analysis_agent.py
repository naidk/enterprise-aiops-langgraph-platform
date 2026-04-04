"""
Log Analysis Agent — second node in the AIOps LangGraph pipeline.

Responsibility:
    Retrieve and parse recent log entries for the affected service.
    Extract error patterns, stack traces, and correlate with known failure signatures.
    Produce RCAFinding objects for the Incident Classifier to score.

Stage 2 implementation will:
    - Query Elasticsearch / Loki / CloudWatch Logs for recent ERROR/FATAL lines
    - Use LLM to extract structured findings from unstructured log text
    - Implement pattern matching against a known failure signature library
    - Correlate log timestamps with recent deployments and metric spikes
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas import LogEntry, RCAFinding
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)

# ── Known error patterns ───────────────────────────────────────────────────────
# Stage 2: move these to a database / vector store for dynamic expansion

_ERROR_PATTERNS: dict[str, str] = {
    r"OOMKill|memory limit exceeded":            "Memory exhaustion — container OOMKilled",
    r"connection refused|ECONNREFUSED":          "Dependency unreachable — connection refused",
    r"timeout|timed out":                        "Request/query timeout — downstream latency",
    r"NPE|NullPointerException|null pointer":    "Null pointer exception in application code",
    r"deployment|rollout|readiness probe":       "Deployment regression — readiness probe failure",
    r"disk full|no space left":                  "Disk space exhaustion",
    r"deadlock|lock wait timeout":               "Database deadlock detected",
    r"circuit breaker open":                     "Circuit breaker tripped — downstream overload",
}


def _match_patterns(log_text: str) -> list[str]:
    """Extract all matching error pattern labels from a block of log text."""
    matched: list[str] = []
    for pattern, label in _ERROR_PATTERNS.items():
        if re.search(pattern, log_text, re.IGNORECASE):
            matched.append(label)
    return matched


# ── LangGraph node function ────────────────────────────────────────────────────

def log_analysis_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Log Analysis Agent.

    Fetches and analyses logs for the affected service, then populates
    log_entries, rca_findings, and error_patterns in the workflow state.

    Args:
        state: Current AIOpsWorkflowState.

    Returns:
        Partial state dict with log analysis results.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]

    logger.info("LogAnalysisAgent: analysing logs for %s", service)

    # TODO Stage 2: query real log source
    # raw_logs = log_source.fetch(service=service, window_minutes=30, level="ERROR")
    # log_entries = [LogEntry(**parse(line)) for line in raw_logs]

    # Stub log entries representative of each failure type
    stub_messages = _generate_stub_logs(service, failure_type)
    log_entries = [
        LogEntry(service=service, level="ERROR", message=msg)
        for msg in stub_messages
    ]

    # Extract error patterns
    combined_text = " ".join(stub_messages)
    patterns = _match_patterns(combined_text)

    # Build RCA findings from matched patterns
    findings: list[RCAFinding] = []
    for pattern_label in patterns:
        findings.append(
            RCAFinding(
                component=service,
                finding=pattern_label,
                confidence=0.75,   # TODO Stage 2: LLM-scored confidence
                evidence=stub_messages[:2],
            )
        )

    # TODO Stage 2: use LLM to generate additional findings from unstructured logs

    note = f"LogAnalysisAgent: {len(log_entries)} log entries, {len(findings)} RCA findings, patterns={patterns}"
    audit = f"[{incident_id}] LogAnalysisAgent: findings={len(findings)}, patterns={patterns}"

    return {
        "log_entries": [e.model_dump(mode="json") for e in log_entries],
        "rca_findings": [f.model_dump(mode="json") for f in findings],
        "error_patterns": patterns,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["log_analysis_agent"],
    }


def _generate_stub_logs(service: str, failure_type: str) -> list[str]:
    """
    Generate realistic stub log lines for a given failure type.
    Used only in Stage 1 / mock mode — Stage 2 replaces with real log queries.
    """
    _STUB_LOGS: dict[str, list[str]] = {
        "service_crash": [
            f"[FATAL] {service}: Unhandled exception — NullPointerException in WorkerThread",
            f"[ERROR] {service}: OOMKill — container exceeded memory limit 2Gi",
            f"[ERROR] {service}: Readiness probe failing /health — HTTP 503",
        ],
        "high_latency": [
            f"[ERROR] {service}: Request timeout after 30s — downstream payment-gateway",
            f"[WARN]  {service}: p99 latency 4200ms exceeds SLO threshold 500ms",
            f"[ERROR] {service}: Circuit breaker open for auth-service",
        ],
        "db_connection_failure": [
            f"[ERROR] {service}: Connection refused — postgresql:5432",
            f"[ERROR] {service}: Database deadlock — lock wait timeout exceeded",
            f"[WARN]  {service}: Connection pool exhausted — waiting threads: 47",
        ],
        "failed_job": [
            f"[ERROR] {service}: Job execution failed — exit code 1",
            f"[ERROR] {service}: timed out waiting for task queue response",
            f"[WARN]  {service}: Retry attempt 3/3 failed",
        ],
        "bad_deployment": [
            f"[ERROR] {service}: Deployment rollout stalled — readiness probe failure",
            f"[ERROR] {service}: New version v2.3.1 crash-looping — OOMKilled",
            f"[WARN]  {service}: Pod restartCount=5 in last 10 minutes",
        ],
    }
    return _STUB_LOGS.get(failure_type, [f"[ERROR] {service}: Unknown failure type: {failure_type}"])


# ── Agent class ────────────────────────────────────────────────────────────────

class LogAnalysisAgent:
    """
    Reusable log analysis agent class with configurable log source.
    Stage 2 will inject a real log source (Elasticsearch, Loki, etc.)
    """

    def __init__(self, log_source=None, llm=None) -> None:
        self._log_source = log_source   # TODO Stage 2
        self._llm = llm                 # TODO Stage 2

    def run_node(self, state: AIOpsWorkflowState) -> dict[str, Any]:
        """Delegate to the module-level LangGraph node function."""
        return log_analysis_agent(state)
