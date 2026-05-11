from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src import AccessDenied, InvalidToken, PolicyNotFound
from src.audit import AuditLog
from src.lease_manager import LeaseManager
from src.models import AuditEvent, Lease, Policy, TokenScope
from src.secrets_engine import DynamicDBCredentialsEngine
from src.signer import Signer


class MiniVault:
    """Facade that manages policy lookup, lease issuance, validation, and audit."""

    def __init__(self) -> None:
        self._audit_log = AuditLog()
        self._lease_manager = LeaseManager(self._audit_log)
        self._signer = Signer()
        self._engine = DynamicDBCredentialsEngine(self._signer, self._lease_manager)
        self._policies: dict[str, Policy] = {}

    def register_policy(self, policy: Policy) -> None:
        self._policies[policy.name] = policy

    def list_policies(self) -> list[Policy]:
        return list(self._policies.values())

    def request_lease(self, subject: str, policy_name: str, requested_ttl: int) -> tuple[str, Lease]:
        self._audit_log.append(
            AuditEvent(
                timestamp=datetime.now(UTC),
                actor=subject,
                action="lease_requested",
                outcome="success",
                resource=policy_name,
                details={"requested_ttl": requested_ttl},
            )
        )

        policy = self._policies.get(policy_name)
        if policy is None:
            self._audit_log.append(
                AuditEvent(
                    timestamp=datetime.now(UTC),
                    actor=subject,
                    action="lease_denied",
                    outcome="denied",
                    resource=policy_name,
                    details={"reason": "policy not found"},
                )
            )
            raise PolicyNotFound("policy not found")

        token, lease = self._engine.issue(subject, policy, requested_ttl)
        self._audit_log.append(
            AuditEvent(
                timestamp=datetime.now(UTC),
                actor=subject,
                action="lease_granted",
                outcome="success",
                resource=policy_name,
                lease_id=lease.id,
                details={"token_id": str(lease.token_id), "ttl_seconds": requested_ttl},
            )
        )
        return token, lease

    def validate(self, token_str: str) -> TokenScope:
        try:
            # First security boundary: reject forged/expired tokens cryptographically.
            claims = self._signer.decode(token_str)
        except InvalidToken as exc:
            raise AccessDenied(str(exc)) from exc

        raw_jti = claims.get("jti")
        if raw_jti is None:
            raise AccessDenied("lease not found")

        try:
            token_id = UUID(str(raw_jti))
        except ValueError as exc:
            raise AccessDenied("lease not found") from exc

        # Second independent boundary: reject tokens tied to revoked/missing leases.
        lease = self._find_lease_by_token_id(token_id)
        if lease is None:
            raise AccessDenied("lease not found")
        if lease.revoked:
            raise AccessDenied(lease.revocation_reason or "revoked")

        scope_claim = claims.get("scope")
        if not isinstance(scope_claim, dict):
            raise AccessDenied("invalid scope")

        try:
            return TokenScope.model_validate(scope_claim)
        except Exception as exc:  # noqa: BLE001
            raise AccessDenied("invalid scope") from exc

    def revoke(self, lease_id: UUID, reason: str = "manual") -> None:
        lease = self._lease_manager.revoke(lease_id, reason)
        if lease is None:
            raise AccessDenied("lease not found")

        self._audit_log.append(
            AuditEvent(
                timestamp=datetime.now(UTC),
                actor="vault",
                action="lease_revoked",
                outcome="success",
                lease_id=lease_id,
                details={"reason": reason},
            )
        )

    def list_active_leases(self) -> list[Lease]:
        return self._lease_manager.list_active()

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    @property
    def lease_manager(self) -> LeaseManager:
        return self._lease_manager

    def _find_lease_by_token_id(self, token_id: UUID) -> Lease | None:
        for lease in self._lease_manager.list_all():
            if lease.token_id == token_id:
                return lease
        return None
