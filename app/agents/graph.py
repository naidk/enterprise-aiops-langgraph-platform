"""
LangGraph graph assembly for the AIOps agent pipeline.

Graph topology:

    START
      │
    ingest          ← validate & normalise alert
      │
    triage          ← classify severity, set route
      │
    [router]        ← conditional branch on severity
     ├─► rca        ← correlate metrics, logs, deployments (CRITICAL/HIGH/MEDIUM)
     │     │
     │   remediation ← generate ordered fix plan
     │     │
     └─► finalize   ← set resolution status & summary
           │
          END

The graph is compiled once at module import and reused across all requests.
A MemorySaver checkpointer is attached so that individual pipeline runs
can be inspected or replayed by incident_id (thread_id).
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    finalize_node,
    ingest_node,
    remediation_node,
    rca_node,
    route_by_severity,
    triage_node,
)
from app.agents.state import AIOpsState


def build_aiops_graph() -> StateGraph:
    """Construct and compile the AIOps LangGraph pipeline."""

    builder = StateGraph(AIOpsState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("ingest", ingest_node)
    builder.add_node("triage", triage_node)
    builder.add_node("rca", rca_node)
    builder.add_node("remediation", remediation_node)
    builder.add_node("finalize", finalize_node)

    # ── Wire edges ────────────────────────────────────────────────────────────
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "triage")

    builder.add_conditional_edges(
        "triage",
        route_by_severity,
        {
            "rca": "rca",
            "remediation": "remediation",
            "finalize": "finalize",
        },
    )

    builder.add_edge("rca", "remediation")
    builder.add_edge("remediation", "finalize")
    builder.add_edge("finalize", END)

    return builder


# ── Module-level singleton ────────────────────────────────────────────────────
# MemorySaver keeps a per-thread_id checkpoint so each incident run is
# independently replayable. For production, swap with SqliteSaver or
# a PostgresSaver for persistent cross-process state.

_checkpointer = MemorySaver()
aiops_graph = build_aiops_graph().compile(checkpointer=_checkpointer)
