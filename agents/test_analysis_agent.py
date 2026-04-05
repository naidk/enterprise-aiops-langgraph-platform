"""
Test Analysis Agent — scans and simulates running test suites.

Responsibility:
    - Map the failure type to relevant test files.
    - Simulate running unit and integration tests.
    - Report pass/fail results for the implicated modules.
"""
from __future__ import annotations

import logging
import random
from typing import Any

from app.schemas import TestResult, FailureType
from app.state import AIOpsWorkflowState

logger = logging.getLogger(__name__)


def test_analysis_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Test Analysis Agent.
    
    Analyses test coverage and simulates running relevant tests.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]
    
    logger.info("TestAnalysisAgent: running tests for %s", service)
    
    results: list[TestResult] = []
    
    # Simulate test scenarios
    if failure_type == FailureType.SERVICE_CRASH.value:
        results.append(TestResult(
            test_name=f"tests/unit/test_{service.replace('-', '_')}.py::test_init",
            status="FAIL",
            message="RuntimeError: Failed to initialize service",
            module=service,
            duration_ms=12.5
        ))
    elif failure_type == FailureType.DB_CONNECTION_FAILURE.value:
        results.append(TestResult(
            test_name="tests/integration/test_db.py::test_connection",
            status="FAIL",
            message="ConnectionRefusedError: [Errno 111] Connection refused",
            module="infra",
            duration_ms=45.2
        ))
    elif failure_type == FailureType.REPO_BUG.value:
        results.append(TestResult(
            test_name=f"tests/unit/test_{service.replace('-', '_')}.py::test_imports",
            status="ERROR",
            message="ImportError: cannot import name 'LegacyClient' from 'app.clients'",
            module=service,
            duration_ms=5.1
        ))
    else:
        # Default: some tests passing, some unrelated
        results.append(TestResult(
            test_name="tests/unit/test_health.py::test_health_endpoint",
            status="PASS",
            module="core",
            duration_ms=8.0
        ))

    note = f"TestAnalysisAgent: simulated {len(results)} tests, {sum(1 for r in results if r.status == 'FAIL' or r.status == 'ERROR')} failures."
    audit = f"[{incident_id}] TestAnalysisAgent: scanned {service}. Failures: {sum(1 for r in results if r.status != 'PASS')}"
    
    return {
        "test_results": [r.model_dump(mode="json") for r in results],
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["test_analysis_agent"],
    }
