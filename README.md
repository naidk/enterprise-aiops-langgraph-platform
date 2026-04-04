# Enterprise AIOps Platform 🛡️

Our modern infrastructure scales rapidly, but the ability to actively identify, classify, and remediate production outages does not. Operations teams continuously face alert fatigue, heavily manual runbooks, disjointed troubleshooting toolchains, and delayed mean-time-to-recovery (MTTR) as service endpoints fail over the weekend.

The **Enterprise AIOps Platform** solves this using advanced agentic orchestration. 

We utilize a Multi-Agent architecture driven by **LangGraph** to deploy completely autonomous engineering runbooks. When a system anomaly occurs, our platform detects it, spins up isolated containerized agents to analyze server logs, classifies the severity, automatically generates the fix, validates the recovery, and issues Jira tickets to DevOps engineers without human supervision.

---

## 💼 The Business Problem
1. **Downtime Costs Reputation**: Every minute an API Gateway is down, customer workflows freeze.
2. **Alert Fatigue**: Ops Engineers drown in "P99 Latency High" monitor alerts with zero Root Cause context.
3. **Reactive vs Proactive**: Most ops teams triage an incident *after* it begins escalating, forcing frantic searches across Datadog, Jira, and Kubernetes logs.

### The Business Value
Instead of paging a developer at 3 AM for a known Redis cache exhaustion, the AIOps platform dynamically acts as Level 1 and Level 2 support. It:
* Shrinks **MTTD** (Mean Time To Detect) to milliseconds.
* Drastically decreases **MTTR** (Mean Time To Recovery) using automated safe API rollbacks.
* Generates pristine Root Case Analysis post-mortems for compliance auditing before the team even wakes up.

---

## 🧠 Architecture Explanation

The backend operates on a decoupled RESTful layout built on Python 3.11:
-   **API Framework**: FastAPI endpoints governing system state.
-   **Agent Orchestration**: LangGraph driving stateful Multi-Agent transitions.
-   **Frontend Board**: Streamlit Web UI pulling dynamic metrics.
-   **Persistence**: Headless JSON stores for raw mock tracking.

### 🕸️ LangGraph Multi-Agent Flow

The lifecycle of an incident spins through up to 6 distinct agent roles via LangGraph cyclic routing:
1. **Monitoring Agent**: Ingests payloads, filters out noise, confirms an active service issue.
2. **Log Analysis Agent**: Searches local logs recursively for `OOMKilled` or `Query Timeout` patterns.
3. **Incident Classifier**: Maps the incident. High-priority issues are marked `CRITICAL` allowing for immediate Escalation.
4. **Remediation Agent**: Pulls dynamic runbook code and simulates the execution (e.g. restarts DB).
5. **Validation Agent**: Re-queries the health endpoint. If it fails, loops back to Remediation.
6. **Jira Reporting Agent**: Takes the full execution history and constructs an immutable audit log Jira Ticket.

---

## 📁 Folder Structure

```
enterprise-aiops-langgraph-platform/
│
├── agents/             # The standalone LangGraph Agent logic
├── app/                # Core FastAPI Server & Schema configuration
├── dashboard/          # Streamlit UI
├── graph/              # LangGraph Router logic mapping execution paths
├── services/           # Backend persistence classes
├── storage/            # Local JSON Data Mount point
├── tests/              # 100% End-to-End Pytest execution suites
│
├── .env.example        # Configuration hooks
├── requirements.txt    # Frozen Python Dependencies
└── Dockerfile          # Scalable Native Container
```

---

## 🚀 Setup Steps

**1. Clone and Configure**
```bash
git clone https://github.com/organization/enterprise-aiops-langgraph-platform.git
cd enterprise-aiops-langgraph-platform
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**2. Hydrate Environment**
```bash
pip install -r requirements.txt
cp .env.example .env
```

---

## 💻 Running the Platform

This is a distributed architecture. Open two separate terminal windows inside your Virtual Environment to trace both stacks!

**1. Run the FastAPI Backend:**
```bash
uvicorn app.main:app --port 8000
```
*(Optionally view the backend Swagger UI at http://localhost:8000/docs)*

**2. Run the Command Dashboard:**
```bash
streamlit run dashboard/streamlit_app.py
```

**3. Run the complete Pytest Suite**
```bash
pytest tests/ -v
```

---

## 🎭 Demo Scenarios

Once both servers are running, access the Streamlit Dashboard at `http://localhost:8501`.
Navigate to the **⚡ Pipeline Simulator** tab. You can execute multiple different edge cases:
- Select **Database Connection Failure** to watch the system map to a Severity-Critical threshold, bypassing remediation for safety protocols and mapping straight to a red Jira Ticket.
- Select **High Latency** to trace a successful safe-remediation runbook that auto-recovers the network.

Jump over to the **📋 Audit Log** tab afterwards to watch the immutable Langgraph Agent logic trail tracking every LLM reasoning string!

---

## 🔮 Future Enhancements
*   Add Slack Webhook bindings inside the Jira Agent.
*   Swap `LLM_PROVIDER=mock` inside `.env` to `anthropic` and wire dynamic LLM payload generation for `incident_classifier_agent`.
*   Convert the persistence format from `json` to an asynchronous SQLite relational layer.
