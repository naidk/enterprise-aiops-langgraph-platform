"""
FastAPI router — Stage 5 endpoints.
"""
from __future__ import annotations

import logging
import random
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import FailureType, Incident, PlatformMetrics, PipelineEvent
from graph.workflow import aiops_graph
from app.state import build_initial_state
from services.incident_service import IncidentService
from services.metrics_service import MetricsService
from services.pipeline_simulator import PipelineSimulator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["AIOps Stage 5"])

# Initialise Services
incident_svc = IncidentService(storage_path=settings.incidents_file)
metrics_svc = MetricsService(storage_path=settings.metrics_file)
simulator = PipelineSimulator()


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "app_version": settings.app_version,
        "llm_provider": settings.llm_provider,
        "environment": settings.environment
    }


@router.get("/pipeline/state")
async def pipeline_state():
    """Computes the overall pipeline system state including active incidents."""
    incidents = incident_svc.list_all()
    open_incidents = [i for i in incidents if not i.is_resolved]
    
    return {
        "pipeline_name": settings.app_name,
        "current_status": "Degraded" if open_incidents else "Healthy",
        "active_incidents": len(open_incidents),
        "total_incidents": len(incidents),
    }


@router.post("/simulate/{failure_type}", response_model=PipelineEvent)
async def simulate_event(failure_type: FailureType):
    """Maps to PipelineSimulator and returns the raw PipelineEvent."""
    try:
        event = simulator.emit_event(failure_type=failure_type)
        return event
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run-monitoring-cycle")
async def run_monitoring_cycle():
    """
    Simulates a cron tick. Pulls a random event and triggers the LangGraph flow natively.
    Returns the final Execution State Dictionary.
    """
    # 1. Grab a random failure type (excluding Unknown)
    available_failures = [f for f in FailureType if f != FailureType.UNKNOWN]
    chosen_failure = random.choice(available_failures)
    
    # 2. Simulate the Pipeline Event natively from the architecture
    event = simulator.emit_event(failure_type=chosen_failure)
    
    # 3. Create the LangGraph dictionary state
    incident_id = event.event_id.replace("EVT", "INC")
    state = build_initial_state(
        incident_id=incident_id,
        service=event.service,
        failure_type=event.failure_type.value,
        raw_event=event.model_dump(mode="json")
    )
    
    # 4. Invoke the Graph locally
    config = {"configurable": {"thread_id": incident_id}}
    result = aiops_graph.invoke(state, config=config)
    
    # 5. Persist Incident Result explicitly for tracking (simulating real hook)
    incident_record = Incident(
        incident_id=incident_id,
        service=event.service,
        failure_type=event.failure_type,
        severity=result.get("severity", "unknown"),
        status=result.get("final_status", "open"),
        audit_trail=result.get("audit_trail", [])
    )
    # Save the incident internally into JSON array
    incident_svc.create(incident_record)
    
    return {
        "message": f"Cycle complete for {event.service}",
        "execution_path": result.get("execution_path", []),
        "final_severity": result.get("severity"),
        "final_status": result.get("final_status")
    }


@router.get("/incidents", response_model=list[Incident])
async def list_incidents():
    """Returns all incidents from local persistence storage."""
    return incident_svc.list_all()


@router.get("/logs")
async def get_logs():
    """Reads deep into the incidents and simulates tailing backend logs."""
    all_incidents = incident_svc.list_all()
    logs = []
    
    for inc in reversed(all_incidents):
        logs.extend([f"[{inc.incident_id}] {entry}" for entry in inc.audit_trail])
        
    return {"logs": logs}


@router.get("/metrics", response_model=PlatformMetrics)
async def get_metrics():
    """Extracts platform data directly from the Metrics service."""
    # Fast calculate metrics from active JSON Incident Array if needed, 
    # but the service inherently tracks it. Let's just return what's there.
    metrics = metrics_svc.get_platform_metrics()
    
    # Enforce syncing incidents logic here dynamically since we lack real webhooks
    incidents = incident_svc.list_all()
    metrics.total_incidents = len(incidents)
    metrics.open_incidents = len([i for i in incidents if not i.is_resolved])
    metrics.resolved_incidents = len([i for i in incidents if i.is_resolved])
    
    return metrics
