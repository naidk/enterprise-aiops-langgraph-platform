"""
Metrics Service.

Collects, aggregates, and persists platform metrics including:
    - Per-service resource metrics (CPU, memory, latency, error rate)
    - Platform KPIs (MTTD, MTTR, auto-remediation rate, agent success rate)
    - Incident volume and trend data for the dashboard

Stage 2 will:
    - Pull live metrics from Prometheus (via promql) or Datadog API
    - Persist time-series data to metrics.json with TTL-based rotation
    - Expose a /metrics Prometheus endpoint for scraping
    - Compute SLO burn rates and generate alerts when budgets are at risk
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.schemas import PlatformMetrics, ServiceMetrics

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Reads and writes platform metrics to JSON storage.

    Usage:
        svc = MetricsService()
        snapshot = svc.get_service_metrics("payment-service")
        kpis = svc.get_platform_metrics()
    """

    def __init__(
        self,
        storage_path: str = "storage/metrics.json",
        metrics_source=None,   # TODO Stage 2: Prometheus / Datadog client
    ) -> None:
        self._path = Path(storage_path)
        self._source = metrics_source
        self._ensure_file()
        logger.info("MetricsService initialised — storage: %s", self._path)

    def _ensure_file(self) -> None:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        try:
            self._path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except OSError as exc:
            logger.error("MetricsService: save failed — %s", exc)

    # ── Service metrics ────────────────────────────────────────────────────────

    def get_service_metrics(self, service: str) -> ServiceMetrics:
        """
        Return a current metrics snapshot for the named service.

        TODO Stage 2: query Prometheus with promql or call Datadog metrics API.
        """
        # Stub — returns seeded random values for demo reproducibility
        rng = random.Random(service)
        return ServiceMetrics(
            service=service,
            cpu_percent=round(rng.uniform(30, 95), 1),
            memory_percent=round(rng.uniform(40, 90), 1),
            error_rate_percent=round(rng.uniform(0, 30), 2),
            latency_p99_ms=round(rng.uniform(100, 4000), 0),
            request_rate_rps=round(rng.uniform(10, 500), 1),
            health_status="degraded",
            timestamp=datetime.now(timezone.utc),
        )

    def get_all_service_metrics(self, services: list[str]) -> list[ServiceMetrics]:
        return [self.get_service_metrics(s) for s in services]

    # ── Platform KPIs ──────────────────────────────────────────────────────────

    def get_platform_metrics(self) -> PlatformMetrics:
        """
        Compute and return platform-level KPIs.

        TODO Stage 2: derive from incident_service aggregations and real timing data.
        """
        data = self._load()
        return PlatformMetrics(
            total_incidents=data.get("total_incidents", 0),
            open_incidents=data.get("open_incidents", 0),
            resolved_incidents=data.get("resolved_incidents", 0),
            auto_remediated=data.get("auto_remediated", 0),
            mean_time_to_detect_s=data.get("mttd_s", 0.0),
            mean_time_to_resolve_s=data.get("mttr_s", 0.0),
            agent_success_rate=data.get("agent_success_rate", 0.0),
            last_updated=datetime.now(timezone.utc),
        )

    def record_incident_resolved(
        self,
        incident_id: str,
        detection_time_s: float,
        resolution_time_s: float,
        auto_remediated: bool,
    ) -> None:
        """
        Update running KPI aggregates after an incident is resolved.
        TODO Stage 2: implement proper running average computation.
        """
        data = self._load()
        data["total_incidents"] = data.get("total_incidents", 0) + 1
        data["resolved_incidents"] = data.get("resolved_incidents", 0) + 1
        if auto_remediated:
            data["auto_remediated"] = data.get("auto_remediated", 0) + 1
        # Running average (simplified EMA)
        alpha = 0.2
        data["mttd_s"] = alpha * detection_time_s + (1 - alpha) * data.get("mttd_s", detection_time_s)
        data["mttr_s"] = alpha * resolution_time_s + (1 - alpha) * data.get("mttr_s", resolution_time_s)
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        logger.info("MetricsService: recorded resolution for %s (auto=%s)", incident_id, auto_remediated)
