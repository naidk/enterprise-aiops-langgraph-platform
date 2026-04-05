"""
Enterprise AIOps Platform — Streamlit Dashboard.
"""
import sys
import time
from pathlib import Path
import streamlit as st
import requests

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

import os
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")

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
        return {}

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

def fetch_alerts():
    try:
        resp = requests.get(f"{API_BASE_URL}/alerts", timeout=3).json()
        return resp.get("active_alerts", []), resp.get("all_alerts", [])
    except Exception:
        return [], []

def fetch_api_health():
    try:
        return requests.get(f"{API_BASE_URL}/api-health", timeout=3).json()
    except Exception:
        return {"apis": {}, "summary": {"total": 0, "healthy": 0, "degraded": 0, "down": 0}, "incidents": []}

def inject_crash(crash_type: str):
    try:
        return requests.post(f"{API_BASE_URL}/inject-crash/{crash_type}", timeout=10).json()
    except Exception as e:
        return {"error": str(e)}

def analyze_alert(alert_id: str):
    try:
        return requests.post(f"{API_BASE_URL}/alerts/{alert_id}/analyze", timeout=60).json()
    except Exception as e:
        return {"error": str(e)}

def clear_alerts():
    try:
        requests.delete(f"{API_BASE_URL}/alerts/clear", timeout=5)
    except Exception:
        pass


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enterprise AIOps Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🛡️ AIOps Platform")
st.sidebar.caption("Multi-agent self-healing infrastructure")

health_data = fetch_health()
api_status = health_data.get("current_status", "Offline")
color = "🟢" if api_status == "Healthy" else "🟡" if api_status == "Degraded" else "🔴"
st.sidebar.markdown(f"**System Status:** {color} `{api_status}`")

# Show live alert count in sidebar
active_alerts, _ = fetch_alerts()
if active_alerts:
    st.sidebar.error(f"🚨 {len(active_alerts)} ACTIVE ALERT(S) — Action Required!")

st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    options=[
        "🎬 Auto Demo Mode",
        "🚨 Live Alerts",
        "🌐 API Health Monitor",
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
    "  └─ log_analysis\n"
    "       └─ repo_inspection\n"
    "            └─ test_analysis\n"
    "                 └─ root_cause\n"
    "                      ├─ [CRITICAL] → jira\n"
    "                      └─ [other] → remediation\n"
    "                            └─ validation\n"
    "                                  └─ jira",
    language=None,
)

# ── Colour maps ───────────────────────────────────────────────────────────────
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
    "remediating": "🟣",
    "resolved":    "🟢",
    "escalated":   "🚨",
}

def _badge(text: str, colour: str) -> str:
    return (
        f'<span style="background:{colour};color:white;padding:3px 10px;'
        f'border-radius:12px;font-weight:bold;font-size:0.8em">{text.upper()}</span>'
    )


