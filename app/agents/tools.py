"""
Agent tools — deterministic lookups that simulate what a real observability
stack would provide (Prometheus queries, log search, CMDB lookups, etc.).

In production, replace these with live API calls to your data sources.
The interface is intentionally kept simple so the node functions remain
testable without any external dependencies.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from app.domain.models import MetricSnapshot


def fetch_service_metrics(service: str, window_minutes: int = 30) -> list[MetricSnapshot]:
    """
    Retrieve recent metric snapshots for a service.

    Production swap: query Prometheus / Datadog / CloudWatch.
    """
    base_ts = datetime.now(timezone.utc)
    rng = random.Random(service)  # deterministic per service name for demos

    return [
        MetricSnapshot(
            metric_name="cpu_usage_percent",
            value=round(rng.uniform(70, 99), 1),
            unit="%",
            timestamp=base_ts,
            tags={"service": service, "window": f"{window_minutes}m"},
        ),
        MetricSnapshot(
            metric_name="memory_usage_percent",
            value=round(rng.uniform(60, 95), 1),
            unit="%",
            timestamp=base_ts,
            tags={"service": service},
        ),
        MetricSnapshot(
            metric_name="http_error_rate",
            value=round(rng.uniform(5, 45), 2),
            unit="%",
            timestamp=base_ts,
            tags={"service": service, "status_code": "5xx"},
        ),
        MetricSnapshot(
            metric_name="p99_latency_ms",
            value=round(rng.uniform(800, 5000), 0),
            unit="ms",
            timestamp=base_ts,
            tags={"service": service},
        ),
    ]


def search_recent_logs(service: str, severity_filter: str = "ERROR", limit: int = 5) -> list[str]:
    """
    Retrieve recent error log lines for a service.

    Production swap: query Elasticsearch / CloudWatch Logs / Loki.
    """
    templates = [
        f"[ERROR] {service}: Connection pool exhausted — waiting threads: 47",
        f"[ERROR] {service}: OOMKilled — container exceeded memory limit 2Gi",
        f"[WARN]  {service}: Circuit breaker OPEN for downstream auth-service",
        f"[ERROR] {service}: DB query timeout after 30s — query: SELECT * FROM orders",
        f"[ERROR] {service}: Deployment rollout stalled — readiness probe failing /health",
        f"[FATAL] {service}: Unhandled exception in worker thread — NullPointerException",
        f"[ERROR] {service}: Redis connection refused — host: redis-primary:6379",
        f"[WARN]  {service}: Disk usage at 94% on /data — write throttling engaged",
    ]
    rng = random.Random(service + severity_filter)
    return rng.sample(templates, min(limit, len(templates)))


def lookup_recent_deployments(service: str) -> list[dict]:
    """
    Check for recent deployments that could correlate with the incident.

    Production swap: query Argo CD / Spinnaker / GitHub Deployments API.
    """
    rng = random.Random(service)
    deployed_mins_ago = rng.randint(5, 120)
    version = f"v{rng.randint(1,5)}.{rng.randint(0,9)}.{rng.randint(0,20)}"
    return [
        {
            "service": service,
            "version": version,
            "deployed_by": "ci-pipeline",
            "deployed_minutes_ago": deployed_mins_ago,
            "environment": "production",
            "change_risk": "medium" if deployed_mins_ago < 30 else "low",
        }
    ]


def check_downstream_dependencies(service: str) -> dict[str, str]:
    """
    Probe health of services that the affected service depends on.

    Production swap: query your service mesh (Istio) or health-check endpoints.
    """
    deps = {
        "postgresql": "degraded",
        "redis": "healthy",
        "auth-service": "healthy",
        "payment-gateway": "degraded",
        "message-queue": "healthy",
    }
    rng = random.Random(service)
    # Randomly flip one dep to unhealthy to make the demo interesting
    unhealthy_dep = rng.choice(list(deps.keys()))
    deps[unhealthy_dep] = "unhealthy"
    return deps
