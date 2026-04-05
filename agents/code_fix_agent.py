"""
Code Fix Agent — reads real source code, uses LLM to generate a fix, creates GitHub PR.

Responsibility:
    - Read the actual failing file from the repository
    - Send file content + error to Groq LLM
    - LLM generates a targeted code fix
    - Create a GitHub Pull Request with the fix
    - Developer reviews and approves — no auto-merge in production
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from app.state import AIOpsWorkflowState
from app.llm_factory import get_llm
from app.config import settings

logger = logging.getLogger(__name__)


def code_fix_agent(state: AIOpsWorkflowState) -> dict[str, Any]:
    """
    LangGraph node: Code Fix Agent.

    Reads real source code, asks LLM to fix it, creates a GitHub PR.
    """
    incident_id  = state["incident_id"]
    service      = state["service"]
    failure_type = state["failure_type"]
    repo_findings = state.get("repo_findings", [])
    rca_findings  = state.get("rca_findings", [])
    log_entries   = state.get("log_entries", [])
    raw_event     = state.get("raw_event", {})

    logger.info("CodeFixAgent: starting code analysis for %s", service)

    # ── 1. Identify which file to fix ─────────────────────────────────────────
    target_file = None
    for rf in repo_findings:
        fp = rf.get("file_path", "")
        if fp:
            target_file = fp
            break

    # Fallback: derive from service name
    if not target_file:
        svc = service.replace("-", "_")
        target_file = f"app/services/{svc}_service.py"

    # ── 2. Read the actual file content ───────────────────────────────────────
    file_content = _read_file(target_file)

    # ── 3. Build error context for LLM ────────────────────────────────────────
    error_context = _build_error_context(
        service=service,
        failure_type=failure_type,
        log_entries=log_entries,
        rca_findings=rca_findings,
        raw_event=raw_event,
    )

    # ── 4. LLM generates the fix ──────────────────────────────────────────────
    fix_result = _llm_generate_fix(
        service=service,
        target_file=target_file,
        file_content=file_content,
        error_context=error_context,
    )

    # ── 5. Create GitHub PR ───────────────────────────────────────────────────
    pr_url = None
    pr_status = "skipped"
    github_token = os.getenv("GITHUB_TOKEN", "")
    github_repo  = os.getenv("GITHUB_REPO", "naidk/enterprise-aiops-langgraph-platform")

    if github_token and fix_result.get("fixed_code") and fix_result.get("has_real_fix"):
        pr_url, pr_status = _create_github_pr(
            token=github_token,
            repo=github_repo,
            target_file=target_file,
            fixed_code=fix_result["fixed_code"],
            fix_description=fix_result["description"],
            incident_id=incident_id,
            service=service,
        )
    elif not github_token:
        pr_status = "skipped — GITHUB_TOKEN not set (add to .env to enable auto-PR)"
        logger.info("CodeFixAgent: GITHUB_TOKEN not set — PR creation skipped")

    # ── 6. Build result ───────────────────────────────────────────────────────
    note = (
        f"CodeFixAgent: analysed '{target_file}' — "
        f"LLM fix generated={fix_result.get('has_real_fix', False)}, "
        f"PR={pr_status}"
    )
    audit = (
        f"[{incident_id}] CodeFixAgent: file={target_file}, "
        f"pr_status={pr_status}, pr_url={pr_url or 'none'}"
    )

    return {
        "code_fix": {
            "target_file":   target_file,
            "error_context": error_context[:300],
            "llm_fix":       fix_result.get("description", ""),
            "fixed_code":    fix_result.get("fixed_code", ""),
            "has_real_fix":  fix_result.get("has_real_fix", False),
            "pr_url":        pr_url,
            "pr_status":     pr_status,
        },
        "agent_notes":    [note],
        "audit_trail":    [audit],
        "execution_path": ["code_fix_agent"],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_file(file_path: str) -> str:
    """Read file from local repo. Returns empty string if not found."""
    try:
        p = os.path.join(os.getcwd(), file_path.lstrip("/"))
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info("CodeFixAgent: read %d chars from %s", len(content), file_path)
            return content
    except Exception as e:
        logger.warning("CodeFixAgent: could not read %s — %s", file_path, e)
    return f"# File not found locally: {file_path}\n# LLM will generate fix based on error context only"


def _build_error_context(
    service: str,
    failure_type: str,
    log_entries: list,
    rca_findings: list,
    raw_event: dict,
) -> str:
    """Build a concise error context string for the LLM."""
    parts = [f"Service: {service}", f"Failure Type: {failure_type}"]

    # Add real crash logs if available
    injected = raw_event.get("real_logs", "")
    if injected:
        parts.append(f"Real Crash Logs:\n{injected[:600]}")
    elif log_entries:
        msgs = [e.get("message", "") for e in log_entries[:3] if isinstance(e, dict)]
        parts.append("Log Entries:\n" + "\n".join(msgs))

    # Add LLM RCA finding
    if rca_findings:
        first = rca_findings[0]
        finding = first.get("finding", "") if isinstance(first, dict) else ""
        if finding:
            parts.append(f"Root Cause Analysis:\n{finding[:300]}")

    # Add commit info if available
    commit = raw_event.get("triggered_by_commit", {})
    if commit:
        parts.append(
            f"Triggered by commit [{commit.get('commit_hash','')[:7]}] "
            f"by {commit.get('author','unknown')}: '{commit.get('message','')}'"
        )

    return "\n\n".join(parts)


def _llm_generate_fix(
    service: str,
    target_file: str,
    file_content: str,
    error_context: str,
) -> dict[str, Any]:
    """Ask LLM to generate a code fix."""
    if not settings.using_real_llm:
        return {
            "description": f"[Mock] Add null checks in {target_file} to prevent NullPointerException.",
            "fixed_code": "",
            "has_real_fix": False,
        }

    try:
        llm = get_llm()

        prompt = f"""You are a senior software engineer debugging a production crash.

