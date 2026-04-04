"""
Canonical Pydantic schemas for the AIOps platform.

These schemas serve three roles:
  1. FastAPI request/response validation
  2. LangGraph state serialisation (dicts passed through graph nodes)
  3. JSON storage persistence (incidents.json, audit_log.json, metrics.json)

Stage 2 will add full field validation, computed fields, and ORM mappings.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str = "") -> str:
    short = str(uuid.uuid4())[:8].upper()
    return f"{prefix}-{short}" if prefix else short


# ── Enumerations ─────────────────────────────────────────────────────────────

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
    VALIDATING = "validating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class FailureType(str, Enum):
    SERVICE_CRASH = "service_crash"
    HIGH_LATENCY = "high_latency"
    DB_CONNECTION_FAILURE = "db_connection_failure"
    FAILED_JOB = "failed_job"
    BAD_DEPLOYMENT = "bad_deployment"
    UNKNOWN = "unknown"


class RemediationActionType(str, Enum):
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    SCALE_UP = "scale_up"
    CLEAR_CACHE = "clear_cache"
    FAILOVER = "failover"
    RERUN_JOB = "rerun_job"
    NOTIFY_ONCALL = "notify_oncall"
    CREATE_JIRA_TICKET = "create_jira_ticket"
    NO_ACTION = "no_action"


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── Core Domain Schemas ───────────────────────────────────────────────────────

class PipelineEvent(BaseModel):
    """A raw event emitted by the pipeline simulator."""

    event_id: str = Field(default_factory=lambda: _new_id("EVT"))
    service: str = Field(..., description="Service that emitted the event")
    failure_type: FailureType = Field(..., description="Simulated failure category")
    message: str = Field(..., description="Human-readable event message")
    error_code: Optional[str] = Field(None, description="Error code or exception class")
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utcnow)


class LogEntry(BaseModel):
    """A single parsed log line from a service."""

    log_id: str = Field(default_factory=lambda: _new_id("LOG"))
    service: str
    level: str = Field(..., description="DEBUG | INFO | WARN | ERROR | FATAL")
    message: str
    stack_trace: Optional[str] = None
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utcnow)


class RCAFinding(BaseModel):
    """A root cause finding from the log analysis agent."""

    component: str = Field(..., description="Implicated system component")
    finding: str = Field(..., description="Description of the finding")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class RemediationStep(BaseModel):
    """One actionable step in the remediation plan."""

    action: RemediationActionType
    description: str
    command: Optional[str] = Field(None, description="Runbook CLI command if applicable")
    estimated_duration_seconds: int = Field(60, ge=1)
    requires_approval: bool = True
    priority: int = Field(1, ge=1, le=5)


class JiraTicket(BaseModel):
    """Represents a Jira-style incident ticket."""

    ticket_id: str = Field(default_factory=lambda: _new_id("AIOPS"))
    title: str
    description: str
    severity: Severity
    status: str = "Open"
    assignee: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    incident_id: str = ""
    url: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class AgentResult(BaseModel):
    """Output produced by a single agent node in the LangGraph pipeline."""

    agent_name: str
    status: AgentStatus
    output: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


class Incident(BaseModel):
    """
    The canonical incident record.
    Created from a PipelineEvent and progressively enriched by each agent.
    """

    incident_id: str = Field(default_factory=lambda: _new_id("INC"))
    title: str = Field("")
    description: str = Field("")
    severity: Severity = Field(Severity.UNKNOWN)
    status: IncidentStatus = Field(IncidentStatus.OPEN)
    failure_type: FailureType = Field(FailureType.UNKNOWN)
    service: str = Field("")

    # Populated by agents
    log_entries: list[LogEntry] = Field(default_factory=list)
    rca_findings: list[RCAFinding] = Field(default_factory=list)
    remediation_steps: list[RemediationStep] = Field(default_factory=list)
    jira_ticket: Optional[JiraTicket] = None
    agent_results: list[AgentResult] = Field(default_factory=list)
    audit_trail: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = None

    @property
    def is_resolved(self) -> bool:
        return self.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.resolved_at:
            return (self.resolved_at - self.created_at).total_seconds()
        return None


# ── Metrics Schemas ───────────────────────────────────────────────────────────

class ServiceMetrics(BaseModel):
    """Point-in-time metric snapshot for a single service."""

    service: str
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    error_rate_percent: float = 0.0
    latency_p99_ms: float = 0.0
    request_rate_rps: float = 0.0
    health_status: str = "healthy"
    timestamp: datetime = Field(default_factory=_utcnow)


class PlatformMetrics(BaseModel):
    """Aggregated platform-level metrics."""

    total_incidents: int = 0
    open_incidents: int = 0
    resolved_incidents: int = 0
    auto_remediated: int = 0
    mean_time_to_detect_s: float = 0.0
    mean_time_to_resolve_s: float = 0.0
    agent_success_rate: float = 0.0
    last_updated: datetime = Field(default_factory=_utcnow)


# ── Audit Schema ──────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    """An immutable audit log entry for compliance and traceability."""

    audit_id: str = Field(default_factory=lambda: _new_id("AUD"))
    incident_id: Optional[str] = None
    actor: str = Field(..., description="Agent name or user who performed the action")
    action: str = Field(..., description="What was done")
    detail: str = Field("", description="Additional context")
    timestamp: datetime = Field(default_factory=_utcnow)


# ── API Request/Response Schemas ──────────────────────────────────────────────

class TriggerIncidentRequest(BaseModel):
    """POST /api/v1/pipeline/trigger — manually inject a failure scenario."""

    service: str
    failure_type: FailureType
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "service": "payment-service",
                "failure_type": "service_crash",
                "description": "Health check failing for >5 minutes",
            }
        }
    }


class IncidentListResponse(BaseModel):
    incidents: list[Incident]
    total: int
    page: int = 1
    page_size: int = 20


class PlatformStatusResponse(BaseModel):
    status: str
    version: str
    environment: str
    metrics: PlatformMetrics
