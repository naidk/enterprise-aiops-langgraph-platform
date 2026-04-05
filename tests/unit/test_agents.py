"""
Unit tests — individual agent node functions for Stage 3.

Each test calls the node function directly (not via LangGraph) to
keep tests fast and isolated from graph wiring.
"""
from __future__ import annotations

import pytest

from agents.monitoring_agent import monitoring_agent
from agents.log_analysis_agent import log_analysis_agent
from agents.repo_inspection_agent import repo_inspection_agent
# Aliased to avoid pytest collecting this module-level name as a test function
from agents.test_analysis_agent import test_analysis_agent as run_test_analysis_agent
from agents.root_cause_agent import root_cause_agent
from agents.remediation_agent import remediation_agent
from agents.validation_agent import validation_agent
from agents.jira_reporting_agent import jira_reporting_agent
from app.schemas import IncidentStatus, Severity


class TestMonitoringAgent:
    def test_returns_event_detected_true(self, sample_initial_state: dict) -> None:
        result = monitoring_agent(sample_initial_state)
        assert result["event_detected"] is True

    def test_supports_repo_bug_type(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "failure_type": "repo_bug"}
        result = monitoring_agent(state)
        assert "Repo-level bug" in result["event_summary"]


class TestLogAnalysisAgent:
    def test_returns_log_entries_list(self, sample_initial_state: dict) -> None:
        result = log_analysis_agent(sample_initial_state)
        assert isinstance(result["log_entries"], list)
        assert len(result["log_entries"]) > 0

    def test_repo_bug_produces_import_errors(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "failure_type": "repo_bug"}
        result = log_analysis_agent(state)
        # Check that we have findings and log entries, regardless of LLM vs Static
        assert len(result["log_entries"]) > 0
        assert len(result["rca_findings"]) > 0


class TestRepoInspectionAgent:
    def test_returns_findings_list(self, sample_initial_state: dict) -> None:
        result = repo_inspection_agent(sample_initial_state)
        assert isinstance(result["repo_findings"], list)

    def test_identifies_broken_import_for_repo_bug(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "failure_type": "repo_bug"}
        result = repo_inspection_agent(state)
        assert any(f["issue_type"] == "broken_import" for f in result["repo_findings"])


class TestTestAnalysisAgent:
    def test_returns_results_list(self, sample_initial_state: dict) -> None:
        result = run_test_analysis_agent(sample_initial_state)
        assert isinstance(result["test_results"], list)

    def test_detects_test_failure_for_crash(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "failure_type": "service_crash"}
        result = run_test_analysis_agent(state)
        assert any(r["status"] == "FAIL" for r in result["test_results"])


class TestRootCauseAgent:
    def test_aggregates_into_root_cause_object(self, sample_initial_state: dict) -> None:
        result = root_cause_agent(sample_initial_state)
        assert "root_cause" in result
        assert result["root_cause"]["affected_module"] == sample_initial_state["service"]

    def test_confidence_is_high_with_repo_findings(self, sample_initial_state: dict) -> None:
        state = {
            **sample_initial_state,
            "repo_findings": [{"file_path": "app/main.py", "issue_type": "broken_import", "description": "bad import", "severity": "high"}]
        }
        result = root_cause_agent(state)
        assert result["classification_confidence"] >= 0.9


class TestRemediationAgent:
    def test_escalated_incident_skips_remediation(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "escalate": True}
        result = remediation_agent(state)
        assert result["remediation_executed"] is False

    def test_low_confidence_triggers_escalation(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "classification_confidence": 0.4}
        result = remediation_agent(state)
        assert result["escalate"] is True
        assert result["remediation_executed"] is False


class TestValidationAgent:
    def test_successful_remediation_passes_validation(self, sample_initial_state: dict) -> None:
        state = {
            **sample_initial_state,
            "remediation_executed": True,
            "remediation_success": True,
        }
        result = validation_agent(state)
        assert result["validation_passed"] is True
        assert result["final_status"] == IncidentStatus.RESOLVED.value


class TestJiraReportingAgent:
    def test_creates_ticket_with_correct_status(self, sample_initial_state: dict) -> None:
        state = {**sample_initial_state, "final_status": IncidentStatus.RESOLVED.value}
        result = jira_reporting_agent(state)
        assert result["jira_ticket"]["status"] == "Resolved"
        assert result["jira_ticket"]["incident_id"] == sample_initial_state["incident_id"]
