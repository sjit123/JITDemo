# Approval Workflow Design

**Date:** 2026-05-10
**Status:** Approved

## Overview

Add a human-in-the-loop approval workflow for high-privilege lease requests. When a policy has `requires_approval=True`, `request_lease()` raises `ApprovalRequired` instead of issuing a lease. The request lands in an in-memory queue. A designated approver (`admin@corp`) reviews it in Vault Admin and either approves (lease issues) or rejects (request closed, no lease). Every state transition is audited.

Scope: `customer-admin` is the only seeded policy with approval required. All other policies issue leases immediately as before.

---

## Data Model

### New: `PendingRequest` (`src/models.py`)

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
```

All datetime fields must be timezone-aware UTC (enforced via `field_validator`, same pattern as `Lease`).

### Modified: `AuditEvent.action` (`src/models.py`)

Three new literals added to the discriminated union:

- `"approval_requested"` — emitted when a pending request is created
- `"approval_granted"` — emitted when admin approves
- `"approval_rejected"` — emitted when admin rejects

### New: `ApprovalRequired` exception (`src/__init__.py`)

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.models import PendingRequest

class ApprovalRequired(Exception):
    def __init__(self, pending_request: PendingRequest) -> None:
        self.pending_request = pending_request
        super().__init__("approval required")
```

`TYPE_CHECKING` guard avoids circular import — `src/models.py` already imports from `src/__init__.py`. The annotation is only evaluated by type checkers, not at runtime.

---

## ApprovalQueue (`src/approval_queue.py`)

New module. Thread-safe in-memory store for pending requests.

```
ApprovalQueue
  _requests: dict[UUID, PendingRequest]
  _lock: threading.RLock

  add(request: PendingRequest) -> None
  get(request_id: UUID) -> PendingRequest | None
  approve(request_id, reviewed_by) -> PendingRequest | None
  reject(request_id, reviewed_by, reason) -> PendingRequest | None
  list_pending() -> list[PendingRequest]
```

`approve()` and `reject()` use `model_copy(update={...})` — immutable state transitions, never mutate in place. `list_pending()` filters to `status == "pending"`.

No background sweeper. Pending requests do not expire. TTL enforcement happens at lease issuance after approval — the issued lease TTL is still bounded by `policy.max_ttl_seconds`.

---

## MiniVault Changes (`src/vault.py`)

### `__init__`

Compose `ApprovalQueue`:
```python
self._approval_queue = ApprovalQueue()
```

### `request_lease()` — approval intercept

After policy lookup, before `_engine.issue()`:

```python
if policy.requires_approval:
    pending = PendingRequest(
        id=uuid4(),
        subject=subject,
        policy_name=policy_name,
        requested_ttl=requested_ttl,
        requested_at=datetime.now(UTC),
    )
    self._approval_queue.add(pending)
    self._audit_log.append(AuditEvent(
        timestamp=datetime.now(UTC),
        actor=subject,
        action="approval_requested",
        outcome="success",
        resource=policy_name,
        details={"request_id": str(pending.id), "requested_ttl": requested_ttl},
    ))
    raise ApprovalRequired(pending)
```

Non-approval path is unchanged.

### New: `approve_request(request_id, reviewed_by)` → `tuple[str, Lease]`

1. Call `_approval_queue.approve(request_id, reviewed_by)`
2. Look up policy by `pending.policy_name`
3. Call `_engine.issue(pending.subject, policy, pending.requested_ttl)`
4. Emit `"approval_granted"` audit event
5. Return `(token, lease)`

Raises `AccessDenied("request not found")` if `request_id` is unknown or already reviewed. Raises `PolicyNotFound` if the policy named in the request no longer exists at approval time (defensive — policies are static in the demo but the guard keeps the contract honest).

### New: `reject_request(request_id, reviewed_by, reason)` → `PendingRequest`

1. Call `_approval_queue.reject(request_id, reviewed_by, reason)`
2. Emit `"approval_rejected"` audit event with `rejection_reason`
3. Return updated `PendingRequest`

Raises `AccessDenied("request not found")` if unknown or already reviewed.

### New: `list_pending_requests()` → `list[PendingRequest]`

Delegates to `_approval_queue.list_pending()`.

---

## Persona Changes (`src/personas/`)

All three persona runners (`human.py`, `agent.py`, `app.py`) wrap `vault.request_lease()` in `try/except ApprovalRequired`:

```python
try:
    token, lease = vault.request_lease(subject, policy_name, requested_ttl)
except ApprovalRequired as exc:
    yield {
        "kind": "pending",
        "text": "Approval required. Request queued — waiting for admin@corp.",
        "data": {"request_id": str(exc.pending_request.id)},
    }
    return
```

Generator returns immediately after yielding the `"pending"` event. No DB access attempted (no lease was issued).

---

## Seed Changes (`src/seed.py`)

`customer-admin` policy updated:

```python
Policy(
    name="customer-admin",
    ...
    requires_approval=True,  # was False
)
```

---

## UI Changes

### `app.py`

Add `"admin@corp"` to `ACTOR_OPTIONS`:

```python
ACTOR_OPTIONS = ["alice@corp", "bob@corp", "etl-job", "research-agent", "admin@corp"]
```

### Vault Admin (`pages/3_🔐_Vault_Admin.py`)

New "Pending Approvals" section, rendered only when `actor == "admin@corp"`.

For each pending request, display: subject, policy, requested TTL, requested_at.

- **Approve button**: calls `vault.approve_request(request_id, reviewed_by="admin@corp")`, displays granted lease ID and token, refreshes page.
- **Reject button**: reveals a `st.text_input` for rejection reason, then a confirm button that calls `vault.reject_request(request_id, "admin@corp", reason)`.

Non-admin actors see no pending approvals UI.

### JIT Flow (`pages/2_✅_JIT_Flow.py`)

`_render_stream()` adds handling for `"pending"` kind:

```python
"pending": "[PENDING]",
```

Rendered with `status_chip("Awaiting Approval", "warning")` inline.

---

## Audit Trail

Complete sequence for an approved `customer-admin` request:

| Action | Actor | Outcome |
|---|---|---|
| `approval_requested` | alice@corp | success |
| `approval_granted` | admin@corp | success |
| `lease_granted` | alice@corp | success |
| `access_granted` | db_proxy | success |
| `lease_revoked` | vault | success |

For a rejected request:

| Action | Actor | Outcome |
|---|---|---|
| `approval_requested` | alice@corp | success |
| `approval_rejected` | admin@corp | denied |

---

## What's Out of Scope

- Pending request expiry (no TTL on the request itself)
- Multiple approvers or quorum
- Approval notifications (no push/websocket)
- Persisting approval state across restarts (consistent with rest of demo)
