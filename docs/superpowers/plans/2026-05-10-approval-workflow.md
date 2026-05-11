# Approval Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a human-in-the-loop approval queue so that `customer-admin` lease requests are held pending until `admin@corp` approves or rejects them in Vault Admin.

**Architecture:** `MiniVault.request_lease()` intercepts policies with `requires_approval=True` and raises `ApprovalRequired` instead of issuing a lease. An `ApprovalQueue` (new module) holds `PendingRequest` objects. `admin@corp` reviews the queue in Vault Admin and calls `vault.approve_request()` / `vault.reject_request()`. Persona runners catch the exception and yield a `"pending"` event.


**Tech Stack:** Python 3.13, Pydantic v2, PyJWT, Streamlit, pytest, threading.RLock (in-memory, no persistence)

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `src/approval_queue.py` | Thread-safe in-memory store for `PendingRequest` objects |
| Create | `tests/test_approval.py` | All approval workflow unit tests |
| Modify | `src/models.py` | Add `PendingRequest` model; extend `AuditEvent.action` literals |
| Modify | `src/__init__.py` | Add `ApprovalRequired` exception |
| Modify | `src/vault.py` | Add `ApprovalQueue` composition; approval intercept; `approve_request`/`reject_request`/`list_pending_requests` |
| Modify | `src/personas/human.py` | Catch `ApprovalRequired`, yield `"pending"` event |
| Modify | `src/personas/agent.py` | Same — both `run_happy_path` and `run_denial_path` |
| Modify | `src/personas/app.py` | Same |
| Modify | `src/seed.py` | Set `customer-admin` `requires_approval=True` |
| Modify | `app.py` | Add `"admin@corp"` to `ACTOR_OPTIONS` |
| Modify | `tests/test_personas.py` | Add `"pending"` to valid kinds; add persona approval tests |
| Modify | `pages/2_✅_JIT_Flow.py` | Handle `"pending"` kind in `_render_stream`; update run status chips |
| Modify | `pages/3_🔐_Vault_Admin.py` | Add Pending Approvals section (admin@corp only) |

---

## Task 1: PendingRequest model + AuditEvent action literals

**Files:**
- Modify: `src/models.py`
- Create: `tests/test_approval.py`

- [ ] **Step 1: Create test file with failing PendingRequest tests**

Create `tests/test_approval.py`:

```python
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import AuditEvent, PendingRequest, Policy


def _make_pending(
    policy_name: str = "customer-admin",
    ttl: int = 60,
    subject: str = "alice@corp",
) -> PendingRequest:
    return PendingRequest(
        id=uuid4(),
        subject=subject,
        policy_name=policy_name,
        requested_ttl=ttl,
        requested_at=datetime.now(UTC),
    )


def test_pending_request_defaults_to_pending_status() -> None:
    req = _make_pending()
    assert req.status == "pending"
    assert req.reviewed_by is None
    assert req.reviewed_at is None
    assert req.rejection_reason is None


def test_pending_request_rejects_naive_datetime() -> None:
    with pytest.raises(Exception):
        PendingRequest(
            id=uuid4(),
            subject="alice@corp",
            policy_name="customer-admin",
            requested_ttl=60,
            requested_at=datetime(2026, 1, 1),  # naive — no tzinfo
        )


def test_audit_event_accepts_approval_requested_action() -> None:
    event = AuditEvent(
        timestamp=datetime.now(UTC),
        actor="alice@corp",
        action="approval_requested",
        outcome="success",
        details={},
    )
    assert event.action == "approval_requested"


def test_audit_event_accepts_approval_granted_action() -> None:
    event = AuditEvent(
        timestamp=datetime.now(UTC),
        actor="admin@corp",
        action="approval_granted",
        outcome="success",
        details={},
    )
    assert event.action == "approval_granted"


def test_audit_event_accepts_approval_rejected_action() -> None:
    event = AuditEvent(
        timestamp=datetime.now(UTC),
        actor="admin@corp",
        action="approval_rejected",
        outcome="denied",
        details={},
    )
    assert event.action == "approval_rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_approval.py -v
```

Expected: FAIL — `PendingRequest` and the new `AuditEvent` action literals don't exist yet.

- [ ] **Step 3: Add PendingRequest and update AuditEvent.action in `src/models.py`**

Add `PendingRequest` class after the `Lease` class (after line ~55):

