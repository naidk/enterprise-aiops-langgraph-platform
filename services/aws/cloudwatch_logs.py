"""
CloudWatch Logs Client — retrieves log events from AWS CloudWatch Logs.

Provides recent log tailing, error-filtered log retrieval, and message-only
output. All boto3 calls are wrapped in try/except so missing log groups or
API errors never crash the AIOps pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class CloudWatchLogsClient:
    """
    Retrieves log events from AWS CloudWatch Logs.

    Args:
        client_factory: BotoClientFactory instance providing boto3 clients.
        log_group_prefix: Prefix for log group names. Default: "/aws/ecs".
    """

    def __init__(self, client_factory, log_group_prefix: str = "/aws/ecs") -> None:
        self._factory = client_factory
        self._log_group_prefix = log_group_prefix

    def _log_group_name(self, service: str) -> str:
        return f"{self._log_group_prefix}/{service}"

    def get_recent_logs(
        self,
        service: str,
        minutes: int = 10,
        max_events: int = 50,
    ) -> list[dict]:
        """
        Return the most recent log events for a service.

        Args:
            service: Service name (appended to log_group_prefix).
            minutes: How many minutes back to look.
            max_events: Maximum number of events to return.

        Returns:
            List of dicts: [{"timestamp": ISO_str, "message": str, "log_stream": str}]
            Returns [] if the log group does not exist or on any error.
        """
        log_group = self._log_group_name(service)
        try:
            logs_client = self._factory.logs()
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(minutes=minutes)
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(now.timestamp() * 1000)

            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_ms,
                endTime=end_ms,
                limit=max_events,
            )

            events = response.get("events", [])
            result = []
            for event in events:
                ts_ms = event.get("timestamp", 0)
                ts_iso = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()
                result.append({
                    "timestamp": ts_iso,
                    "message": event.get("message", ""),
                    "log_stream": event.get("logStreamName", ""),
                })

            logger.info(
                "CloudWatchLogsClient.get_recent_logs: %s — retrieved %d events from %s",
                service, len(result), log_group,
            )
            return result

        except Exception as exc:
            # Handle ResourceNotFoundException (log group not found) gracefully
            exc_name = type(exc).__name__
            if "ResourceNotFoundException" in exc_name or (
                hasattr(exc, "response") and
                exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException"
            ):
                logger.warning(
                    "CloudWatchLogsClient.get_recent_logs: log group '%s' not found — returning []",
                    log_group,
                )
            else:
                logger.warning(
                    "CloudWatchLogsClient.get_recent_logs: failed for '%s' — %s",
                    service, exc,
                )
            return []

    def get_error_logs(self, service: str, minutes: int = 10) -> list[dict]:
        """
        Return log events matching the ERROR filter pattern.

        Args:
            service: Service name.
            minutes: How many minutes back to look.

        Returns:
            List of dicts: [{"timestamp": ISO_str, "message": str, "log_stream": str}]
        """
        log_group = self._log_group_name(service)
        try:
            logs_client = self._factory.logs()
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(minutes=minutes)
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(now.timestamp() * 1000)

            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_ms,
                endTime=end_ms,
                filterPattern="ERROR",
                limit=50,
            )

            events = response.get("events", [])
            result = []
            for event in events:
                ts_ms = event.get("timestamp", 0)
                ts_iso = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()
                result.append({
                    "timestamp": ts_iso,
                    "message": event.get("message", ""),
                    "log_stream": event.get("logStreamName", ""),
                })

            logger.info(
                "CloudWatchLogsClient.get_error_logs: %s — retrieved %d ERROR events from %s",
                service, len(result), log_group,
            )
            return result

        except Exception as exc:
            logger.warning(
                "CloudWatchLogsClient.get_error_logs: failed for '%s' — %s",
                service, exc,
            )
            return []

    def tail_logs(self, service: str, minutes: int = 5) -> list[str]:
        """
        Return just the message strings from recent log events.

        Args:
            service: Service name.
            minutes: How many minutes back to look.

        Returns:
            List of message strings, ordered by timestamp (oldest first).
        """
        events = self.get_recent_logs(service, minutes=minutes)
        return [e["message"] for e in events]
