"""
LangGraph workflow — assembles all six agents into the AIOps pipeline.

Graph topology:

    START
      │
    monitoring_agent         ← detect & confirm failure event
      │
    log_analysis_agent       ← parse logs, extract RCA findings
      │
    incident_classifier      ← classify severity, decide escalation path
      │
    [router]                 ← conditional branch
     │
     ├─ [escalate=True]  ──────────────────────────────────► jira_reporting
     │
     └─ [escalate=False] ──► remediation_agent
                                     │
                               validation_agent
                                     │
                               jira_reporting_agent
                                     │
                                    END

The compiled graph is exposed as the `aiops_graph` module singleton.
Import it in services, FastAPI routers, and tests.
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.incident_classifier_agent import incident_classifier_agent
from agents.jira_reporting_agent import jira_reporting_agent
from agents.log_analysis_agent import log_analysis_agent
from agents.monitoring_agent import monitoring_agent
from agents.remediation_agent import remediation_agent
from agents.validation_agent import validation_agent
from app.state import AIOpsWorkflowState
from graph.router import route_after_classification

logger = logging.getLogger(__name__)


def build_aiops_graph() -> StateGraph:
    """
    Construct the AIOps StateGraph.

    Returns the builder (not yet compiled) so callers can optionally
    attach custom checkpointers (e.g. SqliteSaver for persistence).
    """
    builder = StateGraph(AIOpsWorkflowState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("monitoring_agent",          monitoring_agent)
    builder.add_node("log_analysis_agent",        log_analysis_agent)
    builder.add_node("incident_classifier_agent", incident_classifier_agent)
    builder.add_node("remediation_agent",         remediation_agent)
    builder.add_node("validation_agent",          validation_agent)
    builder.add_node("jira_reporting_agent",      jira_reporting_agent)

    # ── Linear edges ──────────────────────────────────────────────────────────
    builder.add_edge(START,                       "monitoring_agent")
    builder.add_edge("monitoring_agent",          "log_analysis_agent")
    builder.add_edge("log_analysis_agent",        "incident_classifier_agent")

    # ── Conditional routing after classification ──────────────────────────────
    builder.add_conditional_edges(
        "incident_classifier_agent",
        route_after_classification,
        {
            "remediation_agent":    "remediation_agent",
            "jira_reporting_agent": "jira_reporting_agent",   # escalation bypass
        },
    )

    builder.add_edge("remediation_agent",   "validation_agent")
    builder.add_edge("validation_agent",    "jira_reporting_agent")
    builder.add_edge("jira_reporting_agent", END)

    logger.debug("AIOps graph topology built successfully.")
    return builder


# ── Module-level singleton ────────────────────────────────────────────────────
# MemorySaver: in-memory checkpoint store — each incident run is independently
# replayable by thread_id (= incident_id). For production, swap with:
#   from langgraph.checkpoint.sqlite import SqliteSaver
#   _checkpointer = SqliteSaver.from_conn_string("storage/checkpoints.db")

_checkpointer = MemorySaver()
aiops_graph = build_aiops_graph().compile(checkpointer=_checkpointer)

logger.info("AIOps LangGraph pipeline compiled. Nodes: %s", list(aiops_graph.nodes.keys()))