ERROR CONTEXT:
{error_context}

FILE TO FIX: {target_file}
CURRENT CODE:
```python
{file_content[:2000]}
```

TASK:
1. Identify the exact bug causing this crash
2. Write a minimal, targeted fix (only change what's needed)
3. Explain what was wrong and what you fixed

Respond in this format:
BUG: <one sentence describing the bug>
FIX: <one sentence describing the fix>
CODE:
```python
<the fixed code here>
```
"""
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Extract fixed code from response
        fixed_code = ""
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1).strip()

        # Extract description
        description = content.split("CODE:")[0].strip() if "CODE:" in content else content[:300]

        has_real_fix = bool(fixed_code and len(fixed_code) > 50)

        logger.info(
            "CodeFixAgent: LLM generated fix for %s — has_code=%s, length=%d",
            target_file, has_real_fix, len(fixed_code)
        )

        return {
            "description": description,
            "fixed_code":  fixed_code,
            "has_real_fix": has_real_fix,
        }

    except Exception as e:
        logger.error("CodeFixAgent: LLM fix generation failed: %s", e)
        return {
            "description": f"LLM fix generation failed: {e}",
            "fixed_code":  "",
            "has_real_fix": False,
        }


def _create_github_pr(
    token: str,
    repo: str,
    target_file: str,
    fixed_code: str,
    fix_description: str,
    incident_id: str,
    service: str,
) -> tuple[str | None, str]:
    """Create a GitHub PR with the LLM-generated fix."""
    try:
        import base64
        import requests as req
        import uuid

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        base_url = f"https://api.github.com/repos/{repo}"

        # Get default branch SHA
        branch_resp = req.get(f"{base_url}/git/refs/heads/main", headers=headers, timeout=10)
        if branch_resp.status_code != 200:
            return None, f"failed to get branch SHA: {branch_resp.status_code}"
        sha = branch_resp.json()["object"]["sha"]

        # Create fix branch
        fix_branch = f"aiops-fix/{incident_id.lower()}-{service}"
        br = req.post(f"{base_url}/git/refs", headers=headers, timeout=10, json={
            "ref": f"refs/heads/{fix_branch}",
            "sha": sha,
        })
        if br.status_code not in (200, 201, 422):
            return None, f"failed to create branch: {br.status_code}"

        # Get current file SHA (needed for update)
        file_resp = req.get(
            f"{base_url}/contents/{target_file}",
            headers=headers,
            params={"ref": fix_branch},
            timeout=10,
        )
        file_sha = file_resp.json().get("sha", "") if file_resp.status_code == 200 else ""

        # Commit the fix
        commit_body: dict[str, Any] = {
            "message": f"fix({service}): AI-generated fix for {incident_id}\n\n{fix_description[:200]}",
            "content": base64.b64encode(fixed_code.encode()).decode(),
            "branch": fix_branch,
        }
        if file_sha:
            commit_body["sha"] = file_sha

        update = req.put(
            f"{base_url}/contents/{target_file}",
            headers=headers,
            json=commit_body,
            timeout=10,
        )
        if update.status_code not in (200, 201):
            return None, f"failed to commit fix: {update.status_code}"

        # Create PR
        pr = req.post(f"{base_url}/pulls", headers=headers, timeout=10, json={
            "title": f"[AIOps Fix] {service} — {incident_id}",
            "body": (
                f"## AI-Generated Fix\n\n"
                f"**Incident:** `{incident_id}`\n"
                f"**Service:** `{service}`\n"
                f"**File:** `{target_file}`\n\n"
                f"### What the AI Found\n{fix_description}\n\n"
                f"### Review Checklist\n"
                f"- [ ] Review the fix logic\n"
                f"- [ ] Run tests locally\n"
                f"- [ ] Approve to deploy\n\n"
                f"🤖 Generated by Enterprise AIOps Platform"
            ),
            "head": fix_branch,
            "base": "main",
        })

        if pr.status_code in (200, 201):
            pr_url = pr.json().get("html_url", "")
            logger.info("CodeFixAgent: PR created — %s", pr_url)
            return pr_url, "created"
        else:
            return None, f"PR creation failed: {pr.status_code}"

    except Exception as e:
        logger.error("CodeFixAgent: GitHub PR creation failed: %s", e)
        return None, f"error: {e}"
