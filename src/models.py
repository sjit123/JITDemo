from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TokenScope(BaseModel):
    ops: set[Literal["read", "write", "delete"]]
    tables: set[str]


class Policy(BaseModel):
    name: str
    description: str
    allowed_ops: set[Literal["read", "write", "delete"]]
    allowed_tables: set[str]
    max_ttl_seconds: int = Field(gt=0, le=3600)
    requires_approval: bool = False


class Lease(BaseModel):
    id: UUID
    token_id: UUID
    subject: str
    policy_name: str
    scope: TokenScope
    granted_at: datetime
    expires_at: datetime
    revoked: bool = False
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    @field_validator("granted_at", "expires_at", "revoked_at")
    @classmethod
    def ensure_utc_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware")
        return value.astimezone(UTC)

    @property
    def is_active(self) -> bool:
        return not self.revoked and self.expires_at > datetime.now(UTC)

    @property
    def seconds_remaining(self) -> float:
        if self.revoked:
            return 0.0
        remaining = (self.expires_at - datetime.now(UTC)).total_seconds()
        return max(0.0, remaining)


class AuditEvent(BaseModel):
    timestamp: datetime
    actor: str
    action: Literal[
        "lease_requested",
        "lease_granted",
        "lease_denied",
        "access_attempted",
        "access_granted",
        "access_denied",
        "lease_revoked",
        "lease_expired",
    ]
    resource: str | None = None
    outcome: Literal["success", "denied"]
    lease_id: UUID | None = None
    details: dict = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def ensure_timestamp_utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)
