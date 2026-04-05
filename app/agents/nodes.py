"""
DEPRECATED — Legacy Stage 1 node functions (app/agents/nodes.py).

The active LangGraph nodes live in: agents/  (root-level package)
  agents/monitoring_agent.py
  agents/log_analysis_agent.py
  agents/repo_inspection_agent.py
  agents/test_analysis_agent.py
  agents/root_cause_agent.py
  agents/remediation_agent.py
  agents/validation_agent.py
  agents/jira_reporting_agent.py

This file is retained for reference only.
────────────────────────────────────────────────────────────────────────────────
LangGraph node functions for the AIOps agent pipeline.

Each function receives the full AIOpsState and returns a *partial* state dict
containing only the fields it modifies. LangGraph merges the return value
into the running state before passing it to the next node.

Design principle:
    Every node is a pure function of state → partial state.
    The `_call_llm()` stub is the single integration point for a real LLM.
    Swap in `langchain_anthropic.ChatAnthropic` or similar with zero other changes.
"""
from __future__ import annotations

from typing import Any

from app.agents.state import AIOpsState
from app.agents.tools import (
    check_downstream_dependencies,
    fetch_service_metrics,
    lookup_recent_deployments,
    search_recent_logs,
)
from app.domain.enums import (
    AlertType,
    IncidentStatus,
    RemediationActionType,
    Severity,
)
from app.domain.models import RCAFinding, RemediationStep


# ── LLM Integration Point ─────────────────────────────────────────────────────

def _call_llm(prompt: str, context: dict[str, Any] | None = None) -> str:
    """
    Abstraction layer for LLM calls.

    In mock mode (default) this returns a deterministic, template-driven
    response that is realistic enough for director-level demos.

    To use Claude:
        from langchain_anthropic import ChatAnthropic
        from app.config.settings import settings
        llm = ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
        return llm.invoke(prompt).content

    The rest of the nodes need no changes.
    """
    # Mock mode — context-aware templated responses
    return _mock_llm_response(prompt, context or {})


def _mock_llm_response(prompt: str, context: dict[str, Any]) -> str:
    """Generate a realistic mock response based on prompt keywords."""
    p = prompt.lower()
    if "triage" in p or "severity" in p:
        return context.get("triage_response", "Incident triaged. Severity determined from signal patterns.")
    if "root cause" in p or "rca" in p:
        return context.get("rca_response", "Root cause identified via metric correlation analysis.")
    if "remediat" in p:
        return context.get("remediation_response", "Remediation plan generated based on runbook templates.")
    return "Analysis complete."


# ── Severity Classification ────────────────────────────────────────────────────

_SEVERITY_RULES: dict[AlertType, Severity] = {
    AlertType.SERVICE_DOWN: Severity.CRITICAL,
    AlertType.RESOURCE_EXHAUSTION: Severity.CRITICAL,
    AlertType.SECURITY: Severity.CRITICAL,
    AlertType.ERROR_RATE: Severity.HIGH,
    AlertType.LATENCY_SPIKE: Severity.HIGH,
    AlertType.LOG_ANOMALY: Severity.MEDIUM,
    AlertType.METRIC_THRESHOLD: Severity.MEDIUM,
    AlertType.CUSTOM: Severity.LOW,
}

_CRITICAL_KEYWORDS = {"down", "outage", "crash", "unavailable", "fatal", "oom", "killed"}
_HIGH_KEYWORDS = {"error rate", "latency", "timeout", "degraded", "spike", "slow"}


def _classify_severity(alert_type: str, title: str, description: str) -> Severity:
    """Rule-based severity classification — mirrors what an LLM would do."""
    text = f"{title} {description}".lower()

    if any(kw in text for kw in _CRITICAL_KEYWORDS):
        return Severity.CRITICAL
    if any(kw in text for kw in _HIGH_KEYWORDS):
        return Severity.HIGH

    return _SEVERITY_RULES.get(AlertType(alert_type), Severity.MEDIUM)