```python
class PendingRequest(BaseModel):
    id: UUID
    subject: str
    policy_name: str
    requested_ttl: int
    requested_at: datetime
    status: Literal["pending", "approved", "rejected"] = "pending"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None

    @field_validator("requested_at", "reviewed_at")
    @classmethod
    def ensure_utc_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware")
        return value.astimezone(UTC)
```

Update `AuditEvent.action` field (currently lines 61–70) to add three new literals:

```python
action: Literal[
    "lease_requested",
    "lease_granted",
    "lease_denied",
    "access_attempted",
    "access_granted",
    "access_denied",
    "lease_revoked",
    "lease_expired",
    "approval_requested",
    "approval_granted",
    "approval_rejected",
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_approval.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Verify no existing tests broke**

```bash
pytest tests/test_vault.py tests/test_db_proxy.py tests/test_personas.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/models.py tests/test_approval.py
git commit -m "feat: add PendingRequest model and approval audit event literals"
```

---

## Task 2: ApprovalRequired exception

**Files:**
- Modify: `src/__init__.py`
- Modify: `tests/test_approval.py`

- [ ] **Step 1: Add failing test to `tests/test_approval.py`**

Append to `tests/test_approval.py`:

```python
from src import ApprovalRequired


def test_approval_required_carries_pending_request() -> None:
    req = _make_pending()
    exc = ApprovalRequired(req)
    assert exc.pending_request is req
    assert str(exc) == "approval required"


def test_approval_required_is_exception_subclass() -> None:
    req = _make_pending()
    exc = ApprovalRequired(req)
    assert isinstance(exc, Exception)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_approval.py::test_approval_required_carries_pending_request tests/test_approval.py::test_approval_required_is_exception_subclass -v
```

Expected: FAIL — `ApprovalRequired` not yet defined.

- [ ] **Step 3: Replace `src/__init__.py` with updated version**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import PendingRequest


class AccessDenied(Exception):
    """Raised when an operation is denied by policy, scope, or lease state."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class InvalidToken(Exception):
    """Raised when a token is invalid, malformed, expired, or untrusted."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class PolicyNotFound(Exception):
    """Raised when a requested policy does not exist in the vault."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ApprovalRequired(Exception):
    """Raised when a policy requires human approval before a lease can be issued."""

    def __init__(self, pending_request: PendingRequest) -> None:
        self.pending_request = pending_request
        super().__init__("approval required")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_approval.py::test_approval_required_carries_pending_request tests/test_approval.py::test_approval_required_is_exception_subclass -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/__init__.py tests/test_approval.py
git commit -m "feat: add ApprovalRequired exception"
```

---

## Task 3: ApprovalQueue

**Files:**
- Create: `src/approval_queue.py`
- Modify: `tests/test_approval.py`

- [ ] **Step 1: Add failing ApprovalQueue tests to `tests/test_approval.py`**

Append to `tests/test_approval.py`:

