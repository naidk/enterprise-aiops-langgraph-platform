"""
Realistic mock alert generator for demos and integration tests.

Produces a variety of alert scenarios covering the most common
AIOps use cases: service outages, latency spikes, resource exhaustion,
and deployment-induced regressions.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from app.domain.enums import AlertType
from app.domain.models import Alert

# ── Scenario templates ────────────────────────────────────────────────────────

_SCENARIOS: list[dict] = [
    {
        "source": "Prometheus",
        "service": "payment-service",
        "alert_type": AlertType.SERVICE_DOWN,
        "title": "payment-service is DOWN — health check failing",
        "description": (
            "Health check endpoint /health returning HTTP 503 for >5 minutes. "
            "No healthy pods in production namespace. Last successful check: 6m ago."
        ),
        "metric_value": 0.0,
        "threshold_value": 1.0,
        "labels": {"team": "payments", "region": "us-east-1", "env": "production"},
    },
    {
        "source": "Datadog",
        "service": "api-gateway",
        "alert_type": AlertType.LATENCY_SPIKE,
        "title": "p99 latency spike detected on api-gateway",
        "description": (
            "p99 request latency has spiked to 4,200 ms (threshold: 500 ms). "
            "Affecting all downstream services. Started ~12 minutes ago."
        ),
        "metric_value": 4200.0,
        "threshold_value": 500.0,
        "labels": {"team": "platform", "region": "us-west-2", "env": "production"},
    },
    {
        "source": "CloudWatch",
        "service": "order-processor",
        "alert_type": AlertType.RESOURCE_EXHAUSTION,
        "title": "order-processor memory exhaustion — OOMKill imminent",
        "description": (
            "Container memory at 98% of limit (2Gi). GC pauses >5s detected. "
            "Pod restart count: 3 in the last 30 minutes. OOMKill risk: HIGH."
        ),
        "metric_value": 98.0,
        "threshold_value": 85.0,
        "labels": {"team": "orders", "region": "eu-west-1", "env": "production"},
    },
    {
        "source": "PagerDuty",
        "service": "auth-service",
        "alert_type": AlertType.ERROR_RATE,
        "title": "auth-service 5xx error rate exceeds 20%",
        "description": (
            "HTTP 500/503 error rate is 23.4% over the last 5 minutes (threshold: 5%). "
            "Login failures increasing. Possible DB connection pool exhaustion."
        ),
        "metric_value": 23.4,
        "threshold_value": 5.0,
        "labels": {"team": "identity", "region": "us-east-1", "env": "production"},
    },
    {
        "source": "Grafana",
        "service": "recommendation-engine",
        "alert_type": AlertType.LOG_ANOMALY,
        "title": "recommendation-engine — anomalous error log volume",
        "description": (
            "Error log rate increased 10x baseline in past 15 minutes. "
            "Pattern: NullPointerException in ModelInferenceWorker. "
            "Possibly related to v3.1.2 deployment 18 minutes ago."
        ),
        "metric_value": 10.0,
        "threshold_value": 1.0,
        "labels": {"team": "ml-platform", "region": "us-east-1", "env": "production"},
    },
    {
        "source": "Prometheus",
        "service": "inventory-service",
        "alert_type": AlertType.METRIC_THRESHOLD,
        "title": "inventory-service DB connection pool at capacity",
        "description": (
            "PostgreSQL connection pool utilisation at 100% (max: 100 connections). "
            "New requests are queuing. Average wait time: 12s."
        ),
        "metric_value": 100.0,
        "threshold_value": 80.0,
        "labels": {"team": "inventory", "region": "ap-southeast-1", "env": "production"},
    },
    {
        "source": "Datadog",
        "service": "notification-service",
        "alert_type": AlertType.METRIC_THRESHOLD,
        "title": "notification-service queue depth growing — consumers lagging",
        "description": (
            "SQS queue depth: 45,000 messages (threshold: 10,000). "
            "Consumer lag increasing. Messages > 30 minutes old accumulating."
        ),
        "metric_value": 45000.0,
        "threshold_value": 10000.0,
        "labels": {"team": "messaging", "region": "us-east-1", "env": "production"},
    },
    {
        "source": "CloudWatch",
        "service": "reporting-service",
        "alert_type": AlertType.CUSTOM,
        "title": "reporting-service — minor disk usage warning",
        "description": (
            "Disk usage on /data volume at 75% (warning threshold: 70%). "
            "No immediate action required. Trend suggests capacity in 14 days."
        ),
        "metric_value": 75.0,
        "threshold_value": 70.0,
        "labels": {"team": "analytics", "region": "us-east-1", "env": "production"},
    },
]


def generate_alert(scenario_index: int | None = None) -> Alert:
    """
    Create a realistic Alert from a scenario template.

    Args:
        scenario_index: Pin to a specific scenario (0-based). Randomly selected if None.
    """
    idx = scenario_index if scenario_index is not None else random.randint(0, len(_SCENARIOS) - 1)
    scenario = _SCENARIOS[idx % len(_SCENARIOS)]
    return Alert(**scenario)


def generate_alert_batch(count: int = 5) -> list[Alert]:
    """Generate a diverse batch of alerts, cycling through all scenario types."""
    return [generate_alert(i) for i in range(count)]


def get_all_scenarios() -> list[dict]:
    """Return the raw scenario templates (useful for UI dropdowns)."""
    return [
        {
            "index": i,
            "service": s["service"],
            "title": s["title"],
            "alert_type": s["alert_type"].value,
            "source": s["source"],
        }
        for i, s in enumerate(_SCENARIOS)
    ]