# ── Node: Ingest ───────────────────────────────────────────────────────────────

def ingest_node(state: AIOpsState) -> dict:
    """
    Validate the incoming alert payload, normalise fields, and set up the
    initial incident context. This is the first node in the pipeline.
    """
    alert = state["alert"]
    service = alert.get("service", "unknown")

    note = (
        f"Alert '{alert.get('alert_id', '')}' received from {alert.get('source', 'unknown')} "
        f"for service '{service}'. Type: {alert.get('alert_type')}."
    )
    return {
        "affected_service": service,
        "status": IncidentStatus.OPEN.value,
        "agent_notes": [note],
        "execution_path": ["ingest"],
    }


# ── Node: Triage ───────────────────────────────────────────────────────────────

def triage_node(state: AIOpsState) -> dict:
    """
    Classify severity, build an incident summary, and determine the routing
    path for downstream nodes. Mirrors an L1 on-call engineer's first pass.
    """
    alert = state["alert"]
    service = alert.get("service", "unknown")
    alert_type = alert.get("alert_type", AlertType.CUSTOM.value)
    title = alert.get("title", "")
    description = alert.get("description", "")

    severity = _classify_severity(alert_type, title, description)

    # Routing decision
    if severity in (Severity.CRITICAL, Severity.HIGH):
        route = "deep_rca"
    elif severity == Severity.MEDIUM:
        route = "standard_rca"
    else:
        route = "auto_close"

    llm_summary = _call_llm(
        f"Triage this incident: severity={severity.value}, service={service}, title={title}",
        context={
            "triage_response": (
                f"[TRIAGE] {severity.value.upper()} incident on '{service}'. "
                f"{alert_type.replace('_', ' ').title()} detected: {title}. "
                f"Routing to {'deep root cause analysis' if route == 'deep_rca' else 'standard analysis'}."
            )
        },
    )

    return {
        "severity": severity.value,
        "route": route,
        "summary": llm_summary,
        "status": IncidentStatus.TRIAGED.value,
        "agent_notes": [
            f"Severity classified as {severity.value.upper()}. Route: {route}."
        ],
        "execution_path": ["triage"],
    }


# ── Node: Root Cause Analysis ─────────────────────────────────────────────────

