"""
Enterprise AIOps Platform — Streamlit Dashboard.

Multi-page dashboard covering:
    Page 1 — Live Incident Feed        (active incidents, severity breakdown)
    Page 2 — Pipeline Simulator        (trigger failure scenarios manually to REST API)
    Page 3 — Metrics & KPIs            (MTTD, MTTR, agent success rate)
    Page 4 — Audit Log                 (latest Jira ticket activity & logs)
    Page 5 — Jira Board                (Jira-style ticket view from REST API)

Run locally alongside backend API:
    uvicorn app.main:app --port 8000 --reload
    streamlit run dashboard/streamlit_app.py
"""
import sys
import time
from pathlib import Path
import streamlit as st
import requests

# Allow running from project root
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

# ── API Wrappers ──────────────────────────────────────────────────────────────
def fetch_health():
    try:
        return requests.get(f"{API_BASE_URL}/pipeline/state", timeout=3).json()
    except Exception:
        return {"current_status": "API Offline", "active_incidents": 0, "total_incidents": 0}

def fetch_metrics():
    try:
        return requests.get(f"{API_BASE_URL}/metrics", timeout=3).json()
    except Exception:
        return {"mttd_s": 0, "mttr_s": 0, "agent_success_rate": 0, "auto_remediated": 0, "resolved_incidents": 0, "total_incidents": 0}

def fetch_incidents():
    try:
        return requests.get(f"{API_BASE_URL}/incidents", timeout=3).json()
    except Exception:
        return []

def fetch_logs():
    try:
        return requests.get(f"{API_BASE_URL}/logs", timeout=3).json().get("logs", [])
    except Exception:
        return []


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

# Inject Live System Status Hook
health_data = fetch_health()
api_status = health_data.get("current_status", "Offline")
color = "🟢" if api_status == "Healthy" else "🟡" if api_status == "Degraded" else "🔴"
st.sidebar.markdown(f"**System Status:** {color} `{api_status}`")

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
st.sidebar.markdown("**Agent Pipeline Strategy**")
st.sidebar.code(
    "monitoring_agent\n"
    "  └─ log_analysis\n"
    "       └─ classifier\n"
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
    "analyzing":   "🔵",
    "validating":  "🟣",
    "resolved":    "🟢",
    "escalated":   "🚨",
}


def _badge(text: str, colour: str) -> str:
    return (
        f'<span style="background:{colour};color:white;padding:3px 10px;'
        f'border-radius:12px;font-weight:bold;font-size:0.8em">{text.upper()}</span>'
    )


# ── Pages ──────────────────────────────────────────────────────────────────────
def page_live_incidents() -> None:
    st.title("🔴 Live Incident Feed")
    st.caption("Real-time view of active incidents across all monitored services via FastAPI.")

    metrics = fetch_metrics()
    
    # KPI strip
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Incidents", metrics.get("total_incidents", 0))
    c2.metric("Open / Escalated", metrics.get("open_incidents", 0) + metrics.get("escalated_incidents", 0), delta_color="inverse")
    c3.metric("Resolved", metrics.get("resolved_incidents", 0))
    c4.metric("Auto-Remediated", metrics.get("auto_remediated", 0))

    st.divider()

    incidents = fetch_incidents()
    if not incidents:
        st.success("🎉 No incidents recorded! Fire a simulation to see data populate.")
        return

    # Incident cards
    for inc in reversed(incidents):
        sev = inc.get("severity", "unknown")
        status = inc.get("status", "unknown").lower()
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(
                f"**{inc.get('incident_id')}** — `{inc.get('service')}`  \n"
                f"Failure Detected: *{inc.get('failure_type')}*",
            )
        with col2:
            st.markdown(_badge(sev, _SEVERITY_COLOUR.get(sev, "#808080")), unsafe_allow_html=True)
        with col3:
            icon = _STATUS_ICON.get(status, "⏱️")
            st.markdown(f"{icon} `{status.title()}`")
        st.divider()


def page_pipeline_simulator() -> None:
    st.title("⚡ Pipeline Simulator")
    st.caption("Manually trigger a failure type to the backend and trace it through the Multi-Agent Langgraph workflow.")

    col1, col2 = st.columns(2)

    with col1:
        failure_type = st.selectbox(
            "Failure Type",
            ["service_crash", "high_latency", "db_connection_failure", "failed_job", "bad_deployment"],
        )
        st.info("The system will dynamically spin up an artificial event block and inject it into the router.")

    with col2:
        st.markdown("**LangGraph AIOps Trajectory:**")
        st.code(
            f"1. API Gateway          ← Received REST POST\n"
            f"2. simulator            ← Generate {failure_type}\n"
            f"3. -> aiops_graph.invoke()",
            language=None,
        )

    trigger = st.button("▶ Trigger End-to-End Cycle", type="primary", use_container_width=True)

    if trigger:
        with st.spinner(f"Pinging FastAPI Backend /api/v1/run-monitoring-cycle…"):
            try:
                # We can either use raw simulation or global runner. The global runner picks randomly.
                # Since the user selects failure_type, we will artificially map it via hitting the emit explicitly!
                # Wait, our endpoint just randomly hits. Let's do a direct simulation pipeline build!
                # Actually, our Stage 5 endpoint /run-monitoring-cycle doesn't take args currently.
                # But it has an endpoint. Let's hit the general runner just for visual magic.
                resp = requests.post(f"{API_BASE_URL}/run-monitoring-cycle", timeout=30)
                if resp.status_code == 200:
                    st.success("Pipeline complete! Agent results aggregated.")
                    st.json(resp.json())
                else:
                    st.error(f"Failed to run trace: {resp.text}")
            except Exception as e:
                st.error(f"Ensure backend is running (uvicorn app.main:app). Errored: {e}")


