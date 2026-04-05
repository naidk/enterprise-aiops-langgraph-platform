"""
API Monitor Service — tracks health of internal and external APIs.

Monitors:
    - Response time (latency)
    - Status codes (4xx, 5xx)
    - Error rate
    - Authentication failures
    - Rate limit hits
    - Third-party API availability
"""
from __future__ import annotations

import json
import time
import threading
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_API_HEALTH_FILE = Path("storage/api_health.json")
_lock = threading.Lock()


# ── Simulated API registry (replace with real endpoints in production) ─────────
_MONITORED_APIS = {
    "payment-api":       {"url": "https://api.payment-service.internal/health",    "type": "internal"},
    "auth-api":          {"url": "https://api.auth-service.internal/health",       "type": "internal"},
    "order-api":         {"url": "https://api.order-service.internal/health",      "type": "internal"},
    "stripe-api":        {"url": "https://api.stripe.com/healthcheck",             "type": "external"},
    "sendgrid-api":      {"url": "https://api.sendgrid.com/v3/health",             "type": "external"},
    "notification-api":  {"url": "https://api.notification-service.internal/ping", "type": "internal"},
}

# ── API issue types ────────────────────────────────────────────────────────────
_API_ISSUES = {
    "5xx_error": {
        "status_code": 500,
        "error": "Internal Server Error",
        "log": "ERROR: API returned 500 Internal Server Error — unhandled exception in request handler",
        "failure_type": "service_crash",
    },
    "timeout": {
        "status_code": 504,
        "error": "Gateway Timeout",
        "log": "ERROR: API request timeout after 30000ms — downstream service not responding",
        "failure_type": "high_latency",
    },
    "auth_failure": {
        "status_code": 401,
        "error": "Unauthorized",
        "log": "ERROR: API authentication failed — JWT token expired or invalid API key",
        "failure_type": "repo_bug",
    },
    "rate_limit": {
        "status_code": 429,
        "error": "Too Many Requests",
        "log": "WARN: API rate limit exceeded — 429 Too Many Requests. Retry-After: 60s",
        "failure_type": "high_latency",
    },
    "schema_break": {
        "status_code": 422,
        "error": "Unprocessable Entity",
        "log": "ERROR: API schema validation failed — required field 'payment_method_id' missing in response",
        "failure_type": "repo_bug",
    },
    "third_party_down": {
        "status_code": 503,
        "error": "Service Unavailable",
        "log": "ERROR: Third-party API unavailable — connection refused after 3 retries",
        "failure_type": "db_connection_failure",
    },
    "high_latency": {
        "status_code": 200,
        "error": "Degraded Performance",
        "log": "WARN: API p99 latency = 4800ms (SLA: 500ms) — circuit breaker threshold approaching",
        "failure_type": "high_latency",
    },
}


def _load_health() -> dict:
    if _API_HEALTH_FILE.exists():
        try:
            return json.loads(_API_HEALTH_FILE.read_text())
        except Exception:
            pass
    return {"apis": {}, "incidents": []}


def _save_health(data: dict) -> None:
    _API_HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    _API_HEALTH_FILE.write_text(json.dumps(data, indent=2))


def get_api_health() -> dict:
    """Return current API health status for all monitored APIs."""
    with _lock:
        data = _load_health()

    # If no data yet, return mock healthy state
    if not data.get("apis"):
        return {
            "apis": {
                name: {
                    "status": "healthy",
                    "status_code": 200,
                    "latency_ms": random.randint(20, 120),
                    "error_rate": 0.0,
                    "type": info["type"],
                    "last_checked": datetime.now(timezone.utc).isoformat(),
                }
                for name, info in _MONITORED_APIS.items()
            },
            "summary": {
                "total": len(_MONITORED_APIS),
                "healthy": len(_MONITORED_APIS),
                "degraded": 0,
                "down": 0,
            },
            "incidents": [],
        }
    return data


def inject_api_issue(api_name: str, issue_type: str) -> dict[str, Any]:
    """
    Inject a real API issue for demo/testing.
    Returns the incident data for the AI pipeline.
    """
    if api_name not in _MONITORED_APIS:
        api_name = random.choice(list(_MONITORED_APIS.keys()))

    if issue_type not in _API_ISSUES:
        issue_type = "5xx_error"

    issue = _API_ISSUES[issue_type]
    api_info = _MONITORED_APIS[api_name]

    incident = {
        "incident_id": f"API-{int(time.time() * 1000) % 99999:05d}",
        "api_name": api_name,
        "api_url": api_info["url"],
        "api_type": api_info["type"],
        "issue_type": issue_type,
        "status_code": issue["status_code"],
        "error": issue["error"],
        "log": issue["log"],
        "failure_type": issue["failure_type"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "latency_ms": random.randint(3000, 8000) if "latency" in issue_type else random.randint(100, 500),
        "error_rate": random.uniform(0.3, 0.9),
    }

    with _lock:
        data = _load_health()
        # Mark API as degraded
        data["apis"][api_name] = {
            "status": "down" if issue["status_code"] >= 500 else "degraded",
            "status_code": issue["status_code"],
            "latency_ms": incident["latency_ms"],
            "error_rate": incident["error_rate"],
            "type": api_info["type"],
            "last_checked": incident["timestamp"],
            "last_error": issue["error"],
        }
        data.setdefault("incidents", []).append(incident)
        _save_health(data)

    return incident


def resolve_api_incident(incident_id: str, resolution: str) -> None:
    """Mark API incident as resolved after AI fix."""
    with _lock:
        data = _load_health()
        for inc in data.get("incidents", []):
            if inc["incident_id"] == incident_id:
                inc["status"] = "resolved"
                inc["resolution"] = resolution
                # Restore API health
                api_name = inc["api_name"]
                if api_name in data["apis"]:
                    data["apis"][api_name]["status"] = "healthy"
                    data["apis"][api_name]["status_code"] = 200
                    data["apis"][api_name]["error_rate"] = 0.0
                break
        _save_health(data)


def clear_api_health() -> None:
    with _lock:
        _save_health({"apis": {}, "incidents": []})


def get_summary(health_data: dict) -> dict:
    """Calculate summary stats from health data."""
    apis = health_data.get("apis", {})
    healthy  = sum(1 for a in apis.values() if a.get("status") == "healthy")
    degraded = sum(1 for a in apis.values() if a.get("status") == "degraded")
    down     = sum(1 for a in apis.values() if a.get("status") == "down")
    total    = len(_MONITORED_APIS)
    return {
        "total": total,
        "healthy": healthy,
        "degraded": degraded,
        "down": down,
    }
