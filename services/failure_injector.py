"""
Failure Injector Service — generates real Python crashes with actual tracebacks.

These are real exceptions caught and stored so the LLM can analyze genuine error logs.
"""
from __future__ import annotations

import traceback
import time
import json
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

_ALERTS_FILE = Path("storage/active_alerts.json")
_lock = threading.Lock()


def _load_alerts() -> list[dict]:
    if _ALERTS_FILE.exists():
        try:
            return json.loads(_ALERTS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_alerts(alerts: list[dict]) -> None:
    _ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ALERTS_FILE.write_text(json.dumps(alerts, indent=2))


# ── Real crash generators ─────────────────────────────────────────────────────

def _crash_null_pointer(service: str) -> tuple[str, str]:
    """Simulate NullPointerException — real Python AttributeError."""
    try:
        obj = None
        _ = obj.some_attribute.nested_value  # real crash
    except Exception:
        tb = traceback.format_exc()
    log = (
        f"[FATAL] {service}: NullPointerException in WorkerThread\n"
        f"[ERROR] {service}: AttributeError — 'NoneType' object has no attribute 'some_attribute'\n"
        f"{tb}\n"
        f"[ERROR] {service}: OOMKill — memory limit 2Gi exceeded, container killed by kernel"
    )
    return "service_crash", log


def _crash_import_error(service: str) -> tuple[str, str]:
    """Simulate broken import — real Python ImportError."""
    try:
        import importlib
        importlib.import_module("non_existent_legacy_client_module_xyz")
    except Exception:
        tb = traceback.format_exc()
    log = (
        f"[FATAL] {service}: ImportError: cannot import name 'LegacyClient' from 'app.clients'\n"
        f"[ERROR] {service}: ModuleNotFoundError — app startup failed\n"
        f"{tb}\n"
        f"[ERROR] {service}: Service failed to initialize — all health checks returning 503"
    )
    return "repo_bug", log


def _crash_db_connection(service: str) -> tuple[str, str]:
    """Simulate database connection failure — real ConnectionRefusedError."""
    try:
        import socket
        s = socket.create_connection(("127.0.0.1", 5433), timeout=0.001)
    except Exception:
        tb = traceback.format_exc()
    log = (
        f"[ERROR] {service}: connection refused — ECONNREFUSED 127.0.0.1:5432\n"
        f"[ERROR] {service}: Database connection pool exhausted (max=20, active=20, idle=0)\n"
        f"{tb}\n"
        f"[WARN]  {service}: Retrying DB connection (attempt 3/3)... FAILED\n"
        f"[ERROR] {service}: All DB connections failed — service degraded"
    )
    return "db_connection_failure", log


def _crash_high_latency(service: str) -> tuple[str, str]:
    """Simulate high latency — real timeout."""
    try:
        import socket
        s = socket.create_connection(("10.255.255.1", 80), timeout=0.001)
    except Exception:
        tb = traceback.format_exc()
    log = (
        f"[ERROR] {service}: Request timeout after 30000ms — downstream service unreachable\n"
        f"[WARN]  {service}: p99 latency = 4200ms (SLA threshold: 500ms)\n"
        f"{tb}\n"
        f"[WARN]  {service}: Circuit breaker OPEN — 15 consecutive timeouts\n"
        f"[ERROR] {service}: Dropping requests — queue depth 2847 (max: 100)"
    )
    return "high_latency", log


def _crash_memory_leak(service: str) -> tuple[str, str]:
    """Simulate memory leak / OOM."""
    try:
        raise MemoryError("Cannot allocate memory — container exceeded 2Gi limit")
    except Exception:
        tb = traceback.format_exc()
    log = (
        f"[FATAL] {service}: OOMKill — container killed by kernel (limit: 2Gi, usage: 2.1Gi)\n"
        f"[ERROR] {service}: MemoryError — heap exhausted, GC unable to free memory\n"
        f"{tb}\n"
        f"[ERROR] {service}: Pod restarting (restart count: 5) — CrashLoopBackOff"
    )
    return "service_crash", log


_CRASH_MAP = {
    "null_pointer":    _crash_null_pointer,
    "import_error":    _crash_import_error,
    "db_connection":   _crash_db_connection,
    "high_latency":    _crash_high_latency,
    "memory_leak":     _crash_memory_leak,
}

_SERVICES = [
    "payment-service", "auth-service", "order-service",
    "inventory-service", "user-service", "notification-service"
]


def inject_crash(crash_type: str, service: str | None = None) -> dict[str, Any]:
    """
    Inject a real crash into a service and store the alert.
    Returns the alert dict.
    """
    import random
    svc = service or random.choice(_SERVICES)

    if crash_type not in _CRASH_MAP:
        crash_type = "null_pointer"

    failure_type, real_logs = _CRASH_MAP[crash_type](svc)

    alert = {
        "alert_id": f"ALERT-{int(time.time() * 1000) % 99999:05d}",
        "service": svc,
        "crash_type": crash_type,
        "failure_type": failure_type,
        "real_logs": real_logs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",        # pending → analyzing → resolved
        "llm_analysis": None,
        "remediation": None,
    }

    with _lock:
        alerts = _load_alerts()
        alerts.append(alert)
        _save_alerts(alerts)

    return alert


def get_active_alerts() -> list[dict]:
    """Return all pending/analyzing alerts."""
    with _lock:
        alerts = _load_alerts()
    return [a for a in alerts if a.get("status") in ("pending", "analyzing")]


def get_all_alerts() -> list[dict]:
    with _lock:
        return _load_alerts()


def resolve_alert(alert_id: str, llm_analysis: str, remediation: list) -> None:
    """Mark alert as resolved after LLM analysis."""
    with _lock:
        alerts = _load_alerts()
        for a in alerts:
            if a["alert_id"] == alert_id:
                a["status"] = "resolved"
                a["llm_analysis"] = llm_analysis
                a["remediation"] = remediation
                break
        _save_alerts(alerts)


def clear_all_alerts() -> None:
    """Clear all alerts (for demo reset)."""
    with _lock:
        _save_alerts([])