```python
from src.approval_queue import ApprovalQueue


def test_approval_queue_add_and_get() -> None:
    queue = ApprovalQueue()
    req = _make_pending()
    queue.add(req)
    fetched = queue.get(req.id)
    assert fetched is not None
    assert fetched.id == req.id


def test_approval_queue_get_returns_none_for_unknown_id() -> None:
    queue = ApprovalQueue()
    assert queue.get(uuid4()) is None


def test_approval_queue_list_pending_returns_only_pending() -> None:
    queue = ApprovalQueue()
    req1 = _make_pending()
    req2 = _make_pending()
    queue.add(req1)
    queue.add(req2)
    queue.approve(req1.id, reviewed_by="admin@corp")
    pending = queue.list_pending()
    ids = {r.id for r in pending}
    assert req2.id in ids
    assert req1.id not in ids


def test_approval_queue_approve_transitions_to_approved() -> None:
    queue = ApprovalQueue()
    req = _make_pending()
    queue.add(req)
    approved = queue.approve(req.id, reviewed_by="admin@corp")
    assert approved is not None
    assert approved.status == "approved"
    assert approved.reviewed_by == "admin@corp"
    assert approved.reviewed_at is not None


def test_approval_queue_approve_is_immutable() -> None:
    queue = ApprovalQueue()
    req = _make_pending()
    queue.add(req)
    approved = queue.approve(req.id, reviewed_by="admin@corp")
    assert approved is not req


def test_approval_queue_reject_sets_reason() -> None:
    queue = ApprovalQueue()
    req = _make_pending()
    queue.add(req)
    rejected = queue.reject(req.id, reviewed_by="admin@corp", reason="not justified")
    assert rejected is not None
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "not justified"
    assert rejected.reviewed_by == "admin@corp"


def test_approval_queue_approve_returns_none_for_unknown_id() -> None:
    queue = ApprovalQueue()
    result = queue.approve(uuid4(), reviewed_by="admin@corp")
    assert result is None


def test_approval_queue_approve_returns_none_for_already_reviewed() -> None:
    queue = ApprovalQueue()
    req = _make_pending()
    queue.add(req)
    queue.approve(req.id, reviewed_by="admin@corp")
    result = queue.approve(req.id, reviewed_by="admin@corp")
    assert result is None


def test_approval_queue_reject_returns_none_for_unknown_id() -> None:
    queue = ApprovalQueue()
    result = queue.reject(uuid4(), reviewed_by="admin@corp", reason="test")
    assert result is None


def test_approval_queue_reject_returns_none_for_already_reviewed() -> None:
    queue = ApprovalQueue()
    req = _make_pending()
    queue.add(req)
    queue.reject(req.id, reviewed_by="admin@corp", reason="first reason")
    result = queue.reject(req.id, reviewed_by="admin@corp", reason="second reason")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_approval.py -k "approval_queue" -v
```

Expected: FAIL — `src/approval_queue.py` doesn't exist.

- [ ] **Step 3: Create `src/approval_queue.py`**

```python
from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import UUID

from src.models import PendingRequest


class ApprovalQueue:
    """Thread-safe in-memory store for pending lease approval requests."""

    def __init__(self) -> None:
        self._requests: dict[UUID, PendingRequest] = {}
        self._lock = threading.RLock()

    def add(self, request: PendingRequest) -> None:
        with self._lock:
            self._requests[request.id] = request

    def get(self, request_id: UUID) -> PendingRequest | None:
        with self._lock:
            return self._requests.get(request_id)

    def approve(self, request_id: UUID, reviewed_by: str) -> PendingRequest | None:
        with self._lock:
            request = self._requests.get(request_id)
            if request is None or request.status != "pending":
                return None
            updated = request.model_copy(
                update={
                    "status": "approved",
                    "reviewed_by": reviewed_by,
                    "reviewed_at": datetime.now(UTC),
                }
            )
            self._requests[request_id] = updated
            return updated

    def reject(self, request_id: UUID, reviewed_by: str, reason: str) -> PendingRequest | None:
        with self._lock:
            request = self._requests.get(request_id)
            if request is None or request.status != "pending":
                return None
            updated = request.model_copy(
                update={
                    "status": "rejected",
                    "reviewed_by": reviewed_by,
                    "reviewed_at": datetime.now(UTC),
                    "rejection_reason": reason,
                }
            )
            self._requests[request_id] = updated
            return updated

    def list_pending(self) -> list[PendingRequest]:
        with self._lock:
            return [r for r in self._requests.values() if r.status == "pending"]
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/test_approval.py -k "approval_queue" -v
```

Expected: 10 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/approval_queue.py tests/test_approval.py
git commit -m "feat: add ApprovalQueue with thread-safe pending request store"
```

---

## Task 4: MiniVault — approval intercept in request_lease

**Files:**
- Modify: `src/vault.py`
- Modify: `tests/test_approval.py`

- [ ] **Step 1: Add failing vault intercept tests to `tests/test_approval.py`**

Append to `tests/test_approval.py`:

```python
from src import AccessDenied, ApprovalRequired, PolicyNotFound
from src.vault import MiniVault


def _build_vault_with_policies() -> MiniVault:
    vault = MiniVault()
    vault.register_policy(
        Policy(
            name="customer-admin",
            description="Admin access requiring approval",
            allowed_ops={"read", "write", "delete"},
            allowed_tables={"customers"},
            max_ttl_seconds=60,
            requires_approval=True,
        )
    )
    vault.register_policy(
        Policy(
            name="customer-readonly",
            description="Read-only, no approval needed",
            allowed_ops={"read"},
            allowed_tables={"customers"},
            max_ttl_seconds=300,
            requires_approval=False,
        )
    )
    return vault


