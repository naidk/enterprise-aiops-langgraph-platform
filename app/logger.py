"""
Structured logging configuration for the AIOps platform.

Supports two formats:
  - "json"  → machine-readable JSON lines (production / Docker / log aggregators)
  - "text"  → human-readable coloured output (local development)

Usage:
    from app.logger import configure_logging, get_logger
    configure_logging()
    logger = get_logger(__name__)
    logger.info("Incident created", extra={"incident_id": "INC-123"})
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """
    Emit each log record as a single JSON line.
    Compatible with Datadog, CloudWatch, Loki, and ELK ingestion pipelines.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach structured extras (e.g. incident_id, service)
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
            ):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Coloured text formatter for local development."""

    _COLOURS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        prefix = f"{colour}{ts} | {record.levelname:<8}{self._RESET} | {record.name}"
        return f"{prefix} | {record.getMessage()}"


def configure_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    """
    Configure root logger. Call once at application startup (app/main.py).

    Args:
        log_format: "json" for structured output, "text" for human-readable.
        log_level:  Standard Python log level name ("DEBUG", "INFO", etc.).
    """
    # Lazy import to avoid circular dependency at module load
    try:
        from app.config import settings
        log_format = settings.log_format
        log_level = settings.log_level
    except ImportError:
        pass

    formatter: logging.Formatter = (
        JsonFormatter() if log_format == "json" else TextFormatter()
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    # Quieten noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "langsmith"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — returns a named logger."""
    return logging.getLogger(name)
