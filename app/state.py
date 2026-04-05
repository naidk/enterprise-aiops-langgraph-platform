"""
LangGraph shared state for the AIOps multi-agent workflow.

AIOpsWorkflowState flows through every node in the graph:

    START
      │
    monitoring_agent      ← detects failure, creates PipelineEvent
      │
    log_analysis_agent    ← parses logs, extracts patterns
      │
    incident_classifier   ← determines severity and failure type
      │
    remediation_agent     ← builds and executes remediation plan
      │
    validation_agent      ← verifies the fix worked
      │
    jira_reporting_agent  ← creates/updates Jira-style ticket
      │
    END

Accumulating fields (Annotated with operator.add) are appended by
each node rather than replaced, preserving the full audit trail.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

# ── Serialised-model type aliases ─────────────────────────────────────────────
# These dict types represent Pydantic models serialised via .model_dump(mode="json").
# Use the corresponding Pydantic class for validation: LogEntry.model_validate(d)
#
#   LogEntryDict      → app.schemas.LogEntry
#   RCAFindingDict    → app.schemas.RCAFinding
#   RepoFindingDict   → app.schemas.RepoFinding
#   TestResultDict    → app.schemas.TestResult
#   RemStepDict       → app.schemas.RemediationStep
#   RootCauseDict     → app.schemas.RootCauseAnalysis
#   JiraTicketDict    → app.schemas.JiraTicket
LogEntryDict    = dict[str, Any]
RCAFindingDict  = dict[str, Any]
RepoFindingDict = dict[str, Any]
TestResultDict  = dict[str, Any]
RemStepDict     = dict[str, Any]
RootCauseDict   = dict[str, Any]
JiraTicketDict  = dict[str, Any]


class AIOpsWorkflowState(TypedDict):
    """
    Shared state flowing through all LangGraph agent nodes.

    Initialisation:
        Every field must be present in the seed dict passed to graph.invoke().
        Use build_initial_state() to construct it correctly.
    """

    # ── Pipeline input ────────────────────────────────────────────────────────
    incident_id: str               # Unique incident identifier
    service: str                   # Affected service name
    failure_type: str              # FailureType enum value
    raw_event: dict[str, Any]      # Serialised PipelineEvent

    # ── Monitoring agent outputs ──────────────────────────────────────────────
    event_detected: bool           # Whether a real failure was confirmed
    event_summary: str             # One-line summary of the detected event

    # ── Log analysis outputs ──────────────────────────────────────────────────
    log_entries: list[LogEntryDict]        # Serialised LogEntry list
    rca_findings: list[RCAFindingDict]     # Serialised RCAFinding list
    error_patterns: list[str]              # Extracted error pattern strings
    repo_findings: list[RepoFindingDict]   # Serialised RepoFinding list
    test_results: list[TestResultDict]     # Serialised TestResult list

    # ── Incident classifier / RCA outputs ─────────────────────────────────────
    severity: str                  # Severity enum value (e.g. "critical")
    classification_confidence: float
    escalate: bool                 # True → skip auto-remediation, page human
    root_cause: Optional[RootCauseDict]    # Serialised RootCauseAnalysis or None

    # ── Remediation agent outputs ─────────────────────────────────────────────
    remediation_plan: list[RemStepDict]    # Serialised RemediationStep list
    remediation_executed: bool
    remediation_success: bool
    remediation_attempts: int

    # ── Validation agent outputs ──────────────────────────────────────────────
    validation_passed: bool
    validation_details: str
    final_status: str              # IncidentStatus enum value (e.g. "resolved")

    # ── Code fix agent outputs ────────────────────────────────────────────────
    code_fix: Optional[dict[str, Any]]     # LLM-generated code fix + PR URL

    # ── Injected logs (from crash injection) ──────────────────────────────────
    injected_logs: Optional[str]           # Real crash logs from failure injector

    # ── Jira reporting outputs ────────────────────────────────────────────────
    jira_ticket: Optional[JiraTicketDict]  # Serialised JiraTicket or None
    jira_ticket_url: Optional[str]

    # ── Accumulating fields (operator.add = list concatenation) ───────────────
    agent_notes: Annotated[list[str], operator.add]   # All agent notes in order
    audit_trail: Annotated[list[str], operator.add]   # Full audit chain
    execution_path: Annotated[list[str], operator.add]  # Which nodes ran


def build_initial_state(
    incident_id: str,
    service: str,
    failure_type: str,
    raw_event: dict[str, Any],
) -> AIOpsWorkflowState:
    """
    Construct a fully-initialised seed state for a new workflow run.
    All fields must be present for LangGraph to accept the state.

    Args:
        incident_id: Pre-generated incident ID (e.g. "INC-ABC12345").
        service:     Name of the affected service.
        failure_type: FailureType enum value string.
        raw_event:   Serialised PipelineEvent dict.
    """
    return {
        # Input
        "incident_id": incident_id,
        "service": service,
        "failure_type": failure_type,
        "raw_event": raw_event,

        # Monitoring
        "event_detected": False,
        "event_summary": "",

        # Log and code analysis
        "log_entries": [],
        "rca_findings": [],
        "error_patterns": [],
        "repo_findings": [],
        "test_results": [],

        # Classification / RCA
        "severity": "unknown",
        "classification_confidence": 0.0,
        "escalate": False,
        "root_cause": None,

        # Remediation
        "remediation_plan": [],
        "remediation_executed": False,
        "remediation_success": False,
        "remediation_attempts": 0,

        # Validation
        "validation_passed": False,
        "validation_details": "",
        "final_status": "open",

        # Code fix
        "code_fix": None,
        "injected_logs": None,

        # Jira
        "jira_ticket": None,
        "jira_ticket_url": None,

        # Accumulating
        "agent_notes": [],
        "audit_trail": [],
        "execution_path": [],
    }