def test_vault_raises_approval_required_for_approval_policy() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired) as exc_info:
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    assert exc_info.value.pending_request.subject == "alice@corp"
    assert exc_info.value.pending_request.policy_name == "customer-admin"
    assert exc_info.value.pending_request.requested_ttl == 60


def test_vault_emits_approval_requested_audit_event() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired):
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    events = vault.audit_log.tail(100)
    actions = [e.action for e in events]
    assert "approval_requested" in actions


def test_vault_non_approval_policy_issues_lease_directly() -> None:
    vault = _build_vault_with_policies()
    token, lease = vault.request_lease("alice@corp", "customer-readonly", requested_ttl=60)
    assert token
    assert lease.is_active


def test_vault_pending_request_appears_in_list_after_raise() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired) as exc_info:
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    request_id = exc_info.value.pending_request.id
    pending = vault.list_pending_requests()
    assert any(r.id == request_id for r in pending)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_approval.py -k "vault_raises or vault_emits or vault_non_approval or vault_pending_request_appears" -v
```

Expected: FAIL — `list_pending_requests` doesn't exist; `request_lease` doesn't intercept yet.

- [ ] **Step 3: Replace `src/vault.py` with updated version (intercept + list_pending only; approve/reject added in Task 5)**

```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src import AccessDenied, ApprovalRequired, InvalidToken, PolicyNotFound
from src.approval_queue import ApprovalQueue
from src.audit import AuditLog
from src.lease_manager import LeaseManager
from src.models import AuditEvent, Lease, PendingRequest, Policy, TokenScope
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
        self._approval_queue = ApprovalQueue()

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

        if policy.requires_approval:
            pending = PendingRequest(
                id=uuid4(),
                subject=subject,
                policy_name=policy_name,
                requested_ttl=requested_ttl,
                requested_at=datetime.now(UTC),
            )
            self._approval_queue.add(pending)
            self._audit_log.append(
                AuditEvent(
                    timestamp=datetime.now(UTC),
                    actor=subject,
                    action="approval_requested",
                    outcome="success",
                    resource=policy_name,
                    details={"request_id": str(pending.id), "requested_ttl": requested_ttl},
                )
            )
            raise ApprovalRequired(pending)

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

    def list_pending_requests(self) -> list[PendingRequest]:
        return self._approval_queue.list_pending()

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
```

- [ ] **Step 4: Verify intercept tests pass**

```bash
pytest tests/test_approval.py -k "vault_raises or vault_emits or vault_non_approval or vault_pending_request_appears" -v
```

Expected: 4 PASSED

- [ ] **Step 5: Verify all existing tests still pass**

```bash
pytest tests/test_vault.py tests/test_db_proxy.py tests/test_personas.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/vault.py tests/test_approval.py
git commit -m "feat: add approval intercept to MiniVault.request_lease and wire approve/reject methods"
```

---

## Task 5: MiniVault — approve_request and reject_request

**Files:**
- Modify: `src/vault.py`
- Modify: `tests/test_approval.py`

- [ ] **Step 1: Add failing approve/reject tests to `tests/test_approval.py`**

Append to `tests/test_approval.py`:

```python
def test_vault_approve_request_issues_lease_and_token() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired) as exc_info:
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    request_id = exc_info.value.pending_request.id
    token, lease = vault.approve_request(request_id, reviewed_by="admin@corp")
    assert token
    assert lease.is_active
    assert lease.subject == "alice@corp"
    assert lease.policy_name == "customer-admin"


def test_vault_approve_request_emits_approval_granted_audit() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired) as exc_info:
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    request_id = exc_info.value.pending_request.id
    vault.approve_request(request_id, reviewed_by="admin@corp")
    events = vault.audit_log.tail(100)
    actions = [e.action for e in events]
    assert "approval_granted" in actions
    granted = next(e for e in events if e.action == "approval_granted")
    assert granted.actor == "admin@corp"
    assert granted.outcome == "success"


def test_vault_approve_request_removes_from_pending_list() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired) as exc_info:
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    request_id = exc_info.value.pending_request.id
    vault.approve_request(request_id, reviewed_by="admin@corp")
    pending = vault.list_pending_requests()
    assert not any(r.id == request_id for r in pending)


