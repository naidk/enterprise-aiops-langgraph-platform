"""
Unit tests — individual agent node functions.

Each test calls the node function directly (not via LangGraph) to
keep tests fast and isolated from graph wiring.
"""
from __future__ import annotations

import pytest

from agents.incident_classifier_agent import incident_classifier_agent
from agents.log_analysis_agent import log_analysis_agent
from agents.monitoring_agent import monitoring_agent
from agents.remediation_agent import remediation_agent
from agents.validation_agent import validation_agent
from agents.jira_reporting_agent import jira_reporting_agent
from app.schemas import IncidentStatus, Severity


class TestMonitoringAgent:
    def test_returns_event_detected_true(self, sample_initial_state: dict) -> None:
        result = monitoring_agent(sample_initial_state)
        assert result["event_detected"] is True

    def test_returns_event_summary_string(self, sample_initial_state: dict) -> None:
        result = monitoring_agent(sample_initial_state)
        assert isinstance(result["event_summary"], str)
        assert len(result["event_summary"]) > 0

    def test_appends_to_execution_path(self, sample_initial_state: dict) -> None:
        result = monitoring_agent(sample_initial_state)
        assert "monitoring_agent" in result["execution_path"]

    def test_appends_to_audit_trail(self, sample_initial_state: dict) -> None:
        result = monitoring_agent(sample_initial_state)
        assert len(result["audit_trail"]) > 0


class TestLogAnalysisAgent:
    def test_returns_log_entries_list(self, sample_initial_state: dict) -> None:
        result = log_analysis_agent(sample_initial_state)
        assert isinstance(result["log_entries"], list)
        assert len(result["log_entries"]) > 0

    def test_returns_rca_findings_list(self, sample_initial_state: dict) -> None:
        result = log_analysis_agent(sample_initial_state)
        assert isinstance(result["rca_findings"], list)

    def test_returns_error_patterns_list(self, sample_initial_state: dict) -> None:
        result = log_analysis_agent(sample_initial_state)
        assert isinstance(result["error_patterns"], list)

    def test_all_failure_types_produce_log_entries(
        self, sample_initial_state: dict, all_failure_types: list[str]
    ) -> None:
        for ft in all_failure_types:
            state = {**sample_initial_state, "failure_type": ft}
            result = log_analysis_agent(state)
            assert len(result["log_entries"]) > 0, f"No logs for {ft}"


class TestIncidentClassifierAgent:
    def test_service_crash_is_critical(self, sample_initial_state: dict) -> None:
        result = incident_classifier_agent(sample_initial_state)
        assert result["severity"] == Severity.CRITICAL.value

    def test_failed_job_is_medium(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "failure_type": "failed_job", "error_patterns": []}
        result = incident_classifier_agent(state)
        assert result["severity"] == Severity.MEDIUM.value

    def test_critical_triggers_escalation(self, sample_initial_state: dict) -> None:
        result = incident_classifier_agent(sample_initial_state)
        assert result["escalate"] is True

    def test_medium_does_not_escalate(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "failure_type": "failed_job", "error_patterns": []}
        result = incident_classifier_agent(state)
        assert result["escalate"] is False

    def test_confidence_in_valid_range(self, sample_initial_state: dict) -> None:
        result = incident_classifier_agent(sample_initial_state)
        assert 0.0 <= result["classification_confidence"] <= 1.0


class TestRemediationAgent:
    def test_escalated_incident_skips_remediation(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "escalate": True}
        result = remediation_agent(state)
        assert result["remediation_executed"] is False
        assert result["remediation_plan"] == []

    def test_non_escalated_incident_builds_plan(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "escalate": False, "failure_type": "high_latency"}
        result = remediation_agent(state)
        assert len(result["remediation_plan"]) > 0
        assert result["remediation_executed"] is True

    def test_remediation_attempts_increments(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "escalate": False, "failure_type": "failed_job", "remediation_attempts": 1}
        result = remediation_agent(state)
        assert result["remediation_attempts"] == 2


class TestValidationAgent:
    def test_escalated_incident_skips_validation(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "escalate": True, "remediation_executed": False}
        result = validation_agent(state)
        assert result["validation_passed"] is False
        assert result["final_status"] == IncidentStatus.ESCALATED.value

    def test_successful_remediation_passes_validation(self, sample_initial_state: dict) -> None:
        state = {
            **sample_initial_state,
            "escalate": False,
            "remediation_executed": True,
            "remediation_success": True,
        }
        result = validation_agent(state)
        assert result["validation_passed"] is True
        assert result["final_status"] == IncidentStatus.RESOLVED.value

    def test_failed_remediation_fails_validation(self, sample_initial_state: dict) -> None:
        state = {
            **sample_initial_state,
            "escalate": False,
            "remediation_executed": True,
            "remediation_success": False,
        }
        result = validation_agent(state)
        assert result["validation_passed"] is False


class TestJiraReportingAgent:
    def test_creates_ticket_with_correct_status(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "final_status": IncidentStatus.RESOLVED.value}
        result = jira_reporting_agent(state)
        assert result["jira_ticket"]["status"] == "Resolved"
        assert result["jira_ticket"]["incident_id"] == state["incident_id"]

    def test_escalated_status_mapped_correctly(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "final_status": IncidentStatus.ESCALATED.value}
        result = jira_reporting_agent(state)
        assert result["jira_ticket"]["status"] == "Escalated"
        assert "jira_reporting_agent" in result["execution_path"]
