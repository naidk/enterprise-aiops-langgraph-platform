"""
Health Service.

Checks the operational health of monitored services by polling their
health endpoints, inspecting pod status, and reading recent metrics.

Stage 2 will:
    - Implement real HTTP health checks via httpx with configurable timeout
    - Query Kubernetes pod status (kubectl / Python k8s client)
    - Pull live metrics from Prometheus / Datadog / CloudWatch
    - Cache results with TTL to avoid thundering herd during incidents
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

HealthStatus = Literal["healthy", "degraded", "unhealthy", "unknown"]


@dataclass
class ServiceHealth:
    """Health snapshot for a single service."""

    service: str
    status: HealthStatus
    http_status_code: int | None = None
    response_time_ms: float | None = None
    error_message: str | None = None
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    pod_count: int = 0
    ready_pod_count: int = 0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"

    @property
    def readiness_ratio(self) -> float:
        if self.pod_count == 0:
            return 0.0
        return self.ready_pod_count / self.pod_count


class HealthService:
    """
    Checks and reports service health.

    Usage:
        svc = HealthService()
        health = svc.check("payment-service")
        print(health.status)  # "degraded"
    """

    def __init__(self, http_client=None, k8s_client=None) -> None:
        # TODO Stage 2: inject real clients
        self._http = http_client
        self._k8s = k8s_client

    def check(self, service: str) -> ServiceHealth:
        """
        Perform a health check for a named service.

        TODO Stage 2:
            response = await self._http.get(f"http://{service}/health", timeout=5)
            pod_info = self._k8s.get_deployment(service)
            return ServiceHealth(service=service, http_status_code=response.status_code, ...)
        """
        logger.debug("HealthService.check: %s", service)
        # Stub — returns degraded for demo
        return ServiceHealth(
            service=service,
            status="degraded",
            http_status_code=503,
            response_time_ms=None,
            error_message="Stub health check — Stage 2 will call real endpoints",
            pod_count=3,
            ready_pod_count=1,
        )

    def check_all(self, services: list[str]) -> dict[str, ServiceHealth]:
        """Check health for a list of services. Returns dict keyed by service name."""
        return {svc: self.check(svc) for svc in services}

    def is_recovering(self, service: str, prev_health: ServiceHealth) -> bool:
        """
        Compare current health against a previous snapshot to detect recovery.
        TODO Stage 2: implement trend analysis.
        """
        current = self.check(service)
        return current.ready_pod_count > prev_health.ready_pod_count