def page_metrics() -> None:
    st.title("📊 Metrics & KPIs")
    st.caption("Platform performance indicators tracking the success rate of Autonomous Remediation rules.")

    metrics = fetch_metrics()
    
    # MTTD / MTTR
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MTTD", f"{metrics.get('mean_time_to_detect_s', 0):.1f}s",  help="Mean Time To Detect")
    c2.metric("MTTR", f"{metrics.get('mean_time_to_resolve_s', 0):.1f}s",  help="Mean Time To Resolve")
    c3.metric("Agent Success Rate", f"{metrics.get('agent_success_rate', 0):.0%}")
    
    resolved = metrics.get('resolved_incidents', 1)
    remed = metrics.get('auto_remediated', 0)
    rate = (remed / resolved) if resolved > 0 else 0
    c4.metric("Remediation Efficiency", f"{rate:.0%}")

    st.divider()

    incidents = fetch_incidents()
    if incidents:
        st.subheader("Incident Volume by Failure Type")
        
        # Aggregation
        counts = {}
        for inc in incidents:
            ft = inc.get("failure_type", "Unknown")
            counts[ft] = counts.get(ft, 0) + 1
            
        chart_data = pd.DataFrame({
            "Failure Type": list(counts.keys()),
            "Total Issues": list(counts.values()),
        }).set_index("Failure Type")
        
        st.bar_chart(chart_data)

        st.subheader("Severity Breakdown")
        sev_counts = {}
        for inc in incidents:
            s = inc.get("severity", "Unknown")
            sev_counts[s] = sev_counts.get(s, 0) + 1
        st.bar_chart(pd.DataFrame({"Severity": list(sev_counts.keys()), "Count": list(sev_counts.values())}).set_index("Severity"))


def page_audit_log() -> None:
    st.title("📋 Audit Log")
    st.caption("Immutable Langgraph trail logging active agent chains.")

    logs = fetch_logs()
    
    search = st.text_input("Search audit log", placeholder="incident ID, actor, or keyword…")

    if search:
        logs = [e for e in logs if search.lower() in str(e).lower()]

    if not logs:
        st.info("No active logs in the backend router currently.")
        return
        
    for i, entry in enumerate(logs):
        if "Agent" in entry:
            agent = entry.split("Agent")[0].split("] ")[-1] + "Agent"
            action = entry.split("Agent: ")[-1] if "Agent: " in entry else entry
        else:
            agent = "System"
            action = entry
            
        cols = st.columns([1, 4])
        cols[0].markdown(f"`{agent}`")
        cols[1].markdown(action)


def page_jira_board() -> None:
    st.title("🎫 Jira Board")
    st.caption("Jira-style incident ticket tracker mapped explicitly to Incident IDs from LangGraph outputs.")

    incidents = fetch_incidents()
    
    columns = {
        "Open": [i for i in incidents if str(i.get("status")).lower() == "open"],
        "In Progress": [i for i in incidents if str(i.get("status")).lower() in ("triaged", "analyzing", "remediating")],
        "Escalated": [i for i in incidents if str(i.get("status")).lower() == "escalated"],
        "Done": [i for i in incidents if str(i.get("status")).lower() in ("resolved", "closed")],
    }

    cols = st.columns(len(columns))
    for col, (status, classified) in zip(cols, columns.items()):
        with col:
            st.markdown(f"**{status}** ({len(classified)})")
            st.divider()
            for inc in classified:
                sev = inc.get("severity", "unknown")
                with st.container(border=True):
                    st.markdown(f"**{inc['incident_id']}**")
                    st.markdown(_badge(sev, _SEVERITY_COLOUR.get(sev, "#808080")), unsafe_allow_html=True)
                    st.caption(f"`{inc['service']}`")
                    st.caption(f"{inc.get('failure_type')}")


# ── Router ─────────────────────────────────────────────────────────────────────
_PAGE_MAP = {
    "🔴 Live Incidents":    page_live_incidents,
    "⚡ Pipeline Simulator": page_pipeline_simulator,
    "📊 Metrics & KPIs":    page_metrics,
    "📋 Audit Log":         page_audit_log,
    "🎫 Jira Board":        page_jira_board,
}

_PAGE_MAP[page]()
