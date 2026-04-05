"""
Health Service — Stage 4.

Performs real HTTP health checks against service endpoints.
Falls back to a degraded stub in dry_run mode for backward compatibility.

Usage:
    from services.health_service import HealthService
    svc = HealthService(base_url_pattern="http://{service}.internal", health_path="/health")
    health = svc.check("payment-service")
    print(health.status)  # "healthy" | "degraded" | "unhealthy" | "unknown"

    # Poll until healthy (blocks, use in async context with thread executor):
    ok, msg = svc.poll_until_healthy("payment-service", max_wait_seconds=120)
"""
from __future__ import annotations

import logging
import time
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
    endpoint_url: str = ""
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
    Checks and reports service health via real HTTP calls.

    Args:
        base_url_pattern: URL template where ``{service}`` is replaced with
            the service name. E.g. ``"http://{service}.svc.cluster.local"``
            or ``"http://localhost:8000"`` (for local testing).
        health_path: Path appended to the base URL. Default: ``"/health"``.
        timeout_seconds: Request timeout. Default: 5s.
    """

    def __init__(
        self,
        base_url_pattern: str = "http://localhost:8000",
        health_path: str = "/health",
        timeout_seconds: int = 5,
    ) -> None:
        self._base_url_pattern = base_url_pattern
        self._health_path = health_path
        self._timeout_seconds = timeout_seconds

    def _build_url(self, service: str) -> str:
        """Build the health check URL for a given service."""
        base = self._base_url_pattern.replace("{service}", service)
        return base.rstrip("/") + self._health_path

    def check_aws(self, service: str, client_factory) -> "ServiceHealth":
        """
        Check service health via AWS ECS and CloudWatch alarms.

        Uses ECS running/desired counts as the primary health signal.
        Downgrades status to "degraded" if any CloudWatch alarm is in ALARM state.

        Args:
            service: Service name to check.
            client_factory: BotoClientFactory instance.

        Returns:
            ServiceHealth populated from ECS and CloudWatch data.
        """
        from services.aws.cloudwatch_health import CloudWatchHealthChecker  # local import
        from app.config import settings  # local import

        ecs_cluster = getattr(settings, "aws_ecs_cluster", "production")
        checker = CloudWatchHealthChecker(client_factory, ecs_cluster=ecs_cluster)

        ecs_result = checker.check_ecs_service_health(service)
        alarm_result = checker.check_service_alarms(service)

        running = ecs_result.get("running_count", 0)
        desired = ecs_result.get("desired_count", 0)
        ecs_healthy = ecs_result.get("healthy", False)
        ecs_error = ecs_result.get("error", "")

        in_alarm_count = alarm_result.get("in_alarm", 0)

        if ecs_error:
            status: HealthStatus = "unknown"
            error_msg = ecs_error
        elif not ecs_healthy:
            status = "unhealthy"
            error_msg = f"ECS: running={running} < desired={desired}"
        elif in_alarm_count > 0:
            status = "degraded"
            error_msg = f"{in_alarm_count} CloudWatch alarm(s) in ALARM state"
        else:
            status = "healthy"
            error_msg = None

        logger.info(
            "HealthService.check_aws: '%s' → status=%s (running=%d desired=%d alarms_in_alarm=%d)",
            service, status, running, desired, in_alarm_count,
        )

        return ServiceHealth(
            service=service,
            status=status,
            pod_count=desired,
            ready_pod_count=running,
            error_message=error_msg,
            endpoint_url=f"ecs://{ecs_cluster}/{service}",
        )

    def check(self, service: str) -> ServiceHealth:
        """
        Perform a real HTTP health check for a named service.

        When CLOUD_PROVIDER=aws is set, delegates to check_aws() instead of HTTP.

        Returns:
            ServiceHealth with status based on HTTP response or connection error.
        """
        # AWS mode: use ECS + CloudWatch instead of HTTP
        try:
            from app.config import settings as _settings  # local import
            if _settings.using_aws:
                from services.aws.boto_client import BotoClientFactory  # local import
                factory = BotoClientFactory(
                    region=_settings.aws_region,
                    aws_access_key_id=_settings.aws_access_key_id,
                    aws_secret_access_key=_settings.aws_secret_access_key,
                    aws_session_token=_settings.aws_session_token,
                    role_arn=_settings.aws_role_arn,
                )
                return self.check_aws(service, factory)
        except Exception as exc:
            logger.warning(
                "HealthService.check: AWS mode check failed for '%s' — %s; falling back to HTTP",
                service, exc,
            )

        import requests  # local import — avoid hard failure if requests not installed

        url = self._build_url(service)
        logger.info("HealthService.check: GET %s (timeout=%ds)", url, self._timeout_seconds)
        start = time.monotonic()

        try:
            response = requests.get(url, timeout=self._timeout_seconds)
            response_time_ms = round((time.monotonic() - start) * 1000, 2)

            if response.status_code == 200:
                logger.info(
                    "HealthService: '%s' is HEALTHY (HTTP 200, %.0fms)",
                    service, response_time_ms,
                )
                return ServiceHealth(
                    service=service,
                    status="healthy",
                    http_status_code=200,
                    response_time_ms=response_time_ms,
                    endpoint_url=url,
                )
            else:
                logger.warning(
                    "HealthService: '%s' is DEGRADED (HTTP %d, %.0fms)",
                    service, response.status_code, response_time_ms,
                )
                return ServiceHealth(
                    service=service,
                    status="degraded",
                    http_status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    endpoint_url=url,
                    error_message=f"HTTP {response.status_code}",
                )

        except requests.exceptions.ConnectionError:
            response_time_ms = round((time.monotonic() - start) * 1000, 2)
            logger.warning("HealthService: '%s' is UNHEALTHY — connection refused at %s", service, url)
            return ServiceHealth(
                service=service,
                status="unhealthy",
                http_status_code=None,
                response_time_ms=response_time_ms,
                endpoint_url=url,
                error_message="Connection refused",
            )

        except requests.exceptions.Timeout:
            response_time_ms = round((time.monotonic() - start) * 1000, 2)
            msg = f"Timeout after {self._timeout_seconds}s"
            logger.warning("HealthService: '%s' is UNHEALTHY — %s at %s", service, msg, url)
            return ServiceHealth(
                service=service,
                status="unhealthy",
                http_status_code=None,
                response_time_ms=response_time_ms,
                endpoint_url=url,
                error_message=msg,
            )

        except Exception as exc:
            response_time_ms = round((time.monotonic() - start) * 1000, 2)
            logger.error("HealthService: '%s' check raised unexpected error — %s", service, exc)
            return ServiceHealth(
                service=service,
                status="unknown",
                http_status_code=None,
                response_time_ms=response_time_ms,
                endpoint_url=url,
                error_message=str(exc),
            )

    def poll_until_healthy(
        self,
        service: str,
        max_wait_seconds: int = 120,
        interval_seconds: int = 10,
    ) -> tuple[bool, str]:
        """
        Poll the health endpoint until the service is healthy or timeout is reached.

        Args:
            service: Service name to poll.
            max_wait_seconds: Maximum seconds to wait before giving up.
            interval_seconds: Seconds between each check attempt.

        Returns:
            (True, "healthy after Xs") on success.
            (False, "still unhealthy after Xs") on timeout.
        """
        deadline = time.monotonic() + max_wait_seconds
        attempt = 0

        logger.info(
            "HealthService: polling '%s' for up to %ds (interval=%ds)",
            service, max_wait_seconds, interval_seconds,
        )

        while time.monotonic() < deadline:
            attempt += 1
            elapsed = round(time.monotonic() - (deadline - max_wait_seconds))
            health = self.check(service)

            logger.info(
                "HealthService: poll attempt %d — '%s' status=%s (elapsed ~%ds/%ds)",
                attempt, service, health.status, elapsed, max_wait_seconds,
            )

            if health.is_healthy:
                elapsed_total = round((time.monotonic() - (deadline - max_wait_seconds)))
                msg = f"healthy after {elapsed_total}s"
                logger.info("HealthService: '%s' recovered — %s", service, msg)
                return True, msg

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            wait = min(interval_seconds, remaining)
            time.sleep(wait)

        elapsed_total = max_wait_seconds
        msg = f"still unhealthy after {elapsed_total}s"
        logger.warning("HealthService: '%s' did NOT recover — %s", service, msg)
        return False, msg

    def check_all(self, services: list[str]) -> dict[str, ServiceHealth]:
        """Check health for a list of services. Returns dict keyed by service name."""
        return {svc: self.check(svc) for svc in services}

    def is_recovering(self, service: str, prev_health: ServiceHealth) -> bool:
        """
        Compare current health against a previous snapshot to detect recovery trend.
        """
        current = self.check(service)
        return current.ready_pod_count > prev_health.ready_pod_count
