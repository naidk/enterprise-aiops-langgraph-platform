"""
LangGraph workflow — assembles all eight agents into the Stage 3 AIOps pipeline.

Graph topology:

    START
      │
    monitoring_agent         ← detect & confirm failure event
      │
    log_analysis_agent       ← parse logs, extract error patterns
      │
    repo_inspection_agent    ← [NEW] identify module bugs/config issues
      │
    test_analysis_agent      ← [NEW] scan/run tests for affected modules
      │
    root_cause_agent         ← [NEW] aggregate signals, diagnose core issue
      │
    [router]                 ← conditional logic
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
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.jira_reporting_agent import jira_reporting_agent
from agents.log_analysis_agent import log_analysis_agent
from agents.monitoring_agent import monitoring_agent
from agents.remediation_agent import remediation_agent
from agents.validation_agent import validation_agent
from agents.repo_inspection_agent import repo_inspection_agent
from agents.test_analysis_agent import test_analysis_agent
from agents.root_cause_agent import root_cause_agent
from app.state import AIOpsWorkflowState
from graph.router import route_after_rca, route_after_validation

logger = logging.getLogger(__name__)


def build_aiops_graph() -> StateGraph:
    """
    Construct the AIOps StateGraph with Stage 3 agents.
    """
    builder = StateGraph(AIOpsWorkflowState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("monitoring_agent",          monitoring_agent)
    builder.add_node("log_analysis_agent",        log_analysis_agent)
    builder.add_node("repo_inspection_agent",     repo_inspection_agent)
    builder.add_node("test_analysis_agent",       test_analysis_agent)
    builder.add_node("root_cause_agent",          root_cause_agent)
    builder.add_node("remediation_agent",         remediation_agent)
    builder.add_node("validation_agent",          validation_agent)
    builder.add_node("jira_reporting_agent",      jira_reporting_agent)

    # ── Linear edges ──────────────────────────────────────────────────────────
    builder.add_edge(START,                       "monitoring_agent")
    builder.add_edge("monitoring_agent",          "log_analysis_agent")
    builder.add_edge("log_analysis_agent",        "repo_inspection_agent")
    builder.add_edge("repo_inspection_agent",     "test_analysis_agent")
    builder.add_edge("test_analysis_agent",       "root_cause_agent")

    # ── Conditional routing after RCA ─────────────────────────────────────────
    builder.add_conditional_edges(
        "root_cause_agent",
        route_after_rca,
        {
            "remediation_agent":    "remediation_agent",
            "jira_reporting_agent": "jira_reporting_agent",   # escalation bypass
        },
    )

    builder.add_edge("remediation_agent",   "validation_agent")
    
    # ── Validation loopback routing ──────────────────────────────────────────
    builder.add_conditional_edges(
        "validation_agent",
        route_after_validation,
        {
            "remediation_agent":    "remediation_agent",
            "jira_reporting_agent": "jira_reporting_agent",
        },
    )

    builder.add_edge("jira_reporting_agent", END)

    logger.debug("AIOps Stage 3 graph topology built successfully.")
    return builder


# ── Compiled Singleton ────────────────────────────────────────────────────────
_checkpointer = MemorySaver()
aiops_graph = build_aiops_graph().compile(checkpointer=_checkpointer)

logger.info("AIOps LangGraph pipeline (Stage 3) compiled. Nodes: %s", list(aiops_graph.nodes.keys()))
