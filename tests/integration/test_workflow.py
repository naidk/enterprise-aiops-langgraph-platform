"""
Integration tests — full LangGraph AIOps workflow for Stage 3.

Runs the compiled graph end-to-end for each failure type without
mocking any agent. Uses simulated logic for all nodes.

No LLM API keys are required (LLM_PROVIDER=mock).
"""
from __future__ import annotations

import pytest

from app.schemas import FailureType, IncidentStatus
from app.state import build_initial_state


@pytest.fixture(scope="module")
def aiops_graph():
    """Compile the AIOps graph once for all integration tests in this module."""
    from graph.workflow import aiops_graph
    return aiops_graph


def _run(graph, failure_type: str, service: str = "test-service") -> dict:
    """Helper: run the graph for a given failure type and return final state."""
    import uuid
    incident_id = f"INC-TEST-{str(uuid.uuid4())[:6].upper()}"
    from app.schemas import PipelineEvent
    event = PipelineEvent(service=service, failure_type=FailureType(failure_type), message="integration test event")
    state = build_initial_state(
        incident_id=incident_id,
        service=service,
        failure_type=failure_type,
        raw_event=event.model_dump(mode="json"),
    )
    config = {"configurable": {"thread_id": incident_id}}
    return graph.invoke(state, config=config)


class TestWorkflowEndToEndStage3:
    def test_repo_bug_identified_and_mapped(self, aiops_graph) -> None:
        """REPO_BUG incidents should trigger repo inspection and test analysis."""
        state = _run(aiops_graph, "repo_bug")
        assert "repo_findings" in state
        assert len(state["repo_findings"]) > 0
        assert "test_results" in state
        assert "root_cause_agent" in state["execution_path"]
        assert "repo_inspection_agent" in state["execution_path"]
        assert "test_analysis_agent" in state["execution_path"]
        assert "Repo-level bug" in state["event_summary"]

    def test_service_crash_escalates_on_critical_severity(self, aiops_graph) -> None:
        """CRITICAL incidents (from RootCauseAgent) should be escalated."""
        state = _run(aiops_graph, "service_crash")
        # In our simulation, service_crash leads to critical severity
        assert "root_cause_agent" in state["execution_path"]
        assert state["severity"] == "critical"
        assert state["escalate"] is True
        assert "remediation_agent" not in state["execution_path"]

    def test_high_latency_goes_through_remediation(self, aiops_graph) -> None:
        """HIGH incidents should be auto-remediated."""
        state = _run(aiops_graph, "high_latency")
        assert state["escalate"] is False
        assert "remediation_agent" in state["execution_path"]
        assert "validation_agent" in state["execution_path"]
        assert len(state["remediation_plan"]) > 0

    def test_all_failure_types_complete_without_error(self, aiops_graph, all_failure_types: list[str]) -> None:
        """Smoke test: every failure type should produce a valid final state."""
        for ft in all_failure_types:
            state = _run(aiops_graph, ft)
            assert "execution_path" in state
            # monitoring -> log_analysis -> repo_inspection -> test_analysis -> root_cause -> (remed -> valid) -> jira
            assert len(state["execution_path"]) >= 6, f"{ft}: too few nodes executed"

    def test_jira_ticket_contains_rca_and_tests(self, aiops_graph) -> None:
        """Jira ticket should be enriched with new Stage 3 diagnostic data."""
        state = _run(aiops_graph, "high_latency")
        ticket = state["jira_ticket"]
        assert ticket is not None
        assert "Root Cause Analysis" in ticket["description"]
        assert "Test Results" in ticket["description"]
        assert "Repo Inspection" in ticket["description"]

    def test_remediation_safety_checks_escalate_low_confidence(self, aiops_graph) -> None:
        """Simulation: low confidence RCA should escalate instead of auto-remediate."""
        # We'll trigger a failure type not explicitly handled with high confidence
        state = _run(aiops_graph, "unknown")
        if state["classification_confidence"] < 0.6:
            assert state["escalate"] is True
            assert "remediation_agent" in state["execution_path"] # it runs but skips
            assert state["remediation_executed"] is False