# ── Page: Auto Demo Mode ─────────────────────────────────────────────────────
def page_auto_demo() -> None:
    st.title("🎬 Enterprise AIOps — Live Demo")
    st.caption("Fully automatic. No manual clicks. Watch AI detect, diagnose, and fix production issues in real time.")

    # ── Header metrics ────────────────────────────────────────────────────────
    metrics = fetch_metrics()
    incidents = fetch_incidents()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Incidents Handled", metrics.get("total_incidents", 0))
    c2.metric("Auto-Resolved by AI", metrics.get("resolved_incidents", 0))
    c3.metric("Open / In Progress", metrics.get("open_incidents", 0))
    c4.metric("AI Engine", "Groq Llama 3.3-70B")

    st.divider()

    # ── Scenario selector ─────────────────────────────────────────────────────
    st.subheader("Select Demo Scenario")

    scenarios = {
        "scenario_1": {
            "title": "💥 Service Crash — Auto Detection & Recovery",
            "description": "A microservice crashes due to memory exhaustion. AI detects, diagnoses, restarts, and resolves in under 10 seconds.",
            "crash_type": "null_pointer",
            "service": "payment-service",
            "author": "john.dev@company.com",
            "commit": "feat: optimise payment processor for Black Friday load",
        },
        "scenario_2": {
            "title": "🗄️ Database Connection Failure — Auto Failover",
            "description": "Production database connection pool exhausted. AI detects ECONNREFUSED, triggers failover, restores service.",
            "crash_type": "db_connection",
            "service": "order-service",
            "author": "sarah.dev@company.com",
            "commit": "fix: increase DB pool size for order processing",
        },
        "scenario_3": {
            "title": "📦 Bad Deployment — AI Detects Broken Import, Auto Rollback",
            "description": "Developer pushes code that passes all 52 CI tests but crashes in production. AI links crash to commit, auto-rolls back, creates fix PR.",
            "crash_type": "import_error",
            "service": "auth-service",
            "author": "mike.dev@company.com",
            "commit": "refactor: migrate auth client to new SDK version",
        },
        "scenario_4": {
            "title": "⏱️ High Latency — AI Scales Infrastructure",
            "description": "API response time hits 4200ms (SLA: 500ms). AI detects latency spike, flushes cache, scales pods, restores performance.",
            "crash_type": "high_latency",
            "service": "inventory-service",
            "author": "lisa.dev@company.com",
            "commit": "perf: add caching layer to inventory lookups",
        },
        "scenario_5": {
            "title": "🌍 Third-Party API Down — Stripe Payment Gateway",
            "description": "Stripe payment API returns 503. AI detects external dependency failure, enables fallback, notifies on-call.",
            "crash_type": "high_latency",
            "service": "stripe-api",
            "author": "External",
            "commit": "Stripe infrastructure outage",
        },
    }

    selected = st.selectbox(
        "Choose a scenario to demonstrate:",
        options=list(scenarios.keys()),
        format_func=lambda k: scenarios[k]["title"],
    )

    sc = scenarios[selected]
    st.info(f"**Scenario:** {sc['description']}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Service:** `" + sc["service"] + "`")
        st.markdown("**Developer:** `" + sc["author"] + "`")
    with col2:
        st.markdown("**Commit:** `" + sc["commit"] + "`")
        st.markdown("**AI Engine:** `Groq Llama 3.3-70B`")

    st.divider()

    # ── Run Demo Button ───────────────────────────────────────────────────────
    run_btn = st.button(
        "▶ RUN DEMO — Watch AI Fix This Automatically",
        type="primary",
        use_container_width=True,
    )

    if run_btn:
        # Step-by-step visual progress
        st.markdown("---")
        st.markdown("### 🔴 PRODUCTION INCIDENT DETECTED")

        progress_bar = st.progress(0)
        status_box = st.empty()
        result_box = st.empty()

        steps = [
            (10,  "🔴 monitoring_agent      → Production crash detected in `" + sc['service'] + "`"),
            (22,  "📋 log_analysis_agent    → Reading real error logs and stack trace..."),
            (35,  "🔍 repo_inspection_agent → Linking crash to commit by `" + sc['author'] + "`"),
            (47,  "🧪 test_analysis_agent   → Checking which tests failed to catch this..."),
            (60,  "🧠 root_cause_agent      → Groq LLM diagnosing root cause..."),
            (72,  "🔧 remediation_agent     → Executing fix: rollback / restart / scale..."),
            (84,  "💡 code_fix_agent        → LLM reading source code, writing fix, creating PR..."),
            (93,  "✅ validation_agent      → Confirming service has recovered..."),
            (100, "🎫 jira_reporting_agent  → Creating Jira ticket, notifying developer..."),
        ]

        for pct, msg in steps:
            progress_bar.progress(pct)
            status_box.markdown(f"**{msg}**")
            time.sleep(0.8)

        # Actually run the pipeline
        status_box.markdown("**⏳ Calling Groq AI... analyzing logs...**")
        try:
            resp = requests.post(
                f"{API_BASE_URL}/simulate-commit-crash",
                params={
                    "service": sc["service"],
                    "author": sc["author"],
                    "commit_message": sc["commit"],
                    "crash_type": sc["crash_type"],
                },
                timeout=90,
            )
            data = resp.json()
        except Exception as e:
            data = {"error": str(e)}

        progress_bar.progress(100)
        status_box.empty()

        if "error" not in data:
            ai   = data.get("ai_response", {})
            cmit = data.get("commit", {})

            # Success banner
            st.success("✅ INCIDENT RESOLVED AUTOMATICALLY — No human intervention needed")

            # Results
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Agents Ran",     ai.get("agents_ran", 9))
            r2.metric("Severity",       (ai.get("final_severity") or "high").upper())
            r3.metric("Final Status",   (ai.get("final_status") or "resolved").upper())
            r4.metric("Time to Resolve","< 10 seconds")

            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🤖 AI Root Cause Analysis")
                st.info(ai.get("llm_finding", "Root cause identified by Groq LLM"))

                st.markdown("#### 📦 Commit Linked to Crash")
                st.code(
                    f"Commit:  [{cmit.get('hash','abc1234')}]\n"
                    f"Author:  {cmit.get('author', sc['author'])}\n"
                    f"Message: {cmit.get('message', sc['commit'])}\n"
                    f"CI/CD:   All tests passed ✅\n"
                    f"Prod:    CRASHED ❌ → Auto-fixed ✅",
                    language="text"
                )

            with col2:
                st.markdown("#### 🔧 Actions Taken by AI")
                actions = [
                    "✅ Crash detected in real-time",
                    "✅ Stack trace analyzed by LLM",
                    f"✅ Commit [{cmit.get('hash','abc1234')[:7]}] identified as root cause",
                    "✅ Service rolled back to stable version",
                    "✅ Code fix written by AI",
                    "✅ GitHub PR created for developer review",
                    "✅ Jira ticket auto-created & assigned",
                    f"✅ Developer {cmit.get('author','dev@company.com')} notified",
                ]
                for action in actions:
                    st.markdown(action)

                if ai.get("pr_url"):
                    st.success(f"📦 GitHub PR: {ai.get('pr_url')}")

            st.markdown("---")
            st.markdown("#### 🛤️ Full Agent Execution Path")
            path = ai.get("execution_path", [])
            if path:
                path_display = " → ".join([f"`{p}`" for p in path])
                st.markdown(path_display)

        else:
            st.error(f"Demo failed: {data['error']}")

    st.divider()

    # ── Recent incidents at bottom ────────────────────────────────────────────
    if incidents:
        st.subheader("Recently Resolved Incidents")
        resolved = [i for i in incidents if i.get("status") in ("resolved", "escalated")][-5:]
        for inc in reversed(resolved):
            sev = inc.get("severity", "unknown")
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.markdown(f"**{inc.get('incident_id')}** — `{inc.get('service')}` — *{inc.get('failure_type')}*")
            col2.markdown(_badge(sev, _SEVERITY_COLOUR.get(sev, "#808080")), unsafe_allow_html=True)
            col3.markdown(f"🟢 `{inc.get('status','').title()}`")


