"""
Domain enumerations for the AIOps platform.

Using str-based enums so they serialize cleanly to/from JSON
and are directly usable in Pydantic models and FastAPI responses.
"""
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class IncidentStatus(str, Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    ANALYZING = "analyzing"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class AlertType(str, Enum):
    METRIC_THRESHOLD = "metric_threshold"
    LOG_ANOMALY = "log_anomaly"
    SERVICE_DOWN = "service_down"
    LATENCY_SPIKE = "latency_spike"
    ERROR_RATE = "error_rate"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SECURITY = "security"
    CUSTOM = "custom"


class RemediationActionType(str, Enum):
    RESTART_SERVICE = "restart_service"
    SCALE_UP = "scale_up"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CLEAR_CACHE = "clear_cache"
    FAILOVER = "failover"
    NOTIFY_ONCALL = "notify_oncall"
    CREATE_TICKET = "create_ticket"
    AUTO_HEAL = "auto_heal"
    NO_ACTION = "no_action"


class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
