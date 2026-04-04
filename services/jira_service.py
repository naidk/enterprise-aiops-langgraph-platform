"""
Jira Service.

Creates, updates, and transitions Jira-style incident tickets.
In Stage 1, tickets are persisted to storage/incidents.json.
When JIRA_ENABLED=true and credentials are present, Stage 2 will
call the real Jira REST API v3.

Stage 2 will:
    - Implement real Jira API v3 calls via httpx
    - Support both Jira Cloud and Jira Data Centre
    - Auto-assign tickets based on service ownership (team registry)
    - Attach runbook links, metric snapshots, and RCA findings as ticket attachments
    - Transition ticket status in sync with IncidentStatus changes
    - Post Slack notifications to the owning team's channel on creation
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.schemas import JiraTicket, Severity

logger = logging.getLogger(__name__)


class JiraService:
    """
    Creates and manages Jira-style incident tickets.

    When JIRA_ENABLED=false (default), all operations are stubbed and
    tickets are returned as in-memory JiraTicket objects without any
    external API calls.

    Usage:
        svc = JiraService()
        ticket = svc.create_ticket(title="...", description="...", severity=Severity.HIGH)
        svc.transition(ticket.ticket_id, new_status="In Progress")
    """

    def __init__(self, http_client=None) -> None:
        self._http = http_client   # TODO Stage 2: inject httpx.AsyncClient
        self._enabled = settings.jira_enabled
        logger.info("JiraService initialised (enabled=%s)", self._enabled)

    def create_ticket(
        self,
        title: str,
        description: str,
        severity: Severity,
        incident_id: str = "",
        labels: Optional[list[str]] = None,
        assignee: Optional[str] = None,
    ) -> JiraTicket:
        """
        Create a new Jira ticket.

        Args:
            title:       Short ticket title (maps to Jira Summary field).
            description: Full incident description (maps to Jira Description).
            severity:    Incident severity → Jira Priority mapping.
            incident_id: Link back to the AIOps incident record.
            labels:      List of Jira labels to apply.
            assignee:    Jira user account ID to assign.

        Returns:
            JiraTicket with populated ticket_id and url.
        """
        if self._enabled:
            # TODO Stage 2: real API call
            # response = self._http.post(
            #     f"{settings.jira_base_url}/rest/api/3/issue",
            #     json=self._build_jira_payload(title, description, severity, labels),
            #     auth=(settings.jira_user_email, settings.jira_api_token),
            # )
            # response.raise_for_status()
            # ticket_id = response.json()["key"]
            # url = f"{settings.jira_base_url}/browse/{ticket_id}"
            raise NotImplementedError("Real Jira API not yet implemented — Stage 2")

        # Stub mode — return a mock ticket
        ticket = JiraTicket(
            title=title,
            description=description,
            severity=severity,
            status="Open",
            assignee=assignee,
            labels=labels or [settings.jira_project_key, severity.value],
            incident_id=incident_id,
            url=f"https://jira.example.com/browse/{settings.jira_project_key}-STUB",
        )
        logger.info("JiraService [STUB]: created ticket %s — %s", ticket.ticket_id, title[:50])
        return ticket

    def transition(self, ticket_id: str, new_status: str) -> bool:
        """
        Transition a Jira ticket to a new status (e.g. "In Progress", "Done").

        TODO Stage 2: POST to /rest/api/3/issue/{ticket_id}/transitions
        """
        logger.debug("JiraService [STUB]: transition %s → %s", ticket_id, new_status)
        return True  # stub

    def add_comment(self, ticket_id: str, comment: str) -> bool:
        """
        Add a comment to an existing ticket.

        TODO Stage 2: POST to /rest/api/3/issue/{ticket_id}/comment
        """
        logger.debug("JiraService [STUB]: comment on %s: %s", ticket_id, comment[:80])
        return True  # stub

    def _build_jira_payload(
        self,
        title: str,
        description: str,
        severity: Severity,
        labels: Optional[list[str]],
    ) -> dict:
        """Build the Jira API v3 request payload."""
        priority_map = {
            Severity.CRITICAL: "Highest",
            Severity.HIGH: "High",
            Severity.MEDIUM: "Medium",
            Severity.LOW: "Low",
        }
        return {
            "fields": {
                "project": {"key": settings.jira_project_key},
                "summary": title,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
                },
                "issuetype": {"name": "Bug"},
                "priority": {"name": priority_map.get(severity, "Medium")},
                "labels": labels or [],
            }
        }