def rca_node(state: AIOpsState) -> dict:
    """
    Correlate metrics, logs, deployments, and dependency health to identify
    probable root causes. Returns ranked RCAFinding objects.
    """
    service = state["affected_service"]
    is_deep = state["route"] == "deep_rca"

    # Gather observability signals
    metrics = fetch_service_metrics(service, window_minutes=30 if is_deep else 15)
    logs = search_recent_logs(service, limit=5 if is_deep else 3)
    deployments = lookup_recent_deployments(service) if is_deep else []
    deps = check_downstream_dependencies(service) if is_deep else {}

    findings: list[RCAFinding] = []

    # ── Signal 1: recent deployment correlation ────────────────────────────
    if deployments:
        deploy = deployments[0]
        mins_ago = deploy["deployed_minutes_ago"]
        if mins_ago < 60:
            findings.append(
                RCAFinding(
                    component=f"{service}:deployment",
                    finding=(
                        f"Recent deployment ({deploy['version']}) {mins_ago} minutes ago "
                        f"correlates with incident start time. Risk level: {deploy['change_risk']}."
                    ),
                    confidence=0.85 if mins_ago < 20 else 0.65,
                    supporting_metrics=[],
                    evidence=[f"Deployment by {deploy['deployed_by']} at T-{mins_ago}m"],
                )
            )

    # ── Signal 2: resource exhaustion ────────────────────────────────────
    cpu_metric = next((m for m in metrics if m.metric_name == "cpu_usage_percent"), None)
    mem_metric = next((m for m in metrics if m.metric_name == "memory_usage_percent"), None)

    if mem_metric and mem_metric.value > 85:
        findings.append(
            RCAFinding(
                component=f"{service}:memory",
                finding=(
                    f"Memory pressure at {mem_metric.value}% — likely triggering GC pauses "
                    f"or OOMKill events that caused the service degradation."
                ),
                confidence=0.78,
                supporting_metrics=[mem_metric],
                evidence=[l for l in logs if "oom" in l.lower() or "memory" in l.lower()],
            )
        )

    if cpu_metric and cpu_metric.value > 80:
        findings.append(
            RCAFinding(
                component=f"{service}:cpu",
                finding=(
                    f"CPU saturation at {cpu_metric.value}% — thread starvation likely "
                    f"causing request queue build-up and timeout cascade."
                ),
                confidence=0.72,
                supporting_metrics=[cpu_metric],
                evidence=[l for l in logs if "timeout" in l.lower() or "pool" in l.lower()],
            )
        )

    # ── Signal 3: unhealthy upstream/downstream ────────────────────────────
    unhealthy_deps = [dep for dep, health in deps.items() if health != "healthy"]
    if unhealthy_deps:
        findings.append(
            RCAFinding(
                component="dependency:external",
                finding=(
                    f"Degraded/unhealthy dependencies detected: {', '.join(unhealthy_deps)}. "
                    f"Cascading failures may be the root cause."
                ),
                confidence=0.70,
                supporting_metrics=[],
                evidence=[f"{dep}: {deps[dep]}" for dep in unhealthy_deps],
            )
        )

    # ── Signal 4: error log pattern ────────────────────────────────────────
    if logs:
        findings.append(
            RCAFinding(
                component=f"{service}:application",
                finding="Repeated error-level log events detected in the analysis window.",
                confidence=0.60,
                supporting_metrics=[],
                evidence=logs[:3],
            )
        )

    # Sort by confidence descending
    findings.sort(key=lambda f: f.confidence, reverse=True)

    note = (
        f"RCA complete ({'deep' if is_deep else 'standard'} analysis). "
        f"{len(findings)} finding(s). Top: {findings[0].component if findings else 'none'}."
    )

    return {
        "rca_findings": [f.model_dump() for f in findings],
        "status": IncidentStatus.ANALYZING.value,
        "agent_notes": [note],
        "execution_path": ["rca"],
    }


# ── Node: Remediation ─────────────────────────────────────────────────────────

