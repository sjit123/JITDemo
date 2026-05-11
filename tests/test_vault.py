from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from uuid import UUID, uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import AccessDenied, InvalidToken
from src.audit import AuditLog
from src.lease_manager import LeaseManager
from src.models import AuditEvent, Policy
from src.models import Lease, TokenScope
from src.signer import Signer
from src.vault import MiniVault


def test_signer_round_trip_preserves_claims() -> None:
    signer = Signer()

    token = signer.encode(
        {
            "sub": "alice@corp",
            "jti": str(uuid4()),
            "scope": {"ops": ["read"], "tables": ["customers"]},
            "exp": int((datetime.now(UTC) + timedelta(seconds=30)).timestamp()),
        }
    )

    payload = signer.decode(token)

    assert payload["sub"] == "alice@corp"
    assert "scope" in payload
    assert "jti" in payload
    UUID(payload["jti"])


def test_signer_raises_invalid_token_on_expiry() -> None:
    signer = Signer()

    token = signer.encode(
        {
            "sub": "alice@corp",
            "jti": str(uuid4()),
            "scope": {"ops": ["read"], "tables": ["customers"]},
            "exp": int((datetime.now(UTC) - timedelta(seconds=1)).timestamp()),
        }
    )

    with pytest.raises(InvalidToken, match="expired"):
        signer.decode(token)


def test_audit_append_and_tail() -> None:
    log = AuditLog()
    now = datetime.now(UTC)

    first = AuditEvent(
        timestamp=now,
        actor="system",
        action="lease_requested",
        outcome="success",
        details={"step": 1},
    )
    second = AuditEvent(
        timestamp=now + timedelta(seconds=1),
        actor="system",
        action="lease_granted",
        outcome="success",
        details={"step": 2},
    )

    log.append(first)
    log.append(second)

    tail = log.tail(1)
    assert len(tail) == 1
    assert tail[0].action == "lease_granted"

    later = log.since(now)
    assert len(later) == 1
    assert later[0].action == "lease_granted"


def _build_lease(ttl_seconds: int = 5) -> Lease:
    now = datetime.now(UTC)
    return Lease(
        id=uuid4(),
        token_id=uuid4(),
        subject="alice@corp",
        policy_name="customer-readonly",
        scope=TokenScope(ops={"read"}, tables={"customers"}),
        granted_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )


def test_lease_manager_add_get_revoke() -> None:
    audit = AuditLog()
    manager = LeaseManager(audit)
    lease = _build_lease(ttl_seconds=10)

    manager.add(lease)
    fetched = manager.get(lease.id)
    assert fetched is not None
    assert fetched.id == lease.id
    assert len(manager.list_active()) == 1

    revoked = manager.revoke(lease.id, reason="manual")
    assert revoked is not None
    assert revoked.revoked is True
    assert revoked.revocation_reason == "manual"
    assert len(manager.list_active()) == 0


def test_sweeper_marks_expired_and_emits_audit_event_within_three_seconds() -> None:
    audit = AuditLog()
    manager = LeaseManager(audit)
    lease = _build_lease(ttl_seconds=1)
    manager.add(lease)
    manager.start_sweeper(interval=0.1)

    try:
        deadline = time.monotonic() + 4.0
        matched: AuditEvent | None = None

        while time.monotonic() < deadline:
            events = audit.tail(100)
            for event in events:
                if event.action == "lease_expired" and event.lease_id == lease.id:
                    matched = event
                    break
            if matched is not None:
                break
            time.sleep(0.05)

        assert matched is not None
        assert matched.outcome == "success"
        assert matched.timestamp <= lease.expires_at + timedelta(seconds=3)

        active_ids = {active.id for active in manager.list_active()}
        assert lease.id not in active_ids
    finally:
        manager.stop_sweeper()


def _build_vault_with_policy(max_ttl_seconds: int = 300) -> MiniVault:
    vault = MiniVault()
    vault.register_policy(
        Policy(
            name="customer-readonly",
            description="Read-only access to customers",
            allowed_ops={"read"},
            allowed_tables={"customers"},
            max_ttl_seconds=max_ttl_seconds,
        )
    )
    return vault


def test_vault_lease_lifecycle_expiry_and_audit_order() -> None:
    vault = _build_vault_with_policy(max_ttl_seconds=2)
    vault.lease_manager.start_sweeper(interval=0.1)

    try:
        token, lease = vault.request_lease(
            subject="alice@corp",
            policy_name="customer-readonly",
            requested_ttl=2,
        )

        time.sleep(1.0)
        scope = vault.validate(token)
        assert scope.ops == {"read"}
        assert scope.tables == {"customers"}

        time.sleep(2.0)
        with pytest.raises(AccessDenied, match="expired"):
            vault.validate(token)

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            events = vault.audit_log.tail(100)
            actions = [event.action for event in events]
            if "lease_expired" in actions:
                break
            time.sleep(0.05)

        events = vault.audit_log.tail(100)
        actions = [event.action for event in events]
        requested_index = actions.index("lease_requested")
        granted_index = actions.index("lease_granted")
        expired_index = actions.index("lease_expired")

        assert requested_index < granted_index < expired_index
        assert any(
            event.action == "lease_expired" and event.lease_id == lease.id
            for event in events
        )
    finally:
        vault.lease_manager.stop_sweeper()


def test_vault_validate_denies_manual_revocation_before_jwt_expiry() -> None:
    vault = _build_vault_with_policy(max_ttl_seconds=60)

    token, lease = vault.request_lease(
        subject="alice@corp",
        policy_name="customer-readonly",
        requested_ttl=60,
    )

    time.sleep(1.0)
    vault.revoke(lease.id, reason="manual")

    assert lease.expires_at > datetime.now(UTC)
    with pytest.raises(AccessDenied, match="manual"):
        vault.validate(token)


def test_vault_validate_denies_when_jti_missing_lease() -> None:
    vault = _build_vault_with_policy()
    now = datetime.now(UTC)

    forged = vault._signer.encode(
        {
            "sub": "alice@corp",
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=30)).timestamp()),
            "scope": {"ops": ["read"], "tables": ["customers"]},
        }
    )

    with pytest.raises(AccessDenied, match="lease not found"):
        vault.validate(forged)
