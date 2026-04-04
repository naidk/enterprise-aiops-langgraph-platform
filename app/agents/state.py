"""
LangGraph state definition for the AIOps agent pipeline.

AIOpsState is a TypedDict that flows through every node in the graph.
Fields annotated with `operator.add` are *accumulative* — node outputs
are appended rather than replaced, so notes and path entries from every
node are preserved in the final state.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AIOpsState(TypedDict):
    """
    Shared state flowing through the LangGraph AIOps pipeline.

    Lifecycle:
        START → ingest → triage → [router] → rca? → remediation? → finalize → END
    """

    # ── Inputs (set at pipeline entry) ────────────────────────────────────────
    incident_id: str
    alert: dict                  # Alert serialised to dict for graph compatibility
    environment: str

    # ── Triage outputs ────────────────────────────────────────────────────────
    severity: str                # Severity enum value
    affected_service: str
    summary: str

    # ── Routing ───────────────────────────────────────────────────────────────
    route: str                   # "deep_rca" | "standard_rca" | "direct_remediate" | "auto_close"

    # ── RCA outputs ───────────────────────────────────────────────────────────
    rca_findings: list[dict]     # List of RCAFinding dicts

    # ── Remediation outputs ───────────────────────────────────────────────────
    remediation_steps: list[dict]  # List of RemediationStep dicts

    # ── Status ────────────────────────────────────────────────────────────────
    status: str                  # IncidentStatus enum value

    # ── Accumulating fields (operator.add = list concatenation) ───────────────
    agent_notes: Annotated[list[str], operator.add]
    execution_path: Annotated[list[str], operator.add]