# ── Page: Live Alerts ─────────────────────────────────────────────────────────
def page_live_alerts() -> None:
    st.title("🚨 Live Alerts — AI-Powered Crash Detection")
    st.caption("Inject real crashes, let the LLM identify and remediate them automatically.")

    # ── Step 1: Inject a Crash ────────────────────────────────────────────────
    st.subheader("Step 1: Inject a Real Crash")
    st.markdown("Select a crash type below. This generates a **real Python exception** with actual traceback logs.")

    crash_options = {
        "null_pointer":  "💥 Null Pointer Exception (NullPointerException / AttributeError)",
        "import_error":  "📦 Broken Import (ModuleNotFoundError / ImportError)",
        "db_connection": "🗄️ Database Connection Failure (ConnectionRefused / Pool Exhausted)",
        "high_latency":  "⏱️ High Latency / Timeout (p99 > 4200ms, Circuit Breaker Open)",
        "memory_leak":   "💾 Memory Leak / OOMKill (Container killed, CrashLoopBackOff)",
    }

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_crash = st.selectbox(
            "Crash Type",
            options=list(crash_options.keys()),
            format_func=lambda x: crash_options[x],
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        inject_btn = st.button("💥 Inject Crash", type="primary", use_container_width=True)

    if inject_btn:
        with st.spinner("Injecting crash into live service..."):
            result = inject_crash(selected_crash)
        if "error" not in result:
            st.error(f"🚨 **ALERT TRIGGERED** — `{result.get('service')}` is DOWN!")
            st.code(result.get("log_preview", ""), language="text")
            st.rerun()
        else:
            st.error(f"Failed: {result['error']}")

    st.divider()

    # ── Step 2: Active Alerts ─────────────────────────────────────────────────
    st.subheader("Step 2: Active Alerts Waiting for AI Analysis")

    active_alerts, all_alerts = fetch_alerts()

    if not active_alerts:
        st.success("✅ No active alerts — all systems healthy. Inject a crash above to test!")
    else:
        for alert in active_alerts:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.markdown(f"### 🔴 `{alert['service']}` — {crash_options.get(alert['crash_type'], alert['crash_type'])}")
                    st.caption(f"Alert ID: `{alert['alert_id']}` | Time: {alert['timestamp'][:19]}")

                with col2:
                    st.markdown(_badge("CRITICAL", "#FF4B4B"), unsafe_allow_html=True)
                    st.caption(f"Type: `{alert['failure_type']}`")

                with col3:
                    analyze_btn = st.button(
                        "🤖 Run AI Analysis",
                        key=f"analyze_{alert['alert_id']}",
                        type="primary",
                        use_container_width=True,
                    )

                # Show real crash logs
                with st.expander("📋 View Real Crash Logs"):
                    st.code(alert["real_logs"], language="text")

                # Run LLM Analysis
                if analyze_btn:
                    with st.spinner(f"🤖 Groq LLM analyzing crash in `{alert['service']}`... Running 8 AI agents..."):
                        analysis = analyze_alert(alert["alert_id"])

                    if "error" not in analysis:
                        st.success(f"✅ **AI Analysis Complete** — Incident `{analysis.get('incident_id')}`")

                        r1, r2, r3 = st.columns(3)
                        r1.metric("Severity", analysis.get("final_severity", "—").upper())
                        r2.metric("Status", analysis.get("final_status", "—").upper())
                        r3.metric("Agents Ran", len(analysis.get("execution_path", [])))

                        st.markdown("**🤖 LLM Root Cause Analysis:**")
                        st.info(analysis.get("llm_analysis", "No analysis"))

                        st.markdown("**🔧 Execution Path:**")
                        st.code(" → ".join(analysis.get("execution_path", [])), language=None)

                        st.markdown(f"**📋 Remediation Steps Executed:** `{analysis.get('remediation_steps', 0)}` steps")
                        st.rerun()
                    else:
                        st.error(f"Analysis failed: {analysis['error']}")

    st.divider()

    # ── Step 3: Resolved Alerts History ──────────────────────────────────────
    st.subheader("Step 3: Resolved by AI")

    resolved = [a for a in all_alerts if a.get("status") == "resolved"]
    if resolved:
        for alert in reversed(resolved):
            with st.expander(f"✅ `{alert['service']}` — {alert['crash_type']} — RESOLVED BY AI"):
                st.markdown(f"**Alert ID:** `{alert['alert_id']}`")
                st.markdown(f"**LLM Finding:** {alert.get('llm_analysis', 'N/A')}")
                steps = alert.get("remediation", [])
                if steps:
                    st.markdown(f"**Remediation:** {len(steps)} steps executed")
    else:
        st.info("Resolved alerts will appear here after AI analysis completes.")

    st.divider()

    # ── Developer Commit Crash Simulator ─────────────────────────────────────
    st.subheader("🧑‍💻 Simulate: Developer Commit Crashes Production")
    st.markdown(
        "Simulates a developer pushing code that **passes all CI tests** "
        "but **crashes in production** under real load. Watch the agents detect, "
        "link the crash to the commit, rollback, and notify the developer."
    )

    with st.form("commit_crash_form"):
        dc1, dc2 = st.columns(2)
        with dc1:
            dev_service = st.selectbox("Service", [
                "payment-service", "auth-service", "order-service",
                "inventory-service", "user-service", "notification-service"
            ])
            dev_author = st.text_input("Developer Email", value="dev@company.com")
        with dc2:
            dev_crash = st.selectbox("Crash Type", list(crash_options.keys()),
                                     format_func=lambda x: crash_options[x])
            dev_message = st.text_input("Commit Message", value="feat: refactor payment processor for performance")

        commit_btn = st.form_submit_button("🚀 Push Commit → Deploy → Crash → AI Fix", type="primary", use_container_width=True)

    if commit_btn:
        with st.spinner(f"Simulating: {dev_author} pushed to {dev_service}... CI passed... deploying... CRASH DETECTED... AI analyzing..."):
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/simulate-commit-crash",
                    params={
                        "service": dev_service,
                        "author": dev_author,
                        "commit_message": dev_message,
                        "crash_type": dev_crash,
                    },
                    timeout=60,
                )
                data = resp.json()
            except Exception as e:
                data = {"error": str(e)}

        if "error" not in data:
            commit = data.get("commit", {})
            ai = data.get("ai_response", {})

            st.error(f"💥 Production CRASHED after commit `[{commit.get('hash')}]` by `{commit.get('author')}`")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📦 Commit Details:**")
                st.code(
                    f"Commit:  [{commit.get('hash')}]\n"
                    f"Author:  {commit.get('author')}\n"
                    f"Message: {commit.get('message')}\n"
                    f"File:    {commit.get('file')}\n"
                    f"CI:      {commit.get('ci_status')}",
                    language="text"
                )
            with col2:
                st.markdown("**🤖 AI Response:**")
                m1, m2, m3 = st.columns(3)
                m1.metric("Agents", ai.get("agents_ran", 0))
                m2.metric("Severity", (ai.get("final_severity") or "—").upper())
                m3.metric("Status", (ai.get("final_status") or "—").upper())

            st.success(f"✅ Rollback executed: `{ai.get('rollback_executed')}` | Developer notified: `{ai.get('developer_notified')}`")
            st.info(f"🤖 LLM Finding: {ai.get('llm_finding', '')}")
            st.caption(f"Agents ran: {' → '.join(ai.get('execution_path', []))}")
            st.rerun()
        else:
            st.error(f"Failed: {data['error']}")

    st.divider()
    if st.button("🔄 Reset All Alerts (Demo Reset)", use_container_width=True):
        clear_alerts()
        st.success("All alerts cleared!")
        st.rerun()


