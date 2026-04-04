"""
Regression tests — IncidentService persistence layer.

Verifies that the JSON-backed incident store correctly creates, reads,
updates, deletes, and filters incidents across multiple operations.
"""
from __future__ import annotations

import pytest

from app.schemas import FailureType, Incident, IncidentStatus, Severity
from services.incident_service import IncidentService


def _make_incident(**kwargs) -> Incident:
    defaults = {
        "service": "payment-service",
        "severity": Severity.HIGH,
        "status": IncidentStatus.OPEN,
        "failure_type": FailureType.SERVICE_CRASH,
    }
    defaults.update(kwargs)
    return Incident(**defaults)


class TestIncidentServiceCRUD:
    def test_create_returns_incident(self, incident_service: IncidentService) -> None:
        inc = _make_incident()
        saved = incident_service.create(inc)
        assert saved.incident_id == inc.incident_id

    def test_get_returns_saved_incident(self, incident_service: IncidentService) -> None:
        inc = _make_incident()
        incident_service.create(inc)
        fetched = incident_service.get(inc.incident_id)
        assert fetched is not None
        assert fetched.incident_id == inc.incident_id

    def test_get_nonexistent_returns_none(self, incident_service: IncidentService) -> None:
        result = incident_service.get("INC-DOESNOTEXIST")
        assert result is None

    def test_update_modifies_status(self, incident_service: IncidentService) -> None:
        inc = _make_incident()
        incident_service.create(inc)
        inc.status = IncidentStatus.TRIAGED
        incident_service.update(inc)
        fetched = incident_service.get(inc.incident_id)
        assert fetched.status == IncidentStatus.TRIAGED

    def test_update_nonexistent_raises(self, incident_service: IncidentService) -> None:
        inc = _make_incident()
        inc.incident_id = "INC-FAKE9999"
        with pytest.raises(ValueError):
            incident_service.update(inc)

    def test_delete_removes_incident(self, incident_service: IncidentService) -> None:
        inc = _make_incident()
        incident_service.create(inc)
        deleted = incident_service.delete(inc.incident_id)
        assert deleted is True
        assert incident_service.get(inc.incident_id) is None

    def test_delete_nonexistent_returns_false(self, incident_service: IncidentService) -> None:
        assert incident_service.delete("INC-NOPE") is False

    def test_list_all_returns_all_incidents(self, incident_service: IncidentService) -> None:
        for _ in range(3):
            incident_service.create(_make_incident())
        all_incidents = incident_service.list_all()
        assert len(all_incidents) == 3

    def test_list_all_filters_by_status(self, incident_service: IncidentService) -> None:
        open_inc = _make_incident(status=IncidentStatus.OPEN)
        resolved_inc = _make_incident(status=IncidentStatus.RESOLVED)
        incident_service.create(open_inc)
        incident_service.create(resolved_inc)
        open_only = incident_service.list_all(status=IncidentStatus.OPEN)
        assert all(i.status == IncidentStatus.OPEN for i in open_only)
        assert len(open_only) == 1

    def test_resolve_sets_resolved_at(self, incident_service: IncidentService) -> None:
        inc = _make_incident()
        incident_service.create(inc)
        resolved = incident_service.resolve(inc.incident_id, "Issue fixed by rollback")
        assert resolved.status == IncidentStatus.RESOLVED
        assert resolved.resolved_at is not None

    def test_count_returns_correct_number(self, incident_service: IncidentService) -> None:
        for _ in range(4):
            incident_service.create(_make_incident())
        assert incident_service.count() == 4