def remediation_node(state: AIOpsState) -> dict:
    """
    Generate an ordered, actionable remediation plan based on RCA findings
    and incident severity. Steps are ranked by priority and approval requirement.
    """
    service = state["affected_service"]
    severity = state["severity"]
    rca_findings = state.get("rca_findings", [])
    alert_type = state["alert"].get("alert_type", "")

    steps: list[RemediationStep] = []

    # ── Step 1: Immediate stabilisation ───────────────────────────────────
    if severity in (Severity.CRITICAL.value, Severity.HIGH.value):
        steps.append(
            RemediationStep(
                action=RemediationActionType.NOTIFY_ONCALL,
                description=f"Page on-call engineer — {severity.upper()} incident on {service}.",
                command=f"pagerduty-cli trigger --service {service} --severity {severity}",
                estimated_duration_seconds=30,
                requires_approval=False,
                priority=1,
            )
        )

    # ── Step 2: Deployment rollback if recent deploy was implicated ────────
    deploy_finding = next(
        (f for f in rca_findings if "deployment" in f.get("component", "")), None
    )
    if deploy_finding and deploy_finding.get("confidence", 0) > 0.7:
        steps.append(
            RemediationStep(
                action=RemediationActionType.ROLLBACK_DEPLOYMENT,
                description=f"Roll back {service} to last known-good version.",
                command=f"kubectl rollout undo deployment/{service} -n production",
                estimated_duration_seconds=180,
                requires_approval=True,
                priority=2,
            )
        )

    # ── Step 3: Memory/resource relief ────────────────────────────────────
    mem_finding = next(
        (f for f in rca_findings if "memory" in f.get("component", "")), None
    )
    if mem_finding:
        steps.append(
            RemediationStep(
                action=RemediationActionType.SCALE_UP,
                description=f"Scale {service} replica count to distribute memory load.",
                command=f"kubectl scale deployment/{service} --replicas=6 -n production",
                estimated_duration_seconds=120,
                requires_approval=True,
                priority=3,
            )
        )

    # ── Step 4: Service restart for crash/OOM ─────────────────────────────
    if alert_type in (AlertType.SERVICE_DOWN.value, AlertType.RESOURCE_EXHAUSTION.value):
        steps.append(
            RemediationStep(
                action=RemediationActionType.RESTART_SERVICE,
                description=f"Perform rolling restart of {service} pods.",
                command=f"kubectl rollout restart deployment/{service} -n production",
                estimated_duration_seconds=90,
                requires_approval=True,
                priority=4,
            )
        )

    # ── Step 5: Cache flush for stale state ───────────────────────────────
    if alert_type in (AlertType.LATENCY_SPIKE.value, AlertType.ERROR_RATE.value):
        steps.append(
            RemediationStep(
                action=RemediationActionType.CLEAR_CACHE,
                description=f"Flush Redis cache for {service} — may resolve stale-state errors.",
                command=f"redis-cli -h redis-primary FLUSHDB async  # scope: {service}",
                estimated_duration_seconds=15,
                requires_approval=True,
                priority=5,
            )
        )

    # ── Fallback ──────────────────────────────────────────────────────────
    if not steps:
        steps.append(
            RemediationStep(
                action=RemediationActionType.CREATE_TICKET,
                description="No automated remediation available — create ticket for manual review.",
                command=None,
                estimated_duration_seconds=1,
                requires_approval=False,
                priority=1,
            )
        )

    steps.sort(key=lambda s: s.priority)

    note = f"Remediation plan: {len(steps)} step(s). Requires approval: {sum(s.requires_approval for s in steps)}."

    return {
        "remediation_steps": [s.model_dump() for s in steps],
        "status": IncidentStatus.REMEDIATING.value,
        "agent_notes": [note],
        "execution_path": ["remediation"],
    }


# ── Node: Finalize ────────────────────────────────────────────────────────────

def finalize_node(state: AIOpsState) -> dict:
    """
    Set final incident status and write the resolution summary.
    For LOW severity with no RCA, auto-resolves. Otherwise marks as ESCALATED
    pending human action on the remediation plan.
    """
    route = state["route"]
    findings_count = len(state.get("rca_findings", []))
    steps_count = len(state.get("remediation_steps", []))

    if route == "auto_close":
        status = IncidentStatus.RESOLVED.value
        summary = (
            f"Incident auto-closed. Severity LOW — no RCA required. "
            f"Monitoring continues for recurrence."
        )
    elif steps_count > 0:
        status = IncidentStatus.ESCALATED.value
        summary = (
            f"Incident escalated with {findings_count} RCA finding(s) and "
            f"{steps_count} remediation step(s) awaiting engineer approval."
        )
    else:
        status = IncidentStatus.RESOLVED.value
        summary = "Incident resolved automatically — no remediation required."

    return {
        "status": status,
        "summary": state["summary"] + f" | Resolution: {summary}",
        "agent_notes": [f"Pipeline complete. Final status: {status}."],
        "execution_path": ["finalize"],
    }


# ── Conditional Router ────────────────────────────────────────────────────────

def route_by_severity(state: AIOpsState) -> str:
    """
    LangGraph conditional edge function.
    Returns the name of the next node based on the triage routing decision.
    """
    route = state.get("route", "standard_rca")
    routing_map = {
        "deep_rca": "rca",
        "standard_rca": "rca",
        "direct_remediate": "remediation",
        "auto_close": "finalize",
    }
    return routing_map.get(route, "rca")
