"""
Unit tests — PipelineSimulator.

Verifies that the simulator generates valid events for all failure types
and respects the failure_rate configuration.
"""
from __future__ import annotations

import pytest

from app.schemas import FailureType, PipelineEvent
from services.pipeline_simulator import PipelineSimulator


class TestPipelineSimulator:
    def test_emit_event_returns_pipeline_event(self, pipeline_simulator: PipelineSimulator) -> None:
        event = pipeline_simulator.emit_event(FailureType.SERVICE_CRASH)
        assert isinstance(event, PipelineEvent)

    def test_emit_event_sets_correct_failure_type(self, pipeline_simulator: PipelineSimulator) -> None:
        event = pipeline_simulator.emit_event(FailureType.HIGH_LATENCY)
        assert event.failure_type == FailureType.HIGH_LATENCY

    def test_emit_event_with_custom_service(self, pipeline_simulator: PipelineSimulator) -> None:
        event = pipeline_simulator.emit_event(FailureType.FAILED_JOB, service="my-service")
        assert event.service == "my-service"

    def test_all_failure_types_produce_events(
        self, pipeline_simulator: PipelineSimulator, all_failure_types: list[str]
    ) -> None:
        for ft in all_failure_types:
            event = pipeline_simulator.emit_event(ft)
            assert event.failure_type.value == ft

    def test_failure_rate_1_always_emits(self) -> None:
        sim = PipelineSimulator(failure_rate=1.0, seed=0)
        for _ in range(10):
            assert sim.emit_random_event() is not None

    def test_failure_rate_0_never_emits(self) -> None:
        sim = PipelineSimulator(failure_rate=0.0, seed=0)
        for _ in range(10):
            assert sim.emit_random_event() is None

    def test_stream_events_yields_correct_count(self, pipeline_simulator: PipelineSimulator) -> None:
        events = list(pipeline_simulator.stream_events(count=5))
        assert len(events) == 5

    def test_event_id_is_unique_per_emission(self, pipeline_simulator: PipelineSimulator) -> None:
        e1 = pipeline_simulator.emit_event(FailureType.SERVICE_CRASH)
        e2 = pipeline_simulator.emit_event(FailureType.SERVICE_CRASH)
        assert e1.event_id != e2.event_id
