"""
Pipeline Simulator Service.

Simulates a production microservice environment that can generate
realistic failure events for each of the five supported failure types.
Used by the dashboard, integration tests, and the /pipeline/trigger API endpoint.

Stage 2 will add:
    - A background thread / asyncio task for continuous event emission
    - Configurable failure rate, burst mode, and correlated multi-service failures
    - Replay of historical incident logs for regression testing
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Iterator

from app.config import settings
from app.schemas import FailureType, PipelineEvent

logger = logging.getLogger(__name__)


# ── Failure scenario templates ─────────────────────────────────────────────────

_SCENARIOS: dict[str, list[dict]] = {
    FailureType.SERVICE_CRASH.value: [
        {"service": "payment-service",      "error_code": "OOMKilled",         "message": "Container memory limit exceeded — 2Gi. Pod restarted 3 times."},
        {"service": "auth-service",         "error_code": "NullPointerException", "message": "Fatal exception in WorkerThread. Service unavailable."},
        {"service": "order-processor",      "error_code": "SIGSEGV",            "message": "Segmentation fault in native library. Core dump written."},
    ],
    FailureType.HIGH_LATENCY.value: [
        {"service": "api-gateway",          "error_code": "TIMEOUT",            "message": "p99 latency 4,200ms — SLO threshold 500ms breached."},
        {"service": "recommendation-engine","error_code": "SLOW_QUERY",         "message": "ML inference timeout — model load taking >10s per request."},
        {"service": "search-service",       "error_code": "QUEUE_BACKLOG",      "message": "Request queue depth 12,000 — consumers lagging 45 minutes."},
    ],
    FailureType.DB_CONNECTION_FAILURE.value: [
        {"service": "inventory-service",    "error_code": "ECONNREFUSED",       "message": "PostgreSQL connection refused on port 5432. Pool exhausted."},
        {"service": "user-service",         "error_code": "DEADLOCK",           "message": "Deadlock detected — lock wait timeout 30s exceeded."},
        {"service": "reporting-service",    "error_code": "MAX_CONNECTIONS",    "message": "MySQL max_connections (500) reached. New connections rejected."},
    ],
    FailureType.FAILED_JOB.value: [
        {"service": "etl-pipeline",         "error_code": "EXIT_CODE_1",        "message": "Spark job failed — stage 3/7 executor lost. Data incomplete."},
        {"service": "notification-service", "error_code": "SMTP_ERROR",         "message": "Email batch job failed — SMTP connection refused."},
        {"service": "billing-worker",       "error_code": "STRIPE_TIMEOUT",     "message": "Billing job timed out — Stripe API unresponsive after 30s."},
    ],
    FailureType.BAD_DEPLOYMENT.value: [
        {"service": "payment-service",      "error_code": "READINESS_PROBE_FAIL", "message": "v2.3.1 rollout stalled — readiness probe /health returning 503."},
        {"service": "frontend",             "error_code": "CONFIG_ERROR",       "message": "Missing env var API_BASE_URL in new deployment — 500 on all routes."},
        {"service": "ml-serving",           "error_code": "MODEL_LOAD_FAIL",    "message": "New model version incompatible with serving framework. Crash loop."},
    ],
}

_ALL_SERVICES = list({s["service"] for scenarios in _SCENARIOS.values() for s in scenarios})


class PipelineSimulator:
    """
    Simulates a live microservice pipeline by generating PipelineEvent objects.

    Usage:
        sim = PipelineSimulator()
        event = sim.emit_event(failure_type=FailureType.SERVICE_CRASH)
        event = sim.emit_random_event()
    """

    def __init__(self, failure_rate: float | None = None, seed: int | None = None) -> None:
        """
        Args:
            failure_rate: Probability 0–1 that emit_random_event() produces a failure.
                          Defaults to SIMULATOR_FAILURE_RATE from config.
            seed:         RNG seed for deterministic test output.
        """
        self._failure_rate = failure_rate if failure_rate is not None else settings.simulator_failure_rate
        self._rng = random.Random(seed)
        logger.info("PipelineSimulator initialised (failure_rate=%.0f%%)", self._failure_rate * 100)

    def emit_event(
        self,
        failure_type: str | FailureType,
        service: str | None = None,
        metadata: dict | None = None,
    ) -> PipelineEvent:
        """
        Emit a specific failure event.

        Args:
            failure_type: FailureType enum value or string.
            service:      Override the default service. Random if None.
            metadata:     Extra key-value context attached to the event.
        """
        ft = failure_type.value if isinstance(failure_type, FailureType) else failure_type
        scenarios = _SCENARIOS.get(ft, [])

        if not scenarios:
            logger.warning("No scenarios defined for failure_type=%s", ft)
            scenario = {"service": service or "unknown-service", "error_code": "UNKNOWN", "message": f"Simulated {ft} failure"}
        else:
            scenario = self._rng.choice(scenarios)

        chosen_service = service or scenario["service"]

        event = PipelineEvent(
            event_id=f"EVT-{str(uuid.uuid4())[:8].upper()}",
            service=chosen_service,
            failure_type=FailureType(ft),
            message=scenario["message"],
            error_code=scenario.get("error_code"),
            metadata=metadata or {"simulated": True, "failure_rate": self._failure_rate},
            timestamp=datetime.now(timezone.utc),
        )

        logger.info("PipelineSimulator: emitted %s for %s", ft, chosen_service)
        return event

    def emit_random_event(self) -> PipelineEvent | None:
        """
        Randomly decide whether to emit a failure event.
        Returns None if no failure this tick (probability = 1 - failure_rate).
        """
        if self._rng.random() > self._failure_rate:
            return None

        failure_type = self._rng.choice(list(FailureType))
        while failure_type == FailureType.UNKNOWN:
            failure_type = self._rng.choice(list(FailureType))

        return self.emit_event(failure_type)

    def stream_events(self, count: int = 10) -> Iterator[PipelineEvent]:
        """
        Yield a stream of failure events for batch testing or dashboard replay.

        Args:
            count: Number of events to generate.
        """
        for _ in range(count):
            event = self.emit_random_event()
            if event:
                yield event

    def all_failure_types(self) -> list[str]:
        """Return all supported failure type names."""
        return [ft.value for ft in FailureType if ft != FailureType.UNKNOWN]

    def all_services(self) -> list[str]:
        """Return all simulated service names."""
        return _ALL_SERVICES