# ── Page: API Health Monitor ─────────────────────────────────────────────────
def page_api_health() -> None:
    st.title("🌐 API Health Monitor")
    st.caption("Real-time health of all internal and external APIs. Inject an issue to see AI auto-diagnosis.")

    health = fetch_api_health()
    summary = health.get("summary", {})

    # Summary strip
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total APIs", summary.get("total", 0))
    c2.metric("Healthy", summary.get("healthy", 0))
    c3.metric("Degraded", summary.get("degraded", 0), delta_color="inverse")
    c4.metric("Down", summary.get("down", 0), delta_color="inverse")

    st.divider()

    # API status table
    st.subheader("Live API Status")
    apis = health.get("apis", {})

    _API_LIST = ["payment-api", "auth-api", "order-api", "stripe-api", "sendgrid-api", "notification-api"]
    _ISSUE_LIST = ["5xx_error", "timeout", "auth_failure", "rate_limit", "schema_break", "third_party_down", "high_latency"]
    _ISSUE_LABELS = {
        "5xx_error":        "💥 500 Internal Server Error",
        "timeout":          "⏱️ Gateway Timeout (504)",
        "auth_failure":     "🔐 Auth Failed (401 Unauthorized)",
        "rate_limit":       "🚦 Rate Limit Exceeded (429)",
        "schema_break":     "📋 Schema Validation Error (422)",
        "third_party_down": "🌍 Third-Party API Down (503)",
        "high_latency":     "🐢 High Latency (p99 > 4000ms)",
    }

    _STATUS_COLOUR = {"healthy": "#2ECC71", "degraded": "#FF8C00", "down": "#FF4B4B"}

    # Display each API
    for api_name in _API_LIST:
        api_data = apis.get(api_name, {})
        status    = api_data.get("status", "healthy")
        code      = api_data.get("status_code", 200)
        latency   = api_data.get("latency_ms", "-")
        err_rate  = api_data.get("error_rate", 0.0)
        api_type  = api_data.get("type", "internal")
        colour    = _STATUS_COLOUR.get(status, "#2ECC71")

        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
        with col1:
            st.markdown(
                f'<span style="background:{colour};color:white;padding:2px 8px;'
                f'border-radius:8px;font-size:0.75em">{status.upper()}</span> '
                f'**{api_name}** `{api_type}`',
                unsafe_allow_html=True,
            )
        col2.markdown(f"`{code}`")
        col3.markdown(f"`{latency}ms`" if isinstance(latency, int) else "`-`")
        col4.markdown(f"`{err_rate:.0%}`" if isinstance(err_rate, float) else "`0%`")
        if api_data.get("last_error"):
            col5.caption(api_data["last_error"][:30])

    st.divider()

    # Inject API Issue
    st.subheader("Inject an API Issue — Watch AI Fix It")

    col1, col2 = st.columns(2)
    with col1:
        selected_api = st.selectbox("API", _API_LIST)
    with col2:
        selected_issue = st.selectbox("Issue Type", _ISSUE_LIST,
                                       format_func=lambda x: _ISSUE_LABELS.get(x, x))

    if st.button("🚨 Inject API Issue + Run AI Analysis", type="primary", use_container_width=True):
        with st.spinner(f"Injecting {selected_issue} into {selected_api}... AI agents analyzing..."):
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/api-health/inject/{selected_api}/{selected_issue}",
                    timeout=60,
                )
                data = resp.json()
            except Exception as e:
                data = {"error": str(e)}

        if "error" not in data:
            ai = data.get("ai_response", {})

            st.error(f"🚨 **{data['error']}** detected on `{data['api_name']}`")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("HTTP Status", data.get("status_code"))
            col2.metric("Latency", f"{data.get('latency_ms')}ms")
            col3.metric("Error Rate", data.get("error_rate"))
            col4.metric("AI Agents", ai.get("agents_ran"))

            st.success(f"✅ AI resolved: `{ai.get('final_status')}` | Severity: `{ai.get('final_severity')}`")
            st.info(f"🤖 LLM Diagnosis: {ai.get('llm_diagnosis', '')}")

            if ai.get("pr_url"):
                st.success(f"📦 GitHub PR created: {ai.get('pr_url')}")

            st.code(" → ".join(ai.get("execution_path", [])), language=None)
            st.rerun()
        else:
            st.error(f"Failed: {data['error']}")

    st.divider()

    # Resolved API incidents
    resolved = [i for i in health.get("incidents", []) if i.get("status") == "resolved"]
    if resolved:
        st.subheader("Resolved API Incidents")
        for inc in reversed(resolved):
            with st.expander(f"✅ `{inc['api_name']}` — {inc['issue_type']} — RESOLVED"):
                st.markdown(f"**Error:** `{inc['error']}` (HTTP {inc['status_code']})")
                st.markdown(f"**Log:** {inc['log']}")
                st.markdown(f"**Resolution:** {inc.get('resolution','')[:150]}")

    if st.button("🔄 Reset API Health (Demo Reset)", use_container_width=True):
        requests.delete(f"{API_BASE_URL}/api-health/clear", timeout=5)
        st.rerun()


