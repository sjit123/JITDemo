from __future__ import annotations

from datetime import datetime
from threading import RLock

from src.models import AuditEvent


class AuditLog:
    """Thread-safe append-only store for security-relevant events."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = RLock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def tail(self, n: int = 50) -> list[AuditEvent]:
        with self._lock:
            return list(self._events[-n:])

    def since(self, timestamp: datetime) -> list[AuditEvent]:
        with self._lock:
            return [event for event in self._events if event.timestamp > timestamp]
