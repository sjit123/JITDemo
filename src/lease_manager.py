from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from src.audit import AuditLog
from src.models import AuditEvent, Lease

LOGGER = logging.getLogger(__name__)


class LeaseManager:
    """In-memory lease store with background expiry revocation."""

    def __init__(self, audit_log: AuditLog, now_fn: Callable[[], datetime] | None = None) -> None:
        self._audit_log = audit_log
        self._leases: dict[UUID, Lease] = {}
        self._lock = threading.RLock()
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._stop_event = threading.Event()
        self._sweeper_thread: threading.Thread | None = None

    def add(self, lease: Lease) -> None:
        with self._lock:
            self._leases[lease.id] = lease

    def get(self, lease_id: UUID) -> Lease | None:
        with self._lock:
            return self._leases.get(lease_id)

    def revoke(self, lease_id: UUID, reason: str) -> Lease | None:
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None or lease.revoked:
                return lease

            now = self._now_fn()
            updated = lease.model_copy(
                update={
                    "revoked": True,
                    "revoked_at": now,
                    "revocation_reason": reason,
                }
            )
            self._leases[lease_id] = updated
            return updated

    def list_active(self) -> list[Lease]:
        with self._lock:
            return [lease for lease in self._leases.values() if lease.is_active]

    def list_all(self) -> list[Lease]:
        with self._lock:
            return list(self._leases.values())

    def start_sweeper(self, interval: float = 1.0) -> None:
        if self._sweeper_thread and self._sweeper_thread.is_alive():
            return

        self._stop_event.clear()
        self._sweeper_thread = threading.Thread(
            target=self._run_sweeper,
            args=(interval,),
            daemon=True,
            name="lease-sweeper",
        )
        self._sweeper_thread.start()

    def stop_sweeper(self) -> None:
        self._stop_event.set()
        if self._sweeper_thread and self._sweeper_thread.is_alive():
            self._sweeper_thread.join(timeout=2.0)

    def _run_sweeper(self, interval: float) -> None:
        while not self._stop_event.is_set():
            self._expire_overdue_leases()
            self._stop_event.wait(interval)

    def _expire_overdue_leases(self) -> None:
        now = self._now_fn()
        expired: list[Lease] = []

        with self._lock:
            for lease_id, lease in list(self._leases.items()):
                if lease.revoked or lease.expires_at > now:
                    continue

                updated = lease.model_copy(
                    update={
                        "revoked": True,
                        "revoked_at": now,
                        "revocation_reason": "expired",
                    }
                )
                self._leases[lease_id] = updated
                expired.append(updated)

        for lease in expired:
            self._audit_log.append(
                AuditEvent(
                    timestamp=now,
                    actor="sweeper",
                    action="lease_expired",
                    outcome="success",
                    lease_id=lease.id,
                    details={
                        "subject": lease.subject,
                        "policy_name": lease.policy_name,
                        "reason": "expired",
                    },
                )
            )
            LOGGER.info("Lease expired and revoked", extra={"lease_id": str(lease.id)})
