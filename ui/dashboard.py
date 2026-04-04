"""
Enterprise AIOps Platform — Streamlit Dashboard.

Run with:
    streamlit run ui/dashboard.py

The dashboard calls the incident service directly (no API server required)
so it can be demo-ed standalone. A sidebar lets you pick any scenario,
then the full LangGraph pipeline runs and results are rendered live.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# ── Path setup (allows `streamlit run ui/dashboard.py` from repo root) ────────
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.domain.enums import IncidentStatus, Severity
from app.services.incident_service import run_incident_pipeline
from app.services.mock_data import generate_alert, get_all_scenarios

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Enterprise AIOps Platform",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Severity colour mapping ───────────────────────────────────────────────────

_SEVERITY_COLOUR: dict[str, str] = {
    Severity.CRITICAL.value: "#FF4B4B",
    Severity.HIGH.value: "#FF8C00",
    Severity.MEDIUM.value: "#FFC300",
    Severity.LOW.value: "#2ECC71",
    Severity.UNKNOWN.value: "#808080",
}

_STATUS_ICON: dict[str, str] = {
    IncidentStatus.OPEN.value: "🔴",
    IncidentStatus.TRIAGED.value: "🟡",
    IncidentStatus.ANALYZING.value: "🔵",
    IncidentStatus.REMEDIATING.value: "🟠",
    IncidentStatus.RESOLVED.value: "🟢",
    IncidentStatus.ESCALATED.value: "🚨",
    IncidentStatus.CLOSED.value: "⚫",
}


def _severity_badge(severity: str) -> str:
    colour = _SEVERITY_COLOUR.get(severity, "#808080")
    return f'<span style="background:{colour};color:white;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:0.85em">{severity.upper()}</span>'


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple[int, bool]:
    """Render sidebar controls. Returns (scenario_index, should_run)."""
    st.sidebar.image("https://img.shields.io/badge/AIOps-LangGraph-blue?style=for-the-badge", use_container_width=False)
    st.sidebar.title("AIOps Platform")
    st.sidebar.caption("Powered by LangGraph + FastAPI")
    st.sidebar.divider()

    scenarios = get_all_scenarios()
    scenario_labels = [f"{s['index']}. [{s['alert_type'].upper()}] {s['service']}" for s in scenarios]

    st.sidebar.subheader("Alert Scenario")
    selected_idx = st.sidebar.selectbox(
        "Select a pre-built alert",
        options=list(range(len(scenarios))),
        format_func=lambda i: scenario_labels[i],
        index=0,
    )

    selected = scenarios[selected_idx]
    st.sidebar.markdown(f"**Source:** {selected['source']}")
    st.sidebar.markdown(f"**Service:** `{selected['service']}`")

    st.sidebar.divider()
    run_btn = st.sidebar.button("▶ Run Agent Pipeline", type="primary", use_container_width=True)

    st.sidebar.divider()
    st.sidebar.caption("**Architecture**")
    st.sidebar.code(
        "START\n"
        "  └─ ingest\n"
        "       └─ triage\n"
        "            ├─[CRITICAL/HIGH]─ rca\n"
        "            │                   └─ remediation\n"
        "            ├─[MEDIUM]────────── rca → remediation\n"
        "            └─[LOW]──────────── finalize\n"
        "                                   └─ END",
        language=None,
    )

    return selected_idx, run_btn


# ── Main content panels ───────────────────────────────────────────────────────

def render_alert_card(alert) -> None:
    """Render the incoming alert details."""
    with st.container(border=True):
        st.subheader("📡 Incoming Alert")
        c1, c2, c3 = st.columns(3)
        c1.metric("Source", alert.source)
        c2.metric("Service", alert.service)
        c3.metric("Type", alert.alert_type.value.replace("_", " ").title())

        st.markdown(f"**Title:** {alert.title}")
        st.markdown(f"**Description:** {alert.description}")

        if alert.metric_value is not None:
            mc1, mc2 = st.columns(2)
            mc1.metric("Observed Value", alert.metric_value)
            if alert.threshold_value is not None:
                mc2.metric("Threshold", alert.threshold_value, delta=round(alert.metric_value - alert.threshold_value, 2))

        if alert.labels:
            st.markdown("**Labels:** " + " · ".join(f"`{k}={v}`" for k, v in alert.labels.items()))


def render_incident_header(incident) -> None:
    """Render incident ID, severity badge, and status."""
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    col1.markdown(f"### {incident.incident_id}")
    col2.markdown(_severity_badge(incident.severity.value), unsafe_allow_html=True)
    col3.markdown(f"{_STATUS_ICON.get(incident.status.value, '')} **{incident.status.value.upper()}**")
    col4.markdown(f"🌍 `{incident.environment.value}`")


def render_execution_trace(execution_path: list[str], duration_ms: float) -> None:
    """Show which graph nodes ran and in what order."""
    with st.container(border=True):
        st.subheader("🔄 Agent Execution Trace")
        if not execution_path:
            st.info("No execution path recorded.")
            return

        steps = " → ".join(f"**{node}**" for node in execution_path)
        st.markdown(f"Pipeline: {steps}")
        st.caption(f"Total pipeline latency: **{duration_ms:.1f} ms**")


def render_rca_findings(findings: list) -> None:
    """Render RCA findings as expandable cards sorted by confidence."""
    with st.container(border=True):
        st.subheader("🔍 Root Cause Analysis")
        if not findings:
            st.info("No RCA findings generated (LOW severity — skipped).")
            return

        for i, finding in enumerate(findings):
            confidence_pct = int(finding.confidence * 100)
            label = f"#{i+1} · {finding.component} — {confidence_pct}% confidence"
            with st.expander(label, expanded=(i == 0)):
                st.markdown(f"**Finding:** {finding.finding}")
                st.progress(confidence_pct / 100, text=f"Confidence: {confidence_pct}%")
                if finding.evidence:
                    st.markdown("**Evidence:**")
                    for ev in finding.evidence:
                        st.code(ev, language=None)
                if finding.supporting_metrics:
                    st.markdown("**Supporting Metrics:**")
                    for m in finding.supporting_metrics:
                        st.markdown(f"- `{m.metric_name}`: **{m.value} {m.unit}**")


def render_remediation_steps(steps: list) -> None:
    """Render the ordered remediation plan."""
    with st.container(border=True):
        st.subheader("🛠️ Remediation Plan")
        if not steps:
            st.info("No remediation steps generated.")
            return

        for step in steps:
            approval_tag = "⚠️ Requires Approval" if step.requires_approval else "✅ Auto-Execute"
            with st.expander(f"Step {step.priority} · {step.action.value.replace('_', ' ').title()} · {approval_tag}", expanded=True):
                st.markdown(f"**Action:** {step.description}")
                if step.command:
                    st.code(step.command, language="bash")
                c1, c2 = st.columns(2)
                c1.metric("Est. Duration", f"{step.estimated_duration_seconds}s")
                c2.metric("Approval Required", "Yes" if step.requires_approval else "No")


def render_agent_notes(notes: list[str]) -> None:
    """Render the chain-of-thought notes from each agent node."""
    with st.expander("📝 Agent Notes (Chain of Thought)", expanded=False):
        for note in notes:
            st.markdown(f"- {note}")


# ── Main App ──────────────────────────────────────────────────────────────────

def main() -> None:
    st.title("🔬 Enterprise AIOps Platform")
    st.caption("Multi-agent incident management powered by LangGraph · FastAPI · Streamlit")
    st.divider()

    scenario_idx, should_run = render_sidebar()

    # Pre-load alert preview
    alert = generate_alert(scenario_index=scenario_idx)
    render_alert_card(alert)

    st.divider()

    if not should_run:
        st.info("👈 Select a scenario and click **Run Agent Pipeline** to see the full analysis.")

        # Show platform KPIs as placeholder
        st.subheader("Platform Overview")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Scenarios Available", "8")
        k2.metric("Graph Nodes", "5")
        k3.metric("LLM Provider", "Mock (Demo)")
        k4.metric("Auto-Remediation", "Off")
        return

    # ── Run pipeline ──────────────────────────────────────────────────────
    with st.spinner("Running LangGraph agent pipeline…"):
        t_start = time.monotonic()
        result = run_incident_pipeline(alert)
        elapsed_ms = (time.monotonic() - t_start) * 1000

    if not result.success:
        st.error(f"Pipeline failed: {result.error_message}")
        return

    incident = result.incident

    # ── Results ────────────────────────────────────────────────────────────
    st.success(f"Pipeline complete in **{result.total_duration_ms:.0f} ms**")

    render_incident_header(incident)
    st.markdown(f"> {incident.summary}")
    st.divider()

    left, right = st.columns([1, 1])

    with left:
        render_execution_trace(incident.execution_path, result.total_duration_ms)
        render_rca_findings(incident.rca_findings)

    with right:
        render_remediation_steps(incident.remediation_steps)
        render_agent_notes(incident.agent_notes)


if __name__ == "__main__":
    main()
