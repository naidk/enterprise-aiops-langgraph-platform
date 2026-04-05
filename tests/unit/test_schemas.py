"""
Unit tests — Pydantic schema validation.

Tests that all schemas validate correctly, reject bad input,
and serialise to / deserialise from JSON losslessly.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    AuditEntry,
    FailureType,
    Incident,
    IncidentStatus,
    JiraTicket,
    PipelineEvent,
    RCAFinding,
    RemediationActionType,
    RemediationStep,
    Severity,
)


class TestPipelineEvent:
    def test_valid_event(self) -> None:
        event = PipelineEvent(
            service="payment-service",
            failure_type=FailureType.SERVICE_CRASH,
            message="OOMKilled",
        )
        assert event.service == "payment-service"
        assert event.event_id.startswith("EVT-")

    def test_event_id_auto_generated(self) -> None:
        e1 = PipelineEvent(service="a", failure_type=FailureType.HIGH_LATENCY, message="x")
        e2 = PipelineEvent(service="a", failure_type=FailureType.HIGH_LATENCY, message="x")
        assert e1.event_id != e2.event_id

    def test_json_roundtrip(self, sample_pipeline_event: PipelineEvent) -> None:
        data = sample_pipeline_event.model_dump(mode="json")
        restored = PipelineEvent(**data)
        assert restored.event_id == sample_pipeline_event.event_id
        assert restored.service == sample_pipeline_event.service


class TestRCAFinding:
    def test_confidence_must_be_between_0_and_1(self) -> None:
        with pytest.raises(ValidationError):
            RCAFinding(component="svc", finding="bad", confidence=1.5)

    def test_valid_finding(self) -> None:
        f = RCAFinding(component="db", finding="connection exhausted", confidence=0.9)
        assert f.confidence == 0.9


class TestRemediationStep:
    def test_priority_must_be_1_to_5(self) -> None:
        with pytest.raises(ValidationError):
            RemediationStep(action=RemediationActionType.RESTART_SERVICE, description="x", priority=0)

    def test_duration_must_be_at_least_1(self) -> None:
        with pytest.raises(ValidationError):
            RemediationStep(action=RemediationActionType.RESTART_SERVICE, description="x", estimated_duration_seconds=0)

    def test_valid_step(self) -> None:
        step = RemediationStep(
            action=RemediationActionType.ROLLBACK_DEPLOYMENT,
            description="Rollback payment-service",
            command="kubectl rollout undo deployment/payment-service",
            priority=1,
        )
        assert step.requires_approval is True


class TestIncident:
    def test_incident_id_auto_generated(self) -> None:
        from app.schemas import PipelineEvent
        event = PipelineEvent(service="svc", failure_type=FailureType.FAILED_JOB, message="x")
        inc = Incident(failure_type=FailureType.FAILED_JOB, service="svc")
        assert inc.incident_id.startswith("INC-")

    def test_is_resolved_property(self) -> None:
        inc = Incident(service="svc") 
        inc.status = IncidentStatus.RESOLVED
        assert inc.is_resolved is True

    def test_duration_seconds_none_when_not_resolved(self) -> None:
        inc = Incident(service="svc") 
        assert inc.duration_seconds is None


class TestJiraTicket:
    def test_ticket_id_auto_generated(self) -> None:
        t = JiraTicket(title="Test", description="desc", severity=Severity.HIGH)
        assert len(t.ticket_id) > 4

    def test_json_roundtrip(self) -> None:
        t = JiraTicket(title="T", description="D", severity=Severity.CRITICAL)
        data = t.model_dump(mode="json")
        restored = JiraTicket(**data)
        assert restored.ticket_id == t.ticket_id