def test_vault_reject_request_emits_approval_rejected_audit() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired) as exc_info:
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    request_id = exc_info.value.pending_request.id
    vault.reject_request(request_id, reviewed_by="admin@corp", reason="policy violation")
    events = vault.audit_log.tail(100)
    actions = [e.action for e in events]
    assert "approval_rejected" in actions
    rejected_event = next(e for e in events if e.action == "approval_rejected")
    assert rejected_event.actor == "admin@corp"
    assert rejected_event.outcome == "denied"


def test_vault_reject_request_issues_no_lease() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(ApprovalRequired) as exc_info:
        vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)
    request_id = exc_info.value.pending_request.id
    vault.reject_request(request_id, reviewed_by="admin@corp", reason="not justified")
    assert len(vault.list_active_leases()) == 0


def test_vault_approve_unknown_request_raises_access_denied() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(AccessDenied):
        vault.approve_request(uuid4(), reviewed_by="admin@corp")


def test_vault_reject_unknown_request_raises_access_denied() -> None:
    vault = _build_vault_with_policies()
    with pytest.raises(AccessDenied):
        vault.reject_request(uuid4(), reviewed_by="admin@corp", reason="test")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_approval.py -k "vault_approve or vault_reject" -v
```

Expected: FAIL — `approve_request` and `reject_request` not yet defined on `MiniVault`.

- [ ] **Step 3: Add approve_request and reject_request to `src/vault.py`**

Insert these two methods inside `MiniVault`, before `list_active_leases`:

```python
def approve_request(self, request_id: UUID, reviewed_by: str) -> tuple[str, Lease]:
    approved = self._approval_queue.approve(request_id, reviewed_by)
    if approved is None:
        raise AccessDenied("request not found")

    policy = self._policies.get(approved.policy_name)
    if policy is None:
        raise PolicyNotFound("policy not found")

    token, lease = self._engine.issue(approved.subject, policy, approved.requested_ttl)
    self._audit_log.append(
        AuditEvent(
            timestamp=datetime.now(UTC),
            actor=reviewed_by,
            action="approval_granted",
            outcome="success",
            resource=approved.policy_name,
            lease_id=lease.id,
            details={"request_id": str(request_id), "subject": approved.subject},
        )
    )
    return token, lease

def reject_request(self, request_id: UUID, reviewed_by: str, reason: str) -> PendingRequest:
    rejected = self._approval_queue.reject(request_id, reviewed_by, reason)
    if rejected is None:
        raise AccessDenied("request not found")

    self._audit_log.append(
        AuditEvent(
            timestamp=datetime.now(UTC),
            actor=reviewed_by,
            action="approval_rejected",
            outcome="denied",
            resource=rejected.policy_name,
            details={"request_id": str(request_id), "reason": reason, "subject": rejected.subject},
        )
    )
    return rejected
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/test_approval.py -k "vault_approve or vault_reject" -v
```

Expected: 7 PASSED

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/vault.py tests/test_approval.py
git commit -m "feat: add approve_request and reject_request to MiniVault"
```

---

## Task 6: Persona runner updates

**Files:**
- Modify: `src/personas/human.py`
- Modify: `src/personas/agent.py`
- Modify: `src/personas/app.py`
- Modify: `tests/test_personas.py`

- [ ] **Step 1: Update `_collect_events` in `tests/test_personas.py` to allow "pending" kind**

Find the assertion in `_collect_events` (line ~35):

```python
assert event["kind"] in ("thought", "action", "result", "error"), f"invalid kind: {event['kind']}"
```

Replace with:

```python
assert event["kind"] in ("thought", "action", "result", "error", "pending"), f"invalid kind: {event['kind']}"
```

Also add `Policy` to the existing import line at the top of the file:

```python
from src.models import Policy
```

- [ ] **Step 2: Add failing persona approval tests to `tests/test_personas.py`**

Append to `tests/test_personas.py`:

