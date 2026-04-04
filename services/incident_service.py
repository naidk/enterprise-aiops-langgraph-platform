"""
Incident Service.

Provides CRUD operations for Incident records, backed by JSON file storage.
This is the system of record for all incidents and their lifecycle state.

Stage 2 will:
    - Replace JSON with SQLite (via aiosqlite) or PostgreSQL (via asyncpg)
    - Add full-text search over incident summaries and RCA findings
    - Implement pagination, filtering, and sorting
    - Add incident correlation (linking related incidents)
    - Expose an event bus (or LangGraph channel) for real-time incident updates
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.schemas import Incident, IncidentStatus

logger = logging.getLogger(__name__)


class IncidentService:
    """
    JSON-backed incident store.

    All methods operate synchronously in Stage 1.
    Stage 2 will add async variants for FastAPI integration.

    Usage:
        svc = IncidentService(storage_path="storage/incidents.json")
        incident = svc.create(Incident(...))
        incidents = svc.list_all(status=IncidentStatus.OPEN)
    """

    def __init__(self, storage_path: str = "storage/incidents.json") -> None:
        self._path = Path(storage_path)
        self._ensure_file()
        logger.info("IncidentService initialised — storage: %s", self._path)

    # ── Storage helpers ────────────────────────────────────────────────────────

    def _ensure_file(self) -> None:
        """Create the storage file with an empty list if it doesn't exist."""
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load incidents: %s", exc)
            return []

    def _save(self, records: list[dict]) -> None:
        try:
            self._path.write_text(
                json.dumps(records, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Failed to save incidents: %s", exc)

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def create(self, incident: Incident) -> Incident:
        """Persist a new incident record. Returns the saved incident."""
        records = self._load()
        records.append(incident.model_dump(mode="json"))
        self._save(records)
        logger.info("IncidentService: created %s (%s)", incident.incident_id, incident.severity)
        return incident

    def get(self, incident_id: str) -> Optional[Incident]:
        """Retrieve a single incident by ID. Returns None if not found."""
        for record in self._load():
            if record.get("incident_id") == incident_id:
                return Incident(**record)
        return None

    def update(self, incident: Incident) -> Incident:
        """Update an existing incident record. Raises ValueError if not found."""
        records = self._load()
        for i, record in enumerate(records):
            if record.get("incident_id") == incident.incident_id:
                incident.updated_at = datetime.now(timezone.utc)
                records[i] = incident.model_dump(mode="json")
                self._save(records)
                logger.info("IncidentService: updated %s → %s", incident.incident_id, incident.status)
                return incident
        raise ValueError(f"Incident {incident.incident_id!r} not found")

    def delete(self, incident_id: str) -> bool:
        """Delete an incident by ID. Returns True if deleted, False if not found."""
        records = self._load()
        new_records = [r for r in records if r.get("incident_id") != incident_id]
        if len(new_records) == len(records):
            return False
        self._save(new_records)
        logger.info("IncidentService: deleted %s", incident_id)
        return True

    # ── Queries ────────────────────────────────────────────────────────────────

    def list_all(
        self,
        status: Optional[IncidentStatus] = None,
        service: Optional[str] = None,
        limit: int = 100,
    ) -> list[Incident]:
        """
        List incidents with optional filters.

        Args:
            status:  Filter by IncidentStatus.
            service: Filter by service name.
            limit:   Max records to return.

        TODO Stage 2: push filtering to SQL WHERE clause.
        """
        records = self._load()
        incidents: list[Incident] = []

        for record in records[:limit]:
            if status and record.get("status") != status.value:
                continue
            if service and record.get("service") != service:
                continue
            try:
                incidents.append(Incident(**record))
            except Exception as exc:
                logger.warning("Skipping malformed incident record: %s", exc)

        return incidents

    def count(self, status: Optional[IncidentStatus] = None) -> int:
        """Count incidents, optionally filtered by status."""
        return len(self.list_all(status=status, limit=10_000))

    def resolve(self, incident_id: str, resolution_summary: str = "") -> Incident:
        """Mark an incident as RESOLVED with timestamp and optional summary."""
        incident = self.get(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id!r} not found")
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        if resolution_summary:
            incident.audit_trail.append(f"RESOLVED: {resolution_summary}")
        return self.update(incident)
