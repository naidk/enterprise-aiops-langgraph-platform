"""
Circuit Breaker — Stage 4.

Prevents cascading failures by blocking remediation execution when a service
has experienced too many consecutive failures. Automatically transitions to
half-open after a recovery timeout to allow a test execution.

States:
    closed    — normal, execution allowed
    open      — blocked, too many consecutive failures
    half_open — tentatively allowing one test execution after recovery timeout

Usage:
    from services.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker()
    if cb.is_open("payment-service"):
        raise RuntimeError("Circuit breaker open — skipping remediation")
    result = execute_remediation()
    if result.success:
        cb.record_success("payment-service")
    else:
        cb.record_failure("payment-service")
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_STORAGE = "storage/circuit_breakers.json"

_STATE_CLOSED = "closed"
_STATE_OPEN = "open"
_STATE_HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Per-service circuit breaker backed by JSON storage.

    Args:
        storage_path: Path to the circuit breaker state file.
        failure_threshold: Number of consecutive failures before opening the circuit.
        recovery_timeout_minutes: Minutes after opening before auto-transitioning to half_open.
    """

    def __init__(
        self,
        storage_path: str = _DEFAULT_STORAGE,
        failure_threshold: int = 3,
        recovery_timeout_minutes: int = 10,
    ) -> None:
        self._path = Path(storage_path)
        self.failure_threshold = failure_threshold
        self.recovery_timeout_minutes = recovery_timeout_minutes
        self._ensure_storage()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_storage(self) -> None:
        """Create storage directory and file if they don't exist."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._path.write_text("{}", encoding="utf-8")
        except Exception as exc:
            logger.error("CircuitBreaker: could not init storage at %s — %s", self._path, exc)

    def _load(self) -> dict[str, dict]:
        """Load the full circuit breaker state from disk."""
        try:
            text = self._path.read_text(encoding="utf-8")
            return json.loads(text) if text.strip() else {}
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("CircuitBreaker: could not read storage — %s", exc)
            return {}

    def _save(self, data: dict[str, dict]) -> None:
        """Write circuit breaker state to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("CircuitBreaker: could not write storage — %s", exc)

    def _default_entry(self) -> dict:
        return {
            "state": _STATE_CLOSED,
            "consecutive_failures": 0,
            "opened_at": None,
            "last_failure_at": None,
        }

    def _get_entry(self, data: dict, service: str) -> dict:
        """Return the circuit breaker entry for a service, creating default if absent."""
        if service not in data:
            data[service] = self._default_entry()
        return data[service]

    # ── Public API ────────────────────────────────────────────────────────────

    def is_open(self, service: str) -> bool:
        """
        Return True if the circuit breaker should block execution for this service.

        State transitions:
        - open + recovery timeout NOT passed → return True (block)
        - open + recovery timeout passed     → transition to half_open, return False (allow test)
        - closed / half_open                 → return False (allow)
        """
        data = self._load()
        entry = self._get_entry(data, service)
        state = entry.get("state", _STATE_CLOSED)

        if state == _STATE_OPEN:
            opened_at_str: Optional[str] = entry.get("opened_at")
            if opened_at_str:
                try:
                    opened_at = datetime.fromisoformat(opened_at_str)
                    recovery_deadline = opened_at + timedelta(minutes=self.recovery_timeout_minutes)
                    now = datetime.now(timezone.utc)
                    if now >= recovery_deadline:
                        # Transition to half_open — allow one test execution
                        entry["state"] = _STATE_HALF_OPEN
                        data[service] = entry
                        self._save(data)
                        logger.info(
                            "CircuitBreaker: '%s' transitioned OPEN → HALF_OPEN after recovery timeout",
                            service,
                        )
                        return False  # Allow execution to test recovery
                except (ValueError, TypeError):
                    pass  # Bad timestamp — default to blocking
            return True  # Still within recovery timeout — block

        return False  # closed or half_open

    def record_failure(self, service: str) -> None:
        """
        Record a failure for a service.

        Increments consecutive failure count. Opens the circuit if the
        failure threshold is reached.
        """
        data = self._load()
        entry = self._get_entry(data, service)

        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        entry["last_failure_at"] = datetime.now(timezone.utc).isoformat()

        if entry["consecutive_failures"] >= self.failure_threshold:
            if entry.get("state") != _STATE_OPEN:
                entry["state"] = _STATE_OPEN
                entry["opened_at"] = datetime.now(timezone.utc).isoformat()
                logger.warning(
                    "CircuitBreaker: OPENED for service '%s' after %d consecutive failures",
                    service, entry["consecutive_failures"],
                )
            else:
                logger.warning(
                    "CircuitBreaker: already OPEN for '%s' — failure count now %d",
                    service, entry["consecutive_failures"],
                )
        else:
            logger.info(
                "CircuitBreaker: failure recorded for '%s' (%d/%d before open)",
                service, entry["consecutive_failures"], self.failure_threshold,
            )

        data[service] = entry
        self._save(data)

    def record_success(self, service: str) -> None:
        """
        Record a success for a service.

        Resets consecutive failure count and closes the circuit.
        """
        data = self._load()
        entry = self._get_entry(data, service)
        prev_state = entry.get("state", _STATE_CLOSED)

        entry["state"] = _STATE_CLOSED
        entry["consecutive_failures"] = 0
        entry["opened_at"] = None

        data[service] = entry
        self._save(data)

        if prev_state != _STATE_CLOSED:
            logger.info(
                "CircuitBreaker: CLOSED for service '%s' (was: %s)",
                service, prev_state,
            )
        else:
            logger.debug("CircuitBreaker: success recorded for '%s' (already closed)", service)

    def get_state(self, service: str) -> str:
        """Return the current circuit breaker state string for a service."""
        data = self._load()
        entry = self._get_entry(data, service)
        return entry.get("state", _STATE_CLOSED)