```python
def test_human_persona_yields_pending_for_approval_policy() -> None:
    conn = sqlite3.connect(":memory:")
    vault = MiniVault()
    vault.register_policy(
        Policy(
            name="customer-admin",
            description="Admin access",
            allowed_ops={"read", "write", "delete"},
            allowed_tables={"customers"},
            max_ttl_seconds=60,
            requires_approval=True,
        )
    )
    seed_db(conn)
    proxy = DBProxy(conn, vault)

    events = list(human.run(
        vault=vault,
        db_proxy=proxy,
        subject="alice@corp",
        policy_name="customer-admin",
        task_description="Delete inactive accounts",
        think_delay=0.0,
    ))
    kinds = [e["kind"] for e in events]
    assert "pending" in kinds
    pending_event = next(e for e in events if e["kind"] == "pending")
    assert "request_id" in pending_event["data"]


def test_agent_happy_path_yields_pending_for_approval_policy() -> None:
    conn = sqlite3.connect(":memory:")
    vault = MiniVault()
    vault.register_policy(
        Policy(
            name="customer-readonly",
            description="Read-only requiring approval",
            allowed_ops={"read"},
            allowed_tables={"customers"},
            max_ttl_seconds=300,
            requires_approval=True,
        )
    )
    seed_db(conn)
    proxy = DBProxy(conn, vault)

    events = list(agent.run_happy_path(vault=vault, db_proxy=proxy, think_delay=0.0))
    kinds = [e["kind"] for e in events]
    assert "pending" in kinds


def test_agent_denial_path_yields_pending_for_approval_policy() -> None:
    conn = sqlite3.connect(":memory:")
    vault = MiniVault()
    vault.register_policy(
        Policy(
            name="customer-readonly",
            description="Read-only requiring approval",
            allowed_ops={"read"},
            allowed_tables={"customers"},
            max_ttl_seconds=300,
            requires_approval=True,
        )
    )
    seed_db(conn)
    proxy = DBProxy(conn, vault)

    events = list(agent.run_denial_path(vault=vault, db_proxy=proxy, think_delay=0.0))
    kinds = [e["kind"] for e in events]
    assert "pending" in kinds
```

- [ ] **Step 3: Run new persona tests to verify they fail**

```bash
pytest tests/test_personas.py::test_human_persona_yields_pending_for_approval_policy tests/test_personas.py::test_agent_happy_path_yields_pending_for_approval_policy tests/test_personas.py::test_agent_denial_path_yields_pending_for_approval_policy -v
```

Expected: FAIL — generators raise `ApprovalRequired` instead of yielding `"pending"`.

- [ ] **Step 4: Replace `src/personas/human.py`**

```python
from __future__ import annotations

import time
from typing import Any, Generator

from src import ApprovalRequired
from src.db_proxy import DBProxy
from src.vault import MiniVault


def run(
    vault: MiniVault,
    db_proxy: DBProxy,
    subject: str,
    policy_name: str,
    task_description: str,
    think_delay: float = 0.0,
) -> Generator[dict[str, Any], None, None]:
    """A human user requests access, does a task, and releases."""

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": f"User {subject} wants to: {task_description}",
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": f"Requesting lease on policy '{policy_name}'",
    }

    try:
        token, lease = vault.request_lease(subject, policy_name, requested_ttl=60)
    except ApprovalRequired as exc:
        yield {
            "kind": "pending",
            "text": "Approval required. Request queued — waiting for admin@corp.",
            "data": {"request_id": str(exc.pending_request.id)},
        }
        return

    yield {
        "kind": "result",
        "text": f"✓ Lease granted! Expires in {lease.seconds_remaining:.0f}s",
        "data": {
            "lease_id": str(lease.id),
            "token_id": str(lease.token_id),
            "expires_at": lease.expires_at.isoformat(),
        },
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": f"Executing task: {task_description}",
    }

    rows = db_proxy.read(table="customers", token=token)

    yield {
        "kind": "result",
        "text": f"✓ Read {len(rows)} customer rows",
        "data": {"row_count": len(rows)},
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "Task complete. Releasing lease early.",
    }

    vault.revoke(lease.id, reason="task complete")

    yield {
        "kind": "result",
        "text": f"✓ Lease revoked after {60 - lease.seconds_remaining:.0f}s (released early)",
        "data": {"revocation_reason": "task complete"},
    }
```

- [ ] **Step 5: Update `src/personas/agent.py`**

Change the import line from:
```python
from src import AccessDenied
```
to:
```python
from src import AccessDenied, ApprovalRequired
```

In `run_happy_path`, replace:
```python
token, lease = vault.request_lease(
    subject="research-agent",
    policy_name="customer-readonly",
    requested_ttl=60,
)
```
with:
```python
try:
    token, lease = vault.request_lease(
        subject="research-agent",
        policy_name="customer-readonly",
        requested_ttl=60,
    )
except ApprovalRequired as exc:
    yield {
        "kind": "pending",
        "text": "Approval required. Request queued — waiting for admin@corp.",
        "data": {"request_id": str(exc.pending_request.id)},
    }
    return
```

