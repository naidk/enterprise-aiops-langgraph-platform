"""
FastAPI router — Stage 5 endpoints.
"""
from __future__ import annotations

import logging
import random
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import (
    FailureType, Incident, PlatformMetrics, PipelineEvent,
    LogEntry, RCAFinding, RepoFinding, TestResult,
    RootCauseAnalysis, RemediationStep, JiraTicket, Severity, IncidentStatus,
)
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


# ── Crash Injection & Alert Endpoints ─────────────────────────────────────────

@router.post("/inject-crash/{crash_type}")
async def inject_crash(crash_type: str, service: str | None = None):
    """
    Inject a real crash into a service to generate a live alert.

    crash_type options: null_pointer | import_error | db_connection | high_latency | memory_leak
    """
    from services.failure_injector import inject_crash as _inject
    try:
        alert = _inject(crash_type=crash_type, service=service)
        return {
            "message": f"Crash injected into '{alert['service']}'",
            "alert_id": alert["alert_id"],
            "service": alert["service"],
            "crash_type": alert["crash_type"],
            "failure_type": alert["failure_type"],
            "status": alert["status"],
            "timestamp": alert["timestamp"],
            "log_preview": alert["real_logs"][:300] + "...",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts():
    """Get all active (pending/analyzing) alerts waiting for LLM analysis."""
    from services.failure_injector import get_active_alerts, get_all_alerts
    return {
        "active_alerts": get_active_alerts(),
        "all_alerts": get_all_alerts(),
    }


@router.post("/alerts/{alert_id}/analyze")
async def analyze_alert(alert_id: str):
    """
    Run the full LangGraph AI pipeline on a specific alert.
    The LLM analyzes the real crash logs and executes remediation.
    """
    from services.failure_injector import get_all_alerts, resolve_alert
    import uuid

    alerts = get_all_alerts()
    alert = next((a for a in alerts if a["alert_id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    # Build state with real crash logs injected
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    state = build_initial_state(
        incident_id=incident_id,
        service=alert["service"],
        failure_type=alert["failure_type"],
        raw_event={
            "alert_id": alert["alert_id"],
            "crash_type": alert["crash_type"],
            "real_logs": alert["real_logs"],
            "timestamp": alert["timestamp"],
        }
    )

    # Inject the real crash logs into state so LLM sees them
    state["injected_logs"] = alert["real_logs"]

    # Run the full AI pipeline
    config = {"configurable": {"thread_id": incident_id}}
    result = aiops_graph.invoke(state, config=config)

    # Extract LLM findings
    rca_findings = result.get("rca_findings", [])
    llm_analysis = rca_findings[0].get("finding", "No findings") if rca_findings else result.get("event_summary", "Analysis complete")
    remediation = result.get("remediation_plan", [])

    # Mark alert as resolved
    resolve_alert(alert_id, llm_analysis, remediation)

    # Persist incident
    def _parse_list(raw, model):
        out = []
        for item in raw:
            try:
                out.append(model.model_validate(item))
            except Exception:
                pass
        return out

    from app.schemas import (
        Incident, LogEntry, RCAFinding, RepoFinding,
        TestResult, RemediationStep, RootCauseAnalysis, JiraTicket
    )

    severity_val = result.get("severity", "high")
    title = f"[{severity_val.upper()}] {alert['service']} — {alert['crash_type'].replace('_', ' ').title()} (Real Crash)"

    incident_record = Incident(
        incident_id=incident_id,
        title=title,
        description=f"Real crash detected: {alert['crash_type']} in {alert['service']}",
        service=alert["service"],
        failure_type=alert["failure_type"],
        severity=severity_val,
        status=result.get("final_status", "resolved"),
        log_entries=_parse_list(result.get("log_entries", []), LogEntry),
        rca_findings=_parse_list(rca_findings, RCAFinding),
        repo_findings=_parse_list(result.get("repo_findings", []), RepoFinding),
        test_results=_parse_list(result.get("test_results", []), TestResult),
        remediation_steps=_parse_list(remediation, RemediationStep),
        audit_trail=result.get("audit_trail", []),
    )
    incident_svc.create(incident_record)

    return {
        "alert_id": alert_id,
        "incident_id": incident_id,
        "service": alert["service"],
        "crash_type": alert["crash_type"],
        "llm_analysis": llm_analysis,
        "execution_path": result.get("execution_path", []),
        "final_severity": result.get("severity"),
        "final_status": result.get("final_status"),
        "remediation_steps": len(remediation),
        "message": f"AI analysis complete — {alert['service']} incident resolved",
    }


@router.delete("/alerts/clear")
async def clear_alerts():
    """Clear all alerts (demo reset)."""
    from services.failure_injector import clear_all_alerts
    clear_all_alerts()
    return {"message": "All alerts cleared"}


# ── Developer Commit Crash Simulation ─────────────────────────────────────────

@router.post("/simulate-commit-crash")
async def simulate_commit_crash(
    service: str = "payment-service",
    author: str = "dev@company.com",
    commit_message: str = "feat: refactor payment processor for performance",
    crash_type: str = "null_pointer",
):
    """
    Simulates a developer committing bad code that passes CI tests but crashes production.

    Flow:
      1. Developer pushes commit → all tests pass
      2. Deploy to production
      3. Real crash occurs under production load
      4. AIOps agents detect, diagnose (link to commit), rollback, notify developer
    """
    import uuid
    import random
    import time
    from services.failure_injector import inject_crash as _inject, resolve_alert

    _CRASH_FILES = {
        "null_pointer":  f"app/services/{service.replace('-','_')}_processor.py",
        "import_error":  f"app/clients/{service.replace('-','_')}_client.py",
        "db_connection": f"app/repositories/{service.replace('-','_')}_repo.py",
        "high_latency":  f"app/handlers/{service.replace('-','_')}_handler.py",
        "memory_leak":   f"app/workers/{service.replace('-','_')}_worker.py",
    }

    commit_hash = uuid.uuid4().hex[:8]
    changed_file = _CRASH_FILES.get(crash_type, f"app/services/{service}.py")

    # Stage 1: inject real crash with commit metadata
    alert = _inject(crash_type=crash_type, service=service)
    alert_id = alert["alert_id"]

    # Attach commit info to the raw_event
    commit_info = {
        "commit_hash": commit_hash,
        "author": author,
        "message": commit_message,
        "changed_file": changed_file,
        "branch": "main",
        "ci_status": "passed",   # tests passed but prod crashed
    }

    # Stage 2: run full AI pipeline with commit context
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    state = build_initial_state(
        incident_id=incident_id,
        service=service,
        failure_type=alert["failure_type"],
        raw_event={
            "alert_id": alert_id,
            "crash_type": crash_type,
            "real_logs": alert["real_logs"],
            "timestamp": alert["timestamp"],
            "triggered_by_commit": commit_info,
        }
    )
    state["injected_logs"] = alert["real_logs"]

    config = {"configurable": {"thread_id": incident_id}}
    result = aiops_graph.invoke(state, config=config)

    rca_findings = result.get("rca_findings", [])
    llm_analysis = rca_findings[0].get("finding", result.get("event_summary", "Analysis complete")) if rca_findings else result.get("event_summary", "")
    remediation = result.get("remediation_plan", [])

    resolve_alert(alert_id, llm_analysis, remediation)

    # Persist incident
    def _parse_list(raw, model):
        out = []
        for item in raw:
            try:
                out.append(model.model_validate(item))
            except Exception:
                pass
        return out

    from app.schemas import (
        Incident, LogEntry, RCAFinding, RepoFinding,
        TestResult, RemediationStep
    )

    severity_val = result.get("severity", "high")
    incident_record = Incident(
        incident_id=incident_id,
        title=f"[{severity_val.upper()}] {service} — Commit [{commit_hash[:7]}] by {author} caused crash",
        description=f"Commit [{commit_hash[:7]}] '{commit_message}' passed CI but crashed production.",
        service=service,
        failure_type=alert["failure_type"],
        severity=severity_val,
        status=result.get("final_status", "resolved"),
        log_entries=_parse_list(result.get("log_entries", []), LogEntry),
        rca_findings=_parse_list(rca_findings, RCAFinding),
        repo_findings=_parse_list(result.get("repo_findings", []), RepoFinding),
        test_results=_parse_list(result.get("test_results", []), TestResult),
        remediation_steps=_parse_list(remediation, RemediationStep),
        audit_trail=result.get("audit_trail", []),
    )
    incident_svc.create(incident_record)

    return {
        "message": f"Commit [{commit_hash[:7]}] by {author} caused production crash — AI resolved it",
        "incident_id": incident_id,
        "commit": {
            "hash": commit_hash[:7],
            "author": author,
            "message": commit_message,
            "file": changed_file,
            "ci_status": "passed (tests passed but prod crashed)",
        },
        "ai_response": {
            "execution_path": result.get("execution_path", []),
            "agents_ran": len(result.get("execution_path", [])),
            "final_severity": result.get("severity"),
            "final_status": result.get("final_status"),
            "llm_finding": llm_analysis[:200],
            "rollback_executed": any(
                "rollback" in str(s).lower() for s in remediation
            ),
            "developer_notified": True,
        },
        "jira_ticket": result.get("jira_ticket", {}).get("ticket_id") if result.get("jira_ticket") else "Auto-created",
    }


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
    
    # 5. Persist fully-enriched Incident record for tracking and API access.
    # Parse each list[dict] field from state back into typed Pydantic models.
    # model_validate handles datetime coercion and enum casting automatically.
    def _parse_list(raw: list, model) -> list:
        """Safely parse a list of dicts into Pydantic model instances."""
        out = []
        for item in raw:
            try:
                out.append(model.model_validate(item))
            except Exception as exc:
                logger.warning("Failed to parse %s item: %s", model.__name__, exc)
        return out

    log_entries = _parse_list(result.get("log_entries", []), LogEntry)
    rca_findings = _parse_list(result.get("rca_findings", []), RCAFinding)
    repo_findings = _parse_list(result.get("repo_findings", []), RepoFinding)
    test_results = _parse_list(result.get("test_results", []), TestResult)
    remediation_steps = _parse_list(result.get("remediation_plan", []), RemediationStep)

    root_cause: RootCauseAnalysis | None = None
    if result.get("root_cause"):
        try:
            root_cause = RootCauseAnalysis.model_validate(result["root_cause"])
        except Exception as exc:
            logger.warning("Failed to parse root_cause: %s", exc)

    jira_ticket: JiraTicket | None = None
    if result.get("jira_ticket"):
        try:
            jira_ticket = JiraTicket.model_validate(result["jira_ticket"])
        except Exception as exc:
            logger.warning("Failed to parse jira_ticket: %s", exc)

    severity_val = result.get("severity", "unknown")
    status_val = result.get("final_status", "open")
    title = f"[{severity_val.upper()}] {event.service} — {event.failure_type.value.replace('_', ' ').title()}"

    incident_record = Incident(
        incident_id=incident_id,
        title=title,
        description=result.get("event_summary", f"Automated incident triggered by {event.failure_type.value}"),
        service=event.service,
        failure_type=event.failure_type,
        severity=severity_val,
        status=status_val,
        log_entries=log_entries,
        rca_findings=rca_findings,
        repo_findings=repo_findings,
        test_results=test_results,
        root_cause=root_cause,
        remediation_steps=remediation_steps,
        jira_ticket=jira_ticket,
        audit_trail=result.get("audit_trail", []),
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


# ── Stage 4: Deployment & Circuit-Breaker Endpoints ───────────────────────────

@router.post("/deployments/register")
async def register_deployment(
    service: str,
    version: str,
    image: str = "",
    deployed_by: str = "api",
):
    """
    Register a new deployment so the platform can roll back to the previous version.

    Records the deployment in storage/deployments.json keyed by service name.
    The previous deployment is automatically available as the rollback target.
    """
    from services.deployment_tracker import DeploymentTracker, DeploymentRecord
    from datetime import datetime, timezone

    tracker = DeploymentTracker(storage_path=settings.deployments_file)
    record = DeploymentRecord(
        service=service,
        version=version,
        image=image or f"{service}:{version}",
        deployed_by=deployed_by,
        deployed_at=datetime.now(timezone.utc).isoformat(),
        is_stable=True,
        rollback_command=f"kubectl rollout undo deployment/{service} -n production",
    )
    tracker.record_deployment(record)
    previous = tracker.get_previous_version(service)

    return {
        "message": f"Deployment of '{service}' v{version} registered successfully.",
        "service": service,
        "version": version,
        "rollback_target": previous.version if previous else None,
    }


@router.post("/rollback/{service}")
async def manual_rollback(service: str):
    """
    Manually trigger a rollback for a service to its previous deployment.

    Returns the rollback command, dry_run status, and whether execution succeeded.
    In dry_run mode (default) the command is logged but not executed.
    """
    from services.deployment_tracker import DeploymentTracker
    from services.execution_service import ExecutionService

    tracker = DeploymentTracker(storage_path=settings.deployments_file)
    exec_svc = ExecutionService(
        dry_run=settings.dry_run_mode,
        timeout_seconds=settings.execution_timeout_seconds,
    )

    # Ensure we have deployment history
    tracker.seed_service(service)

    rollback_cmd = tracker.get_rollback_command(service)
    previous = tracker.get_previous_version(service)
    current = tracker.get_current_version(service)

    result = exec_svc.execute(rollback_cmd)

    if result.success:
        tracker.mark_unstable(service)

    return {
        "service": service,
        "rollback_command": rollback_cmd,
        "dry_run": result.dry_run,
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "current_version": current.version if current else None,
        "rollback_target_version": previous.version if previous else None,
        "executed_at": result.executed_at,
    }


@router.get("/circuit-breakers")
async def get_circuit_breakers():
    """
    View circuit breaker states for all tracked services.

    Returns the raw circuit breaker data from storage.
    """
    from services.circuit_breaker import CircuitBreaker
    import json
    from pathlib import Path

    cb = CircuitBreaker(
        storage_path=settings.circuit_breaker_file,
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout_minutes=settings.circuit_breaker_recovery_minutes,
    )
    data = cb._load()

    return {
        "circuit_breakers": data,
        "failure_threshold": settings.circuit_breaker_failure_threshold,
        "recovery_timeout_minutes": settings.circuit_breaker_recovery_minutes,
    }


@router.post("/circuit-breakers/{service}/reset")
async def reset_circuit_breaker(service: str):
    """
    Manually reset a circuit breaker for a service.

    Clears the failure count and sets the circuit back to 'closed' state,
    allowing remediation to proceed for that service.
    """
    from services.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(
        storage_path=settings.circuit_breaker_file,
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout_minutes=settings.circuit_breaker_recovery_minutes,
    )
    prev_state = cb.get_state(service)
    cb.record_success(service)
    new_state = cb.get_state(service)

    return {
        "service": service,
        "previous_state": prev_state,
        "new_state": new_state,
        "message": f"Circuit breaker for '{service}' reset from '{prev_state}' to '{new_state}'.",
    }
