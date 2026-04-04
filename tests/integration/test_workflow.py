"""
Integration tests — full LangGraph AIOps workflow.

Runs the compiled graph end-to-end for each failure type without
mocking any agent. All agents use their Stage 1 stub implementations.

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


class TestWorkflowEndToEnd:
    def test_service_crash_escalates(self, aiops_graph) -> None:
        """CRITICAL incidents should be escalated, not auto-remediated."""
        state = _run(aiops_graph, "service_crash")
        assert state["escalate"] is True
        assert state["severity"] == "critical"
        assert "monitoring_agent" in state["execution_path"]
        assert "incident_classifier_agent" in state["execution_path"]
        assert "jira_reporting_agent" in state["execution_path"]

    def test_high_latency_goes_through_remediation(self, aiops_graph) -> None:
        """HIGH incidents should be auto-remediated (not escalated)."""
        state = _run(aiops_graph, "high_latency")
        assert state["escalate"] is False
        assert "remediation_agent" in state["execution_path"]
        assert "validation_agent" in state["execution_path"]
        assert len(state["remediation_plan"]) > 0

    def test_failed_job_resolves(self, aiops_graph) -> None:
        """MEDIUM incidents should resolve after remediation + validation."""
        state = _run(aiops_graph, "failed_job")
        assert state["final_status"] == IncidentStatus.RESOLVED.value

    def test_all_failure_types_complete_without_error(self, aiops_graph, all_failure_types: list[str]) -> None:
        """Smoke test: every failure type should produce a valid final state."""
        for ft in all_failure_types:
            state = _run(aiops_graph, ft)
            assert "execution_path" in state
            assert len(state["execution_path"]) >= 3, f"{ft}: too few nodes executed"

    def test_jira_ticket_always_created(self, aiops_graph, all_failure_types: list[str]) -> None:
        """A Jira ticket should be created for every incident regardless of path."""
        for ft in all_failure_types:
            state = _run(aiops_graph, ft)
            assert state["jira_ticket"] is not None, f"No Jira ticket for {ft}"

    def test_audit_trail_is_non_empty(self, aiops_graph) -> None:
        state = _run(aiops_graph, "db_connection_failure")
        assert len(state["audit_trail"]) >= 3

    def test_agent_notes_accumulate_across_all_nodes(self, aiops_graph) -> None:
        state = _run(aiops_graph, "high_latency")
        # Expect at least one note per agent that ran
        assert len(state["agent_notes"]) >= len(state["execution_path"])