In `run_denial_path`, replace:
```python
token, lease = vault.request_lease(
    subject="research-agent",
    policy_name="customer-readonly",
    requested_ttl=60,
)
```
with:
```python
try:
    token, lease = vault.request_lease(
        subject="research-agent",
        policy_name="customer-readonly",
        requested_ttl=60,
    )
except ApprovalRequired as exc:
    yield {
        "kind": "pending",
        "text": "Approval required. Request queued — waiting for admin@corp.",
        "data": {"request_id": str(exc.pending_request.id)},
    }
    return
```

- [ ] **Step 6: Update `src/personas/app.py`**

Add `ApprovalRequired` to the import at the top:
```python
from src import ApprovalRequired
```

Replace:
```python
token, lease = vault.request_lease(
    subject="etl-job",
    policy_name="customer-readonly",
    requested_ttl=120,
)
```
with:
```python
try:
    token, lease = vault.request_lease(
        subject="etl-job",
        policy_name="customer-readonly",
        requested_ttl=120,
    )
except ApprovalRequired as exc:
    yield {
        "kind": "pending",
        "text": "Approval required. Request queued — waiting for admin@corp.",
        "data": {"request_id": str(exc.pending_request.id)},
    }
    return
```

- [ ] **Step 7: Verify all persona tests pass**

```bash
pytest tests/test_personas.py -v
```

Expected: all PASSED (including 3 new tests)

- [ ] **Step 8: Run full test suite**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add src/personas/human.py src/personas/agent.py src/personas/app.py tests/test_personas.py
git commit -m "feat: catch ApprovalRequired in persona runners, yield pending event"
```

---

## Task 7: Seed + app.py updates

**Files:**
- Modify: `src/seed.py`
- Modify: `app.py`

- [ ] **Step 1: Update `src/seed.py` — set customer-admin requires_approval=True**

Find the `customer-admin` policy in `seed_policies()`. Change it to:

```python
vault.register_policy(
    Policy(
        name="customer-admin",
        description="Read, write, and delete access to customers",
        allowed_ops={"read", "write", "delete"},
        allowed_tables={"customers"},
        max_ttl_seconds=60,
        requires_approval=True,
    )
)
```

- [ ] **Step 2: Update `app.py` — add admin@corp to ACTOR_OPTIONS**

Find line ~13:
```python
ACTOR_OPTIONS = ["alice@corp", "bob@corp", "etl-job", "research-agent"]
```

Replace with:
```python
ACTOR_OPTIONS = ["alice@corp", "bob@corp", "etl-job", "research-agent", "admin@corp"]
```

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/seed.py app.py
git commit -m "feat: enable approval requirement on customer-admin policy, add admin@corp actor"
```

---

## Task 8: JIT Flow UI — handle "pending" kind

**Files:**
- Modify: `pages/2_✅_JIT_Flow.py`

- [ ] **Step 1: Add "pending" to the label map in `_render_stream`**

Find the `label` dict inside `_render_stream` (around line 49):

```python
label = {
    "thought": "[THINK]",
    "action": "[ACTION]",
    "result": "[OK]",
    "error": "[ERROR]",
}.get(kind, "[INFO]")
```

Replace with:

```python
label = {
    "thought": "[THINK]",
    "action": "[ACTION]",
    "result": "[OK]",
    "error": "[ERROR]",
    "pending": "[PENDING]",
}.get(kind, "[INFO]")
```

- [ ] **Step 2: Update run status chip in human_tab**

Find in the `human_tab` block:
```python
st.markdown(
    f"Run Status {status_chip('Completed', 'success')}",
    unsafe_allow_html=True,
)
```

Replace with:
```python
has_pending = any(e.get("kind") == "pending" for e in events)
run_chip = status_chip("Awaiting Approval", "warning") if has_pending else status_chip("Completed", "success")
st.markdown(f"Run Status {run_chip}", unsafe_allow_html=True)
```

- [ ] **Step 3: Update run status chip in app_tab**

Find in the `app_tab` block:
```python
st.markdown(
    f"Run Status {status_chip('Completed', 'success')}",
    unsafe_allow_html=True,
)
```