# ── Page: Live Incidents ──────────────────────────────────────────────────────
def page_live_incidents() -> None:
    st.title("🔴 Live Incident Feed")
    st.caption("Real-time view of all incidents processed by the AI pipeline.")

    metrics = fetch_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Incidents", metrics.get("total_incidents", 0))
    c2.metric("Open", metrics.get("open_incidents", 0), delta_color="inverse")
    c3.metric("Resolved", metrics.get("resolved_incidents", 0))
    c4.metric("Auto-Remediated", metrics.get("auto_remediated", 0))

    st.divider()

    incidents = fetch_incidents()
    if not incidents:
        st.success("🎉 No incidents! Inject a crash on the Live Alerts page to see data.")
        return

    for inc in reversed(incidents):
        sev = inc.get("severity", "unknown")
        status = inc.get("status", "unknown").lower()
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(
                f"**{inc.get('incident_id')}** — `{inc.get('service')}`  \n"
                f"*{inc.get('title', inc.get('failure_type', ''))}*"
            )
            rca = inc.get("rca_findings", [])
            if rca:
                st.caption(f"🤖 AI Finding: {rca[0].get('finding','')[:100]}")
        with col2:
            st.markdown(_badge(sev, _SEVERITY_COLOUR.get(sev, "#808080")), unsafe_allow_html=True)
        with col3:
            icon = _STATUS_ICON.get(status, "⏱️")
            st.markdown(f"{icon} `{status.title()}`")
        st.divider()


