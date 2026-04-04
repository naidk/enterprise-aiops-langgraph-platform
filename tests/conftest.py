"""
Pytest configuration and shared fixtures.

Fixtures defined here are available to all test modules across
unit/, integration/, and regression/ without explicit imports.

Stage 2 will add:
    - A real IncidentService fixture pointing to a temp JSON file
    - A FastAPI TestClient fixture for API integration tests
    - A compiled LangGraph fixture with mock agents injected
    - A PipelineSimulator fixture with a fixed RNG seed
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.schemas import FailureType, PipelineEvent


@pytest.fixture(scope="session")
def sample_pipeline_event() -> PipelineEvent:
    """A fixed, deterministic PipelineEvent for use in all tests."""
    return PipelineEvent(
        event_id="EVT-TEST0001",
        service="payment-service",
        failure_type=FailureType.SERVICE_CRASH,
        message="OOMKilled — container exceeded memory limit 2Gi",
        error_code="OOMKilled",
        metadata={"simulated": True, "test": True},
    )


@pytest.fixture(scope="session")
def sample_initial_state(sample_pipeline_event) -> dict:
    """Fully initialised AIOpsWorkflowState seed dict for graph tests."""
    from app.state import build_initial_state
    return build_initial_state(
        incident_id="INC-TEST0001",
        service=sample_pipeline_event.service,
        failure_type=sample_pipeline_event.failure_type.value,
        raw_event=sample_pipeline_event.model_dump(mode="json"),
    )


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Temporary directory for JSON storage in tests (isolated per test)."""
    incidents = tmp_path / "incidents.json"
    audit = tmp_path / "audit_log.json"
    metrics = tmp_path / "metrics.json"
    incidents.write_text("[]")
    audit.write_text("[]")
    metrics.write_text("{}")
    return tmp_path


@pytest.fixture
def incident_service(temp_storage_dir: Path):
    """IncidentService backed by a temporary JSON file."""
    from services.incident_service import IncidentService
    return IncidentService(storage_path=str(temp_storage_dir / "incidents.json"))


@pytest.fixture
def pipeline_simulator():
    """PipelineSimulator with fixed seed for deterministic test output."""
    from services.pipeline_simulator import PipelineSimulator
    return PipelineSimulator(failure_rate=1.0, seed=42)


@pytest.fixture
def all_failure_types() -> list[str]:
    """All non-unknown FailureType values."""
    return [ft.value for ft in FailureType if ft != FailureType.UNKNOWN]
