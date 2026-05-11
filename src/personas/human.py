from __future__ import annotations

import time
from typing import Any, Generator

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

    token, lease = vault.request_lease(subject, policy_name, requested_ttl=60)

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
