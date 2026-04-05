"""
CloudWatch Metrics Client — retrieves service metrics from AWS CloudWatch.

Fetches CPU, memory, request counts, error counts, and latency from the
AWS/ECS and AWS/ApplicationELB namespaces. All boto3 calls are wrapped in
try/except so a missing metric never crashes the pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class CloudWatchMetricsClient:
    """
    Retrieves CloudWatch metrics for AWS-hosted services.

    Args:
        client_factory: BotoClientFactory instance providing boto3 clients.
        namespace: Default CloudWatch namespace. Default: "AWS/ECS".
    """

    def __init__(self, client_factory, namespace: str = "AWS/ECS") -> None:
        self._factory = client_factory
        self._namespace = namespace

    def get_metric(
        self,
        service: str,
        metric_name: str,
        stat: str = "Average",
        period_minutes: int = 5,
        namespace: str | None = None,
    ) -> float | None:
        """
        Fetch a single CloudWatch metric datapoint.

        Args:
            service: Service name (used as the ServiceName dimension value).
            metric_name: CloudWatch metric name (e.g. "CPUUtilization").
            stat: Statistic to retrieve ("Average", "Sum", "Maximum", etc.).
            period_minutes: Window size in minutes.
            namespace: Override the instance-level namespace if provided.

        Returns:
            The latest datapoint value as float, or None if no data available.
        """
        try:
            cw = self._factory.cloudwatch()
            ns = namespace or self._namespace
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(minutes=period_minutes)

            response = cw.get_metric_statistics(
                Namespace=ns,
                MetricName=metric_name,
                Dimensions=[{"Name": "ServiceName", "Value": service}],
                StartTime=start_time,
                EndTime=now,
                Period=period_minutes * 60,
                Statistics=[stat],
            )

            datapoints = response.get("Datapoints", [])
            if not datapoints:
                logger.debug(
                    "CloudWatchMetricsClient.get_metric: no datapoints for %s/%s (%s)",
                    ns, metric_name, service,
                )
                return None

            # Return the value from the most recent datapoint
            latest = max(datapoints, key=lambda d: d["Timestamp"])
            value = latest.get(stat, latest.get("Average", 0.0))
            logger.debug(
                "CloudWatchMetricsClient.get_metric: %s/%s=%s for '%s'",
                ns, metric_name, value, service,
            )
            return float(value)

        except Exception as exc:
            logger.error(
                "CloudWatchMetricsClient.get_metric: failed for %s/%s ('%s') — %s",
                namespace or self._namespace, metric_name, service, exc,
            )
            return None

    def get_service_metrics(self, service: str) -> dict:
        """
        Return a snapshot of key service metrics.

        Fetches the following CloudWatch metrics:
        - CPUUtilization (AWS/ECS)
        - MemoryUtilization (AWS/ECS)
        - RequestCount (AWS/ApplicationELB)
        - HTTPCode_Target_5XX_Count (AWS/ApplicationELB)
        - TargetResponseTime (AWS/ApplicationELB) — converted to milliseconds

        Returns:
            {
                "cpu_percent": float,
                "memory_percent": float,
                "request_count": float,
                "error_count": float,
                "latency_p99_ms": float,
            }
        """
        cpu = self.get_metric(
            service, "CPUUtilization", stat="Average", namespace="AWS/ECS"
        )
        memory = self.get_metric(
            service, "MemoryUtilization", stat="Average", namespace="AWS/ECS"
        )
        request_count = self.get_metric(
            service, "RequestCount", stat="Sum", namespace="AWS/ApplicationELB"
        )
        error_count = self.get_metric(
            service, "HTTPCode_Target_5XX_Count", stat="Sum", namespace="AWS/ApplicationELB"
        )
        latency_seconds = self.get_metric(
            service, "TargetResponseTime", stat="p99", namespace="AWS/ApplicationELB"
        )

        # Convert latency from seconds to milliseconds; default 0.0 for missing data
        latency_ms = (latency_seconds * 1000.0) if latency_seconds is not None else 0.0

        metrics = {
            "cpu_percent": cpu if cpu is not None else 0.0,
            "memory_percent": memory if memory is not None else 0.0,
            "request_count": request_count if request_count is not None else 0.0,
            "error_count": error_count if error_count is not None else 0.0,
            "latency_p99_ms": latency_ms,
        }

        logger.info(
            "CloudWatchMetricsClient.get_service_metrics: %s — cpu=%.1f%% mem=%.1f%% errors=%.0f latency=%.0fms",
            service,
            metrics["cpu_percent"],
            metrics["memory_percent"],
            metrics["error_count"],
            metrics["latency_p99_ms"],
        )
        return metrics
