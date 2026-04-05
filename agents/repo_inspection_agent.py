"""
Repo Inspection Agent — identifies file-level issues in the repository.

Responsibility:
    - Inspect project folders and files (simulated).
    - Detect broken imports, configuration mismatches, and dependency issues using LLM.
    - Map log errors to specific modules and lines of code.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas import RepoFinding, FailureType
from app.state import AIOpsWorkflowState
from app.llm_factory import get_llm
from app.config import settings

logger = logging.getLogger(__name__)


def repo_inspection_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Repo Inspection Agent.

    Analyses the repository structure using real LLM inference if enabled.
    Also checks recent commits to identify if a developer commit caused the crash.
    """
    incident_id = state["incident_id"]
    service = state["service"]
    failure_type = state["failure_type"]
    log_entries = state.get("log_entries", [])
    raw_event = state.get("raw_event", {})

    logger.info("RepoInspectionAgent: inspecting repository for %s (LLM: %s)", service, settings.llm_provider)

    # Check if this crash was triggered by a recent commit
    recent_commit = raw_event.get("triggered_by_commit")
    commit_info = ""
    if recent_commit:
        commit_info = (
            f"\nRecent commit detected: [{recent_commit.get('commit_hash','unknown')[:7]}] "
            f"by {recent_commit.get('author','unknown')} — '{recent_commit.get('message','no message')}'"
        )
        logger.info("RepoInspectionAgent: crash linked to commit %s by %s",
                    recent_commit.get("commit_hash", "")[:7], recent_commit.get("author", ""))

    findings: list[RepoFinding] = []

    if settings.using_real_llm:
        findings = _llm_repo_inspection(service, log_entries, commit_info)
        if not findings:
            logger.info("RepoInspectionAgent: LLM returned no findings; using simulation fallback.")
            findings = _simulate_repo_inspection(service, failure_type, recent_commit)
    else:
        findings = _simulate_repo_inspection(service, failure_type, recent_commit)

    note = f"RepoInspectionAgent: identified {len(findings)} repository findings via {settings.llm_provider}.{commit_info}"
    audit = f"[{incident_id}] RepoInspectionAgent: inspected {service}. Findings: {len(findings)}{commit_info}"

    return {
        "repo_findings": [f.model_dump(mode="json") for f in findings],
        "agent_notes": [note],
        "audit_trail": [audit],
        "execution_path": ["repo_inspection_agent"],
    }


def _llm_repo_inspection(service: str, logs: list[dict[str, Any]], commit_info: str = "") -> list[RepoFinding]:
    """Use LLM to predict potential file-level issues based on logs."""
    try:
        llm = get_llm()
        
        prompt = (
            f"You are an SRE Expert. Based on these logs from service '{service}', "
            "predict which file in the repository likely has an issue and what the issue is. "
            f"{commit_info}\n"
            "Identify if the recent commit likely caused this crash. "
            "Return a concise finding with the file path and issue description.\n"
            "Logs:\n" + "\n".join(l.get('message', '') for l in logs[:5])
        )
        
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        
        # For the demo, we create a structured finding from the LLM's text
        return [RepoFinding(
            file_path=f"app/services/{service}_service.py",
            issue_type="code_anomaly",
            description=content[:200], # Analysis from LLM
            severity="high",
            module=service
        )]
    except Exception as e:
        logger.error("RepoInspectionAgent: LLM analysis failed: %s", e)
        return []


def _simulate_repo_inspection(service: str, failure_type: str, recent_commit: dict | None = None) -> list[RepoFinding]:
    """Fallback simulation logic (Stage 3 logic)"""
    findings: list[RepoFinding] = []

    # If a recent commit triggered this crash, link it
    if recent_commit:
        author = recent_commit.get("author", "unknown developer")
        commit_hash = recent_commit.get("commit_hash", "unknown")[:7]
        message = recent_commit.get("message", "no message")
        changed_file = recent_commit.get("changed_file", f"app/services/{service.replace('-','_')}_service.py")
        findings.append(RepoFinding(
            file_path=changed_file,
            issue_type="commit_induced_crash",
            description=(
                f"Commit [{commit_hash}] by {author} — '{message}' — "
                f"introduced a breaking change in {changed_file}. "
                f"Recommend: rollback this commit and notify {author}."
            ),
            severity="critical",
            module=service
        ))
        return findings

    if failure_type == FailureType.REPO_BUG.value:
        findings.append(RepoFinding(
            file_path=f"app/services/{service.replace('-', '_')}_service.py",
            issue_type="broken_import",
            description="ImportError: cannot import name 'LegacyClient' from 'app.clients'",
            severity="high",
            module=service
        ))
    elif failure_type == FailureType.SERVICE_CRASH.value:
        findings.append(RepoFinding(
            file_path="app/config.py",
            issue_type="missing_env_var",
            description=f"Environment variable '{service.upper()}_API_KEY' is not set",
            severity="critical",
            module="config"
        ))
    return findings
