"""
FastAPI request/response schemas.

These are deliberately separate from the domain models so the API contract
can evolve independently from internal business logic.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import AlertType, Environment, IncidentStatus, Severity


# ── Request Schemas ───────────────────────────────────────────────────────────

class AlertIngestRequest(BaseModel):
    """Payload accepted by POST /api/v1/incidents."""

    source: str = Field(..., description="Monitoring source (e.g., Prometheus, Datadog)")
    service: str = Field(..., description="Affected service name")
    alert_type: AlertType = Field(..., description="Alert classification")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    labels: dict[str, str] = Field(default_factory=dict)
    environment: Environment = Field(Environment.PRODUCTION)

    model_config = {"json_schema_extra": {
        "example": {
            "source": "Prometheus",
            "service": "payment-service",
            "alert_type": "service_down",
            "title": "payment-service is DOWN — health check failing",
            "description": "Health check /health returning 503 for >5 minutes. No healthy pods.",
            "metric_value": 0.0,
            "threshold_value": 1.0,
            "labels": {"team": "payments", "region": "us-east-1"},
            "environment": "production",
        }
    }}


# ── Response Schemas ──────────────────────────────────────────────────────────

class RCAFindingResponse(BaseModel):
    component: str
    finding: str
    confidence: float
    evidence: list[str]


class RemediationStepResponse(BaseModel):
    action: str
    description: str
    command: Optional[str]
    estimated_duration_seconds: int
    requires_approval: bool
    priority: int


class IncidentResponse(BaseModel):
    incident_id: str
    severity: Severity
    status: IncidentStatus
    environment: Environment
    affected_service: str
    summary: str
    rca_findings: list[RCAFindingResponse]
    remediation_steps: list[RemediationStepResponse]
    agent_notes: list[str]
    execution_path: list[str]
    created_at: datetime
    resolved_at: Optional[datetime]


class AgentRunResponse(BaseModel):
    """Top-level response for POST /api/v1/incidents."""

    incident: IncidentResponse
    total_duration_ms: float
    success: bool
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_provider: str
    graph_nodes: list[str]


class ScenarioListResponse(BaseModel):
    scenarios: list[dict]
    total: int
