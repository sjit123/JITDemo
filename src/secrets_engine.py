from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.lease_manager import LeaseManager
from src.models import Lease, Policy, TokenScope
from src.signer import Signer


class DynamicDBCredentialsEngine:
    """Issues short-lived scoped JWTs and tracks them as leases."""

    def __init__(self, signer: Signer, lease_manager: LeaseManager) -> None:
        self._signer = signer
        self._lease_manager = lease_manager

    def issue(self, subject: str, policy: Policy, requested_ttl: int) -> tuple[str, Lease]:
        now = datetime.now(UTC)
        ttl_seconds = max(1, min(requested_ttl, policy.max_ttl_seconds))
        expires_at = now + timedelta(seconds=ttl_seconds)

        scope = TokenScope(ops=set(policy.allowed_ops), tables=set(policy.allowed_tables))
        token_id = uuid4()
        lease = Lease(
            id=uuid4(),
            token_id=token_id,
            subject=subject,
            policy_name=policy.name,
            scope=scope,
            granted_at=now,
            expires_at=expires_at,
        )

        claims = {
            "sub": subject,
            "jti": str(token_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "scope": {
                "ops": sorted(scope.ops),
                "tables": sorted(scope.tables),
            },
        }

        token = self._signer.encode(claims)
        self._lease_manager.add(lease)
        return token, lease