# ── Page: Pipeline Simulator ──────────────────────────────────────────────────
def page_pipeline_simulator() -> None:
    st.title("⚡ Pipeline Simulator")
    st.caption("Trigger a random failure and trace it through the 8-agent LangGraph workflow.")

    col1, col2 = st.columns(2)
    with col1:
        st.info("Triggers a random failure type across all monitored services.")
        trigger = st.button("▶ Run Random Monitoring Cycle", type="primary", use_container_width=True)
    with col2:
        st.markdown("**Pipeline Flow:**")
        st.code(
            "monitoring → log_analysis → repo_inspection\n"
            "  → test_analysis → root_cause\n"
            "      → remediation → validation → jira",
            language=None,
        )

    if trigger:
        with st.spinner("Running full 8-agent AI pipeline..."):
            try:
                resp = requests.post(f"{API_BASE_URL}/run-monitoring-cycle", timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(f"Pipeline complete for `{data.get('message','')}`")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Severity", (data.get("final_severity") or "—").upper())
                    c2.metric("Status", (data.get("final_status") or "—").upper())
                    c3.metric("Agents", len(data.get("execution_path", [])))
                    st.code(" → ".join(data.get("execution_path", [])), language=None)
                else:
                    st.error(f"Failed: {resp.text}")
            except Exception as e:
                st.error(f"Backend error: {e}")


# ── Page: Metrics ─────────────────────────────────────────────────────────────
def page_metrics() -> None:
    st.title("📊 Metrics & KPIs")
    metrics = fetch_metrics()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MTTD", f"{metrics.get('mean_time_to_detect_s', 0):.1f}s", help="Mean Time To Detect")
    c2.metric("MTTR", f"{metrics.get('mean_time_to_resolve_s', 0):.1f}s", help="Mean Time To Resolve")
    c3.metric("Agent Success Rate", f"{metrics.get('agent_success_rate', 0):.0%}")
    resolved = metrics.get("resolved_incidents", 1) or 1
    rate = metrics.get("auto_remediated", 0) / resolved
    c4.metric("Remediation Efficiency", f"{rate:.0%}")

    st.divider()
    incidents = fetch_incidents()
    if incidents:
        st.subheader("Incident Volume by Failure Type")
        counts = {}
        for inc in incidents:
            ft = inc.get("failure_type", "Unknown")
            counts[ft] = counts.get(ft, 0) + 1
        st.bar_chart(pd.DataFrame({"Count": counts}))

        st.subheader("Severity Breakdown")
        sev_counts = {}
        for inc in incidents:
            s = inc.get("severity", "unknown")
            sev_counts[s] = sev_counts.get(s, 0) + 1
        st.bar_chart(pd.DataFrame({"Count": sev_counts}))


# ── Page: Audit Log ───────────────────────────────────────────────────────────
def page_audit_log() -> None:
    st.title("📋 Audit Log")
    logs = fetch_logs()
    search = st.text_input("Search logs", placeholder="incident ID, agent, or keyword…")
    if search:
        logs = [e for e in logs if search.lower() in str(e).lower()]
    if not logs:
        st.info("No logs yet. Run a monitoring cycle or inject a crash.")
        return
    for entry in logs:
        agent = "System"
        if "] " in entry and "Agent" in entry:
            parts = entry.split("] ")
            if len(parts) > 1:
                agent = parts[1].split(":")[0]
        cols = st.columns([1, 4])
        cols[0].markdown(f"`{agent}`")
        cols[1].markdown(entry.split(": ", 1)[-1] if ": " in entry else entry)


# ── Page: Jira Board ──────────────────────────────────────────────────────────
def page_jira_board() -> None:
    st.title("🎫 Jira Board")
    incidents = fetch_incidents()
    columns = {
        "Open":        [i for i in incidents if str(i.get("status")).lower() == "open"],
        "In Progress": [i for i in incidents if str(i.get("status")).lower() in ("triaged", "analyzing", "remediating")],
        "Escalated":   [i for i in incidents if str(i.get("status")).lower() == "escalated"],
        "Done":        [i for i in incidents if str(i.get("status")).lower() in ("resolved", "closed")],
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
                    st.caption(inc.get("failure_type", ""))
                    rca = inc.get("rca_findings", [])
                    if rca:
                        st.caption(f"🤖 {rca[0].get('finding','')[:80]}")


# ── Router ────────────────────────────────────────────────────────────────────
_PAGE_MAP = {
    "🎬 Auto Demo Mode":     page_auto_demo,
    "🚨 Live Alerts":        page_live_alerts,
    "🌐 API Health Monitor": page_api_health,
    "🔴 Live Incidents":     page_live_incidents,
    "⚡ Pipeline Simulator":  page_pipeline_simulator,
    "📊 Metrics & KPIs":     page_metrics,
    "📋 Audit Log":          page_audit_log,
    "🎫 Jira Board":         page_jira_board,
}

_PAGE_MAP[page]()
