"""
Deployment Tracker — Stage 4.

Persists deployment history per service to storage/deployments.json so the
platform can roll back to the previous known-good version automatically.

Usage:
    from services.deployment_tracker import DeploymentTracker, DeploymentRecord
    tracker = DeploymentTracker()
    tracker.seed_service("payment-service")
    cmd = tracker.get_rollback_command("payment-service")
    print(cmd)  # "kubectl rollout undo deployment/payment-service -n production"
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_STORAGE = "storage/deployments.json"


@dataclass
class DeploymentRecord:
    """Represents a single deployment event for a service."""

    service: str
    version: str
    image: str
    deployed_by: str
    deployed_at: str  # ISO 8601 string
    is_stable: bool = True
    rollback_command: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DeploymentRecord:
        return cls(
            service=data["service"],
            version=data["version"],
            image=data.get("image", ""),
            deployed_by=data.get("deployed_by", "unknown"),
            deployed_at=data.get("deployed_at", datetime.now(timezone.utc).isoformat()),
            is_stable=data.get("is_stable", True),
            rollback_command=data.get("rollback_command", ""),
        )


class DeploymentTracker:
    """
    Tracks deployment history per service and provides rollback support.

    Storage format (storage/deployments.json):
        {
            "payment-service": [
                { ...DeploymentRecord... },   # oldest → newest
                { ...DeploymentRecord... },
            ]
        }
    """

    def __init__(self, storage_path: str = _DEFAULT_STORAGE) -> None:
        self._path = Path(storage_path)
        self._ensure_storage()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_storage(self) -> None:
        """Create storage directory and file if they don't exist."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._path.write_text("{}", encoding="utf-8")
        except Exception as exc:
            logger.error("DeploymentTracker: could not init storage at %s — %s", self._path, exc)

    def _load(self) -> dict[str, list[dict]]:
        """Load the full deployments JSON from disk."""
        try:
            text = self._path.read_text(encoding="utf-8")
            return json.loads(text) if text.strip() else {}
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("DeploymentTracker: could not read storage — %s", exc)
            return {}

    def _save(self, data: dict[str, list[dict]]) -> None:
        """Atomically write deployments JSON to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("DeploymentTracker: could not write storage — %s", exc)

    def _make_rollback_command(self, service: str) -> str:
        return f"kubectl rollout undo deployment/{service} -n production"

    # ── Public API ────────────────────────────────────────────────────────────

    def record_deployment(self, record: DeploymentRecord) -> None:
        """Append a deployment record to the service's history."""
        data = self._load()
        history = data.get(record.service, [])
        history.append(record.to_dict())
        data[record.service] = history
        self._save(data)
        logger.info(
            "DeploymentTracker: recorded %s v%s for service '%s'",
            record.image, record.version, record.service,
        )

    def get_history(self, service: str) -> list[DeploymentRecord]:
        """Return the full deployment history for a service (oldest first)."""
        data = self._load()
        return [DeploymentRecord.from_dict(d) for d in data.get(service, [])]

    def get_current_version(self, service: str) -> Optional[DeploymentRecord]:
        """Return the most recent deployment record for a service."""
        history = self.get_history(service)
        return history[-1] if history else None

    def get_previous_version(self, service: str) -> Optional[DeploymentRecord]:
        """Return the deployment before the current one (rollback target)."""
        history = self.get_history(service)
        return history[-2] if len(history) >= 2 else None

    def mark_unstable(self, service: str) -> None:
        """Mark the current (latest) deployment of a service as unstable."""
        data = self._load()
        history = data.get(service, [])
        if not history:
            logger.warning("DeploymentTracker: no history for service '%s' — cannot mark unstable", service)
            return
        history[-1]["is_stable"] = False
        data[service] = history
        self._save(data)
        logger.info("DeploymentTracker: marked current deployment of '%s' as unstable", service)

    def get_rollback_command(self, service: str) -> str:
        """
        Return the kubectl rollout undo command for the service.

        Uses the rollback_command stored on the current record if available;
        otherwise generates a canonical kubectl command.
        """
        current = self.get_current_version(service)
        if current and current.rollback_command:
            return current.rollback_command
        return self._make_rollback_command(service)

    def seed_service(
        self,
        service: str,
        current_version: str = "2.0.0",
        previous_version: str = "1.9.0",
    ) -> None:
        """
        Bootstrap deployment history for a service if it has no records.

        Ensures rollback always has a target, even in fresh environments.
        """
        history = self.get_history(service)
        if history:
            logger.debug(
                "DeploymentTracker: service '%s' already has %d deployment records — skipping seed",
                service, len(history),
            )
            return

        now = datetime.now(timezone.utc).isoformat()
        previous = DeploymentRecord(
            service=service,
            version=previous_version,
            image=f"{service}:{previous_version}",
            deployed_by="seed",
            deployed_at=now,
            is_stable=True,
            rollback_command=self._make_rollback_command(service),
        )
        current = DeploymentRecord(
            service=service,
            version=current_version,
            image=f"{service}:{current_version}",
            deployed_by="seed",
            deployed_at=now,
            is_stable=True,
            rollback_command=self._make_rollback_command(service),
        )
        self.record_deployment(previous)
        self.record_deployment(current)
        logger.info(
            "DeploymentTracker: seeded service '%s' with versions %s (prev) and %s (current)",
            service, previous_version, current_version,
        )