Replace with:
```python
has_pending = any(e.get("kind") == "pending" for e in events)
run_chip = status_chip("Awaiting Approval", "warning") if has_pending else status_chip("Completed", "success")
st.markdown(f"Run Status {run_chip}", unsafe_allow_html=True)
```

- [ ] **Step 4: Update run status chip in agent_tab**

Find in the `agent_tab` block:
```python
chip = status_chip("Policy Denied", "error") if mode == "Denial Path" else status_chip("Authorized", "success")
st.markdown(f"Run Status {chip}", unsafe_allow_html=True)
```

Replace with:
```python
has_pending = any(e.get("kind") == "pending" for e in events)
if has_pending:
    chip = status_chip("Awaiting Approval", "warning")
elif mode == "Denial Path":
    chip = status_chip("Policy Denied", "error")
else:
    chip = status_chip("Authorized", "success")
st.markdown(f"Run Status {chip}", unsafe_allow_html=True)
```

- [ ] **Step 5: Syntax check and run full test suite**

```bash
python -m py_compile "pages/2_✅_JIT_Flow.py" && pytest -v
```

Expected: clean compile, all PASS

- [ ] **Step 6: Commit**

```bash
git add "pages/2_✅_JIT_Flow.py"
git commit -m "feat: handle pending kind in JIT Flow render stream and status chips"
```

---

## Task 9: Vault Admin UI — Pending Approvals section

**Files:**
- Modify: `pages/3_🔐_Vault_Admin.py`

- [ ] **Step 1: Add Pending Approvals glass card to `pages/3_🔐_Vault_Admin.py`**

Insert the following block after the `end_glass_card()` that closes the Active Leases section (after line ~84), before the Manual Lease Creation `start_glass_card()`:

```python
start_glass_card()
st.markdown("### Pending Approvals")
if actor == "admin@corp":
    pending_requests = vault.list_pending_requests()
    if not pending_requests:
        st.info("No pending approval requests.")
        st.markdown(f"Approval Queue {status_chip('Empty', 'info')}", unsafe_allow_html=True)
    else:
        st.markdown(
            f"Approval Queue {status_chip(f'{len(pending_requests)} Pending', 'warning')}",
            unsafe_allow_html=True,
        )
        for req in pending_requests:
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.markdown(
                    f"**{req.subject}** → `{req.policy_name}` · TTL {req.requested_ttl}s "
                    f"· requested {req.requested_at.strftime('%H:%M:%S UTC')}"
                )
            with col2:
                if st.button("Approve", key=f"approve_{req.id}"):
                    token, lease = vault.approve_request(req.id, reviewed_by="admin@corp")
                    st.success(f"Approved — lease {lease.id}")
                    st.code(token, language="text")
                    st.rerun()
            with col3:
                if st.button("Reject", key=f"reject_{req.id}"):
                    st.session_state[f"rejecting_{req.id}"] = True
                if st.session_state.get(f"rejecting_{req.id}"):
                    reason = st.text_input("Reason", key=f"reason_{req.id}")
                    if st.button("Confirm", key=f"confirm_reject_{req.id}"):
                        vault.reject_request(
                            req.id,
                            reviewed_by="admin@corp",
                            reason=reason or "no reason given",
                        )
                        st.session_state.pop(f"rejecting_{req.id}", None)
                        st.rerun()
else:
    st.info("Switch sidebar actor to admin@corp to review pending requests.")
end_glass_card()
```

- [ ] **Step 2: Syntax check and run full test suite**

```bash
python -m py_compile "pages/3_🔐_Vault_Admin.py" && pytest -v
```

Expected: clean compile, all PASS

- [ ] **Step 3: Commit**

```bash
git add "pages/3_🔐_Vault_Admin.py"
git commit -m "feat: add Pending Approvals section to Vault Admin (admin@corp only)"
```

---

## Final Verification

- [ ] **Run complete test suite**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Syntax-check all modified Python source files**

```bash
python -m py_compile src/models.py src/__init__.py src/approval_queue.py src/vault.py src/seed.py app.py src/personas/human.py src/personas/agent.py src/personas/app.py
```

Expected: no output (clean)

- [ ] **Confirm 9 feature commits**

```bash
git log --oneline -9
```

Expected: 9 commits covering tasks 1–9.
