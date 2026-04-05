"""
Jira Reporting Agent — final node in the AIOps LangGraph pipeline.

Responsibility:
    Create or update a Jira-style incident ticket at the end of every
    workflow run. The ticket captures the full incident lifecycle:
    detection → classification → remediation → resolution.

Stage 2 implementation will:
    - Call the real Jira REST API (or MockJiraService in test mode)
    - Attach the full agent audit trail as ticket comments
    - Set ticket priority based on incident severity
    - Link to runbooks, RCA findings, and remediation commands
    - Transition ticket status (Open → In Progress → Resolved) throughout the workflow
    - Send Slack / email notifications to the owning team
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.schemas import IncidentStatus, JiraTicket, Severity
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)

# ── Priority mapping ───────────────────────────────────────────────────────────

_SEVERITY_TO_JIRA_PRIORITY: dict[str, str] = {
    Severity.CRITICAL.value: "Highest",
    Severity.HIGH.value:     "High",
    Severity.MEDIUM.value:   "Medium",
    Severity.LOW.value:      "Low",
    Severity.UNKNOWN.value:  "Low",
}


def _build_ticket_description(state: AIOpsWorkflowState) -> str:
    """
    Compose a Jira ticket description from the full workflow state.
    Stage 2 will use an LLM to write a polished incident post-mortem.
    """
    lines = [
        f"*Incident ID:* {state['incident_id']}",
        f"*Service:* {state['service']}",
        f"*Failure Type:* {state['failure_type']}",
        f"*Severity:* {state.get('severity', 'unknown')}",
        f"*Final Status:* {state.get('final_status', 'unknown')}",
        "",
        "*Event Summary:*",
        state.get("event_summary", "N/A"),
        "",
        "*Error Patterns:*",
        "\n".join(f"- {p}" for p in state.get("error_patterns", [])) or "None detected",
        "",
        "*RCA Findings:*",
    ]
    for f in state.get("rca_findings", []):
        lines.append(f"- [{f.get('confidence', 0):.0%}] {f.get('finding', '')}")

    lines += [
        "",
        "*Repo Inspection:*",
    ]
    for r in state.get("repo_findings", []):
        lines.append(f"- [{r.get('severity', 'med')}] {r.get('issue_type', '')}: {r.get('description', '')}")

    lines += [
        "",
        "*Test Results:*",
    ]
    for t in state.get("test_results", []):
        lines.append(f"- [{t.get('status', 'FAIL')}] {t.get('test_name', '')}: {t.get('message', 'N/A')}")

    lines += [
        "",
        "*Root Cause Analysis:*",
    ]
    rc = state.get("root_cause")
    if rc:
        lines.append(f"Predicted Root Cause: {rc.get('predicted_root_cause', 'N/A')}")
        lines.append(f"Affected Module: {rc.get('affected_module', 'N/A')}")
        lines.append(f"Confidence: {rc.get('confidence', 0):.0%}")

    lines += [
        "",
        "*Remediation Steps Executed:*",
    ]
    for s in state.get("remediation_plan", []):
        lines.append(f"- P{s.get('priority', '?')}: {s.get('description', '')}")

    lines += [
        "",
        "*Validation:*",
        f"Passed: {state.get('validation_passed', False)}",
        state.get("validation_details", ""),
        "",
        "*Agent Audit Trail:*",
        "\n".join(f"- {note}" for note in state.get("audit_trail", [])),
    ]
    return "\n".join(lines)


# ── LangGraph node function ────────────────────────────────────────────────────

def jira_reporting_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Jira Reporting Agent.

    Creates a Jira-style ticket summarising the full incident lifecycle
    and posts it to the configured Jira project (or mock store).

    Args:
        state: Final AIOpsWorkflowState after all other agents have run.

    Returns:
        Partial state dict with jira_ticket and jira_ticket_url.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    severity = state.get("severity", Severity.UNKNOWN.value)
    final_status = state.get("final_status", IncidentStatus.OPEN.value)

    logger.info("JiraReportingAgent: creating ticket for %s [%s]", incident_id, severity)

    title = (
        f"[{severity.upper()}] {service} — "
        f"{state['failure_type'].replace('_', ' ').title()} — {incident_id}"
    )

    description = _build_ticket_description(state)
    priority = _SEVERITY_TO_JIRA_PRIORITY.get(severity, "Medium")

    # TODO Stage 2: call jira_service.create_ticket(title, description, priority)
    # ticket = jira_service.create_ticket(...)
    # return {"jira_ticket": ticket.model_dump(), "jira_ticket_url": ticket.url, ...}

    # Stub ticket — real Jira API call in Stage 2
    ticket = JiraTicket(
        title=title,
        description=description,
        severity=Severity(severity),
        status=final_status.replace('_', ' ').title(),
        labels=[service, state["failure_type"], severity, settings.jira_project_key],
        incident_id=incident_id,
        url=f"https://jira.example.com/browse/{settings.jira_project_key}-STUB",
    )

    note = f"JiraReportingAgent: ticket created — {ticket.ticket_id} ({priority} priority)"
    audit = f"[{incident_id}] JiraReportingAgent: ticket={ticket.ticket_id}, url={ticket.url}"

    return {
        "jira_ticket": ticket.model_dump(mode="json"),
        "jira_ticket_url": ticket.url,
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["jira_reporting_agent"],
    }


# ── Agent class ────────────────────────────────────────────────────────────────

class JiraReportingAgent:
    """
    Reusable Jira reporting agent.
    Stage 2 will inject a real JiraService (or MockJiraService for tests).
    """

    def __init__(self, jira_service=None) -> None:
        self._jira_service = jira_service  # TODO Stage 2

    def run_node(self, state: AIOpsWorkflowState) -> dict[str, Any]:
        return jira_reporting_agent(state)
