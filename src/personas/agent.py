from __future__ import annotations

import time
from typing import Any, Generator

from src import AccessDenied
from src.db_proxy import DBProxy
from src.vault import MiniVault


def run_happy_path(
    vault: MiniVault,
    db_proxy: DBProxy,
    think_delay: float = 0.0,
) -> Generator[dict[str, Any], None, None]:
    """Agent analyzes a task and performs it correctly."""

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": "🤔 Task: Fetch all customers with negative balance",
    }

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": "🤔 Required access: read customers table only",
    }

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": "🤔 Matching policy: customer-readonly ✓",
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "▶ Requesting customer-readonly lease",
    }

    token, lease = vault.request_lease(
        subject="research-agent",
        policy_name="customer-readonly",
        requested_ttl=60,
    )

    yield {
        "kind": "result",
        "text": f"✓ Granted for {lease.seconds_remaining:.0f}s",
        "data": {"lease_id": str(lease.id)},
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "▶ Reading customers...",
    }

    rows = db_proxy.read(table="customers", token=token)

    negative = [row for row in rows if row["balance"] < 0]

    yield {
        "kind": "result",
        "text": f"✓ Found {len(negative)} customer(s) with balance < $0",
        "data": {"results": len(negative), "total_customers": len(rows)},
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": f"▶ Releasing lease ({lease.seconds_remaining:.0f}s remaining)",
    }

    vault.revoke(lease.id, reason="task complete")

    yield {
        "kind": "result",
        "text": "✓ Task complete, lease released",
        "data": {"result_count": len(negative)},
    }


def run_denial_path(
    vault: MiniVault,
    db_proxy: DBProxy,
    think_delay: float = 0.0,
) -> Generator[dict[str, Any], None, None]:
    """Agent picks the wrong policy and attempts an unauthorized write."""

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": "🤔 Task: Flag customers with negative balance and zero them out",
    }

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": "🤔 Required access: read + write customers table",
    }

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": "🤔 Wait, let me pick customer-readonly... (wrong!)",
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "▶ Requesting customer-readonly lease",
    }

    token, lease = vault.request_lease(
        subject="research-agent",
        policy_name="customer-readonly",
        requested_ttl=60,
    )

    yield {
        "kind": "result",
        "text": f"✓ Granted for {lease.seconds_remaining:.0f}s",
        "data": {"lease_id": str(lease.id)},
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "▶ Reading customers...",
    }

    rows = db_proxy.read(table="customers", token=token)

    negative = [row for row in rows if row["balance"] < 0]

    yield {
        "kind": "result",
        "text": f"✓ Found {len(negative)} negative balances",
        "data": {"negative_count": len(negative)},
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": f"▶ Attempting to update balance for {len(negative)} customer(s)...",
    }

    try:
        for row in negative:
            db_proxy.update(
                table="customers",
                set_values={"balance": 0.0},
                where={"id": row["id"]},
                token=token,
            )
    except AccessDenied as exc:
        yield {
            "kind": "error",
            "text": f"✗ Access denied: {str(exc)}",
            "data": {"error": str(exc), "attempted_customers": len(negative)},
        }
        vault.revoke(lease.id, reason="access denied")
        return

    yield {
        "kind": "result",
        "text": f"✓ Updated {len(negative)} balance(s) to zero",
        "data": {"updated_count": len(negative)},
    }
