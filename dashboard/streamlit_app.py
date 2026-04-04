"""
Enterprise AIOps Platform — Streamlit Dashboard.

Multi-page dashboard covering:
    Page 1 — Live Incident Feed        (active incidents, severity heatmap)
    Page 2 — Pipeline Simulator        (trigger failure scenarios manually)
    Page 3 — Metrics & KPIs            (MTTD, MTTR, agent success rate)
    Page 4 — Audit Log                 (full agent chain-of-thought)
    Page 5 — Jira Board                (Jira-style ticket view)

Run:
    streamlit run dashboard/streamlit_app.py

Stage 2 will:
    - Replace stub data with live IncidentService / MetricsService calls
    - Add real-time auto-refresh via st.rerun() + a background polling thread
    - Add WebSocket streaming for live agent execution trace
    - Add authentication (streamlit-authenticator)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running from project root
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enterprise AIOps Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar navigation ─────────────────────────────────────────────────────────
st.sidebar.title("🛡️ AIOps Platform")
st.sidebar.caption("Multi-agent self-healing infrastructure")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    options=[
        "🔴 Live Incidents",
        "⚡ Pipeline Simulator",
        "📊 Metrics & KPIs",
        "📋 Audit Log",
        "🎫 Jira Board",
    ],
    index=0,
)

st.sidebar.divider()
st.sidebar.markdown("**Agent Pipeline**")
st.sidebar.code(
    "monitoring_agent\n"
    "  └─ log_analysis_agent\n"
    "       └─ incident_classifier\n"
    "            ├─ [CRITICAL] → jira\n"
    "            └─ [other] → remediation\n"
    "                  └─ validation\n"
    "                        └─ jira",
    language=None,
)


# ── Colour maps ────────────────────────────────────────────────────────────────
_SEVERITY_COLOUR = {
    "critical": "#FF4B4B",
    "high":     "#FF8C00",
    "medium":   "#FFC300",
    "low":      "#2ECC71",
    "unknown":  "#808080",
}

_STATUS_ICON = {
    "open":        "🔴",
    "triaged":     "🟡",
    "analyzing":   "🔵",
    "remediating": "🟠",
    "validating":  "🟣",
    "resolved":    "🟢",
    "escalated":   "🚨",
    "closed":      "⚫",
}


def _badge(text: str, colour: str) -> str:
    return (
        f'<span style="background:{colour};color:white;padding:3px 10px;'
        f'border-radius:12px;font-weight:bold;font-size:0.8em">{text.upper()}</span>'
    )


# ── Stub data (Stage 2: replace with IncidentService / MetricsService calls) ──

_STUB_INCIDENTS = [
    {
        "incident_id": "INC-A1B2C3D4",
        "service": "payment-service",
        "failure_type": "service_crash",
        "severity": "critical",
        "status": "escalated",
        "summary": "OOMKilled — memory exhaustion on payment-service pods",
        "created_at": "2026-04-04T10:12:00Z",
    },
    {
        "incident_id": "INC-E5F6G7H8",
        "service": "api-gateway",
        "failure_type": "high_latency",
        "severity": "high",
        "status": "remediating",
        "summary": "p99 latency 4,200ms — SLO breach. Cache flush in progress.",
        "created_at": "2026-04-04T10:35:00Z",
    },
    {
        "incident_id": "INC-I9J0K1L2",
        "service": "inventory-service",
        "failure_type": "db_connection_failure",
        "severity": "high",
        "status": "resolved",
        "summary": "PostgreSQL connection pool exhausted. Service restarted and recovered.",
        "created_at": "2026-04-04T09:58:00Z",
    },
    {
        "incident_id": "INC-M3N4O5P6",
        "service": "etl-pipeline",
        "failure_type": "failed_job",
        "severity": "medium",
        "status": "open",
        "summary": "Spark ETL job failed at stage 3. Job resubmission pending.",
        "created_at": "2026-04-04T11:02:00Z",
    },
]

_STUB_METRICS = {
    "total_incidents": 47,
    "open_incidents": 3,
    "resolved_incidents": 44,
    "auto_remediated": 38,
    "mttd_s": 42.0,
    "mttr_s": 284.0,
    "agent_success_rate": 0.91,
}


# ── Pages ──────────────────────────────────────────────────────────────────────

def page_live_incidents() -> None:
    st.title("🔴 Live Incident Feed")
    st.caption("Real-time view of active and recent incidents across all monitored services.")

    # KPI strip
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Incidents", _STUB_METRICS["total_incidents"], delta="+2 today")
    c2.metric("Open", _STUB_METRICS["open_incidents"], delta_color="inverse")
    c3.metric("Resolved", _STUB_METRICS["resolved_incidents"])
    c4.metric("Auto-Remediated", _STUB_METRICS["auto_remediated"])

    st.divider()

    # Incident cards
    for inc in _STUB_INCIDENTS:
        sev = inc["severity"]
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(
                f"**{inc['incident_id']}** — `{inc['service']}`  \n"
                f"{inc['summary']}",
            )
        with col2:
            st.markdown(_badge(sev, _SEVERITY_COLOUR.get(sev, "#808080")), unsafe_allow_html=True)
        with col3:
            icon = _STATUS_ICON.get(inc["status"], "")
            st.markdown(f"{icon} `{inc['status']}`")
        st.divider()

    st.caption("TODO Stage 2: live data from IncidentService + auto-refresh every 10s")


def page_pipeline_simulator() -> None:
    st.title("⚡ Pipeline Simulator")
    st.caption("Manually inject failure scenarios to test the AIOps agent pipeline end-to-end.")

    col1, col2 = st.columns(2)

    with col1:
        service = st.selectbox(
            "Target Service",
            ["payment-service", "api-gateway", "auth-service", "order-processor", "etl-pipeline"],
        )
        failure_type = st.selectbox(
            "Failure Type",
            ["service_crash", "high_latency", "db_connection_failure", "failed_job", "bad_deployment"],
        )
        custom_desc = st.text_area("Custom Description (optional)", height=80)

    with col2:
        st.markdown("**Pipeline that will run:**")
        st.code(
            f"1. monitoring_agent      ← detect {failure_type}\n"
            f"2. log_analysis_agent    ← parse {service} logs\n"
            f"3. incident_classifier   ← classify severity\n"
            f"4. remediation_agent     ← build fix plan\n"
            f"5. validation_agent      ← verify recovery\n"
            f"6. jira_reporting_agent  ← create ticket",
            language=None,
        )

    trigger = st.button("▶ Trigger Incident", type="primary", use_container_width=True)

    if trigger:
        with st.spinner(f"Running AIOps pipeline for {service} [{failure_type}]…"):
            # TODO Stage 2: call graph.workflow.aiops_graph.invoke(...)
            time.sleep(1.5)   # simulate pipeline latency

        st.success("Pipeline complete! Incident created.")
        st.info("TODO Stage 2: show live agent execution trace here")

        st.json({
            "incident_id": "INC-DEMO1234",
            "service": service,
            "failure_type": failure_type,
            "severity": "high",
            "status": "escalated",
            "execution_path": [
                "monitoring_agent", "log_analysis_agent",
                "incident_classifier_agent", "remediation_agent",
                "validation_agent", "jira_reporting_agent",
            ],
        })


def page_metrics() -> None:
    st.title("📊 Metrics & KPIs")
    st.caption("Platform performance indicators and SLO tracking.")

    # MTTD / MTTR
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MTTD", f"{_STUB_METRICS['mttd_s']:.0f}s",  help="Mean Time To Detect")
    c2.metric("MTTR", f"{_STUB_METRICS['mttr_s']:.0f}s",  help="Mean Time To Resolve")
    c3.metric("Agent Success Rate", f"{_STUB_METRICS['agent_success_rate']:.0%}")
    c4.metric("Auto-Remediation Rate", f"{_STUB_METRICS['auto_remediated'] / max(_STUB_METRICS['resolved_incidents'], 1):.0%}")

    st.divider()

    st.subheader("Incident Volume by Failure Type")
    # TODO Stage 2: real chart from incident_service aggregations
    import pandas as pd
    chart_data = pd.DataFrame({
        "Failure Type": ["Service Crash", "High Latency", "DB Failure", "Failed Job", "Bad Deployment"],
        "Count": [12, 18, 8, 6, 3],
    }).set_index("Failure Type")
    st.bar_chart(chart_data)

    st.divider()
    st.subheader("Service Error Rate (last 30 min)")
    st.info("TODO Stage 2: live metric charts from MetricsService / Prometheus")


def page_audit_log() -> None:
    st.title("📋 Audit Log")
    st.caption("Immutable chain-of-thought trail for every agent action. Compliance-ready.")

    _STUB_AUDIT = [
        {"timestamp": "2026-04-04T10:12:01Z", "actor": "monitoring_agent",          "incident": "INC-A1B2C3D4", "action": "Event confirmed — OOMKill on payment-service"},
        {"timestamp": "2026-04-04T10:12:02Z", "actor": "log_analysis_agent",        "incident": "INC-A1B2C3D4", "action": "3 RCA findings. Patterns: Memory exhaustion, Deployment regression"},
        {"timestamp": "2026-04-04T10:12:03Z", "actor": "incident_classifier_agent", "incident": "INC-A1B2C3D4", "action": "Severity=CRITICAL, escalate=True"},
        {"timestamp": "2026-04-04T10:12:04Z", "actor": "jira_reporting_agent",      "incident": "INC-A1B2C3D4", "action": "Ticket AIOPS-1042 created — Highest priority, assigned to payments-oncall"},
        {"timestamp": "2026-04-04T10:35:10Z", "actor": "monitoring_agent",          "incident": "INC-E5F6G7H8", "action": "Event confirmed — latency spike on api-gateway"},
        {"timestamp": "2026-04-04T10:35:11Z", "actor": "remediation_agent",         "incident": "INC-E5F6G7H8", "action": "Plan: clear_cache → scale_up. Executed: True"},
        {"timestamp": "2026-04-04T10:35:14Z", "actor": "validation_agent",          "incident": "INC-E5F6G7H8", "action": "Validation PASSED. Latency back within SLO."},
    ]

    search = st.text_input("Search audit log", placeholder="incident ID, actor, or keyword…")

    entries = _STUB_AUDIT
    if search:
        entries = [e for e in entries if search.lower() in str(e).lower()]

    for entry in entries:
        cols = st.columns([1.5, 1.5, 1.5, 5])
        cols[0].caption(entry["timestamp"][11:19])
        cols[1].markdown(f"`{entry['actor']}`")
        cols[2].markdown(f"`{entry['incident']}`")
        cols[3].markdown(entry["action"])

    st.caption("TODO Stage 2: live data from AuditService + pagination")


def page_jira_board() -> None:
    st.title("🎫 Jira Board")
    st.caption("Jira-style incident ticket tracker. Mirrors ticket state from the Jira Reporting Agent.")

    columns = {
        "Open": [i for i in _STUB_INCIDENTS if i["status"] == "open"],
        "In Progress": [i for i in _STUB_INCIDENTS if i["status"] in ("triaged", "analyzing", "remediating")],
        "Escalated": [i for i in _STUB_INCIDENTS if i["status"] == "escalated"],
        "Done": [i for i in _STUB_INCIDENTS if i["status"] in ("resolved", "closed")],
    }

    cols = st.columns(len(columns))
    for col, (status, incidents) in zip(cols, columns.items()):
        with col:
            st.markdown(f"**{status}** ({len(incidents)})")
            st.divider()
            for inc in incidents:
                sev = inc["severity"]
                with st.container(border=True):
                    st.markdown(f"**{inc['incident_id']}**")
                    st.markdown(_badge(sev, _SEVERITY_COLOUR.get(sev, "#808080")), unsafe_allow_html=True)
                    st.caption(f"`{inc['service']}`")
                    st.caption(inc["summary"][:60] + "…")

    st.caption("TODO Stage 2: two-way sync with real Jira API via JiraService")


# ── Router ─────────────────────────────────────────────────────────────────────
_PAGE_MAP = {
    "🔴 Live Incidents":    page_live_incidents,
    "⚡ Pipeline Simulator": page_pipeline_simulator,
    "📊 Metrics & KPIs":    page_metrics,
    "📋 Audit Log":         page_audit_log,
    "🎫 Jira Board":        page_jira_board,
}

_PAGE_MAP[page]()
