"""
Log Analysis Agent — second node in the AIOps LangGraph pipeline.

Responsibility:
    - Retrieve and parse recent log entries for the affected service.
    - Extract error patterns and signatures using LLM inference (Groq/Claude).
    - Produce structured findings for the Root Cause Agent.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas import LogEntry, RCAFinding
from app.state import AIOpsWorkflowState
from app.llm_factory import get_llm
from app.config import settings

logger = logging.getLogger(__name__)

# ── Known error patterns (Static fallback) ────────────────────────────────────
_ERROR_PATTERNS: dict[str, str] = {
    r"OOMKill|memory limit exceeded":            "Memory exhaustion — container OOMKilled",
    r"connection refused|ECONNREFUSED":          "Dependency unreachable — connection refused",
    r"timeout|timed out":                        "Request/query timeout — downstream latency",
    r"NPE|NullPointerException|null pointer":    "Null pointer exception in application code",
    r"ImportError|ModuleNotFoundError":          "Broken import — application dependency error",
}


def _detect_level(message: str) -> str:
    """Classify a log message severity level from its text content."""
    upper = message.upper()
    if "ERROR" in upper or "FATAL" in upper:
        return "ERROR"
    if "WARN" in upper:
        return "WARN"
    return "INFO"


def log_analysis_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Log Analysis Agent.

    Analyses logs using real LLM inference if enabled, otherwise falls back to
    pattern matching. When CLOUD_PROVIDER=aws is set, fetches real log messages
    from CloudWatch Logs instead of using stubs.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]

    logger.info("LogAnalysisAgent: analysing logs for %s (LLM: %s)", service, settings.llm_provider)

    # 1. Fetch Logs — real CloudWatch Logs if AWS mode is active, else stubs
    stub_messages = _generate_stub_logs(service, failure_type)
    log_entries = [LogEntry(service=service, level="ERROR", message=msg) for msg in stub_messages]

    if settings.using_aws:
        try:
            from services.aws.cloudwatch_logs import CloudWatchLogsClient  # local import
            from services.aws.boto_client import BotoClientFactory  # local import

            cw_logs_client = CloudWatchLogsClient(
                BotoClientFactory(
                    region=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    aws_session_token=settings.aws_session_token,
                    role_arn=settings.aws_role_arn,
                ),
                log_group_prefix=settings.aws_log_group_prefix,
            )
            real_logs = cw_logs_client.get_recent_logs(service, minutes=10, max_events=50)
            if real_logs:
                log_entries = [
                    LogEntry(
                        service=service,
                        level=_detect_level(entry["message"]),
                        message=entry["message"],
                    )
                    for entry in real_logs
                ]
                stub_messages = [e["message"] for e in real_logs]
                logger.info(
                    "LogAnalysisAgent: using %d real CloudWatch log entries for '%s'",
                    len(log_entries), service,
                )
            else:
                logger.info(
                    "LogAnalysisAgent: no CloudWatch logs found for '%s' — using stubs",
                    service,
                )
        except Exception as exc:
            logger.warning(
                "LogAnalysisAgent: CloudWatch Logs fetch failed for '%s' — %s; using stubs",
                service, exc,
            )

    # 2. Extract Findings (LLM vs Pattern Matching)
    findings: list[RCAFinding] = []
    patterns: list[str] = []

    if settings.using_real_llm:
        findings, patterns = _llm_log_analysis(service, stub_messages)
        # If LLM call failed or returned empty, fall back to static pattern matching
        if not findings:
            logger.info("LogAnalysisAgent: LLM returned no findings; using static pattern-matching fallback.")
            patterns = _match_patterns(" ".join(stub_messages))
            for p in patterns:
                findings.append(RCAFinding(component=service, finding=p, confidence=0.7, evidence=stub_messages[:1]))
    else:
        patterns = _match_patterns(" ".join(stub_messages))
        for p in patterns:
            findings.append(RCAFinding(component=service, finding=p, confidence=0.7, evidence=stub_messages[:1]))

    note = f"LogAnalysisAgent: {len(log_entries)} logs, {len(findings)} findings via {settings.llm_provider}"
    audit = f"[{incident_id}] LogAnalysisAgent: patterns={patterns}"

    return {
        "log_entries": [e.model_dump(mode="json") for e in log_entries],
        "rca_findings": [f.model_dump(mode="json") for f in findings],
        "error_patterns": patterns,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["log_analysis_agent"],
    }


def _llm_log_analysis(service: str, logs: list[str]) -> tuple[list[RCAFinding], list[str]]:
    """Use LLM to extract structured diagnostic findings from raw logs."""
    try:
        llm = get_llm()
        
        # Simple analysis prompt for the demo
        prompt = (
            f"Analyze the following logs for service '{service}'. "
            "Identify the technical error signature and return a short summary finding. "
            "Logs:\n" + "\n".join(logs)
        )
        
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        
        # For the demo, we create a structured finding from the LLM's text
        # in a real system, we'd use with_structured_output here too
        finding = RCAFinding(
            component=service,
            finding=content[:200], # Summary from LLM
            confidence=0.9,
            evidence=logs[:2]
        )
        return [finding], ["LLM_IDENTIFIED"]
    except Exception as e:
        logger.error("LogAnalysisAgent: LLM analysis failed: %s", e)
        return [], []


def _match_patterns(log_text: str) -> list[str]:
    """Extract all matching error pattern labels from a block of log text."""
    matched: list[str] = []
    for pattern, label in _ERROR_PATTERNS.items():
        if re.search(pattern, log_text, re.IGNORECASE):
            matched.append(label)
    return matched


def _generate_stub_logs(service: str, failure_type: str) -> list[str]:
    """Realistic stub logs for the demo."""
    _STUB_LOGS: dict[str, list[str]] = {
        "service_crash": [f"[FATAL] {service}: NullPointerException in WorkerThread", f"[ERROR] {service}: OOMKill — limit 2Gi"],
        "high_latency": [f"[ERROR] {service}: Request timeout after 30s", f"[WARN] p99 4200ms > 500ms"],
        "repo_bug": [f"[FATAL] {service}: ImportError: cannot import name 'LegacyClient' from 'app.clients'"],
    }
    return _STUB_LOGS.get(failure_type, [f"[ERROR] {service}: failure type {failure_type} observed."])
