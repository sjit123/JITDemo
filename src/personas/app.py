from __future__ import annotations

import time
from typing import Any, Generator

from src.db_proxy import DBProxy
from src.vault import MiniVault


def run(
    vault: MiniVault,
    db_proxy: DBProxy,
    think_delay: float = 0.0,
) -> Generator[dict[str, Any], None, None]:
    """A scheduled batch job: request, read, analyze, release."""

    time.sleep(think_delay)
    yield {
        "kind": "thought",
        "text": "Nightly batch: analyzing customer metrics",
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "Requesting customer-readonly lease",
    }

    token, lease = vault.request_lease(
        subject="etl-job",
        policy_name="customer-readonly",
        requested_ttl=120,
    )

    yield {
        "kind": "result",
        "text": f"✓ Lease granted for {lease.seconds_remaining:.0f}s",
        "data": {"lease_id": str(lease.id)},
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "Reading all customer records",
    }

    rows = db_proxy.read(table="customers", token=token)

    yield {
        "kind": "result",
        "text": f"✓ Retrieved {len(rows)} records",
        "data": {"total": len(rows)},
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": "Computing metrics: negative-balance accounts",
    }

    negative_balance_count = sum(1 for row in rows if row["balance"] < 0)
    avg_balance = sum(row["balance"] for row in rows) / len(rows) if rows else 0.0

    yield {
        "kind": "result",
        "text": f"✓ Metrics: {negative_balance_count} accounts with negative balance, avg balance ${avg_balance:.2f}",
        "data": {
            "negative_balance_count": negative_balance_count,
            "avg_balance": avg_balance,
        },
    }

    time.sleep(think_delay)
    yield {
        "kind": "action",
        "text": f"Releasing lease early ({lease.seconds_remaining:.0f}s remaining)",
    }

    vault.revoke(lease.id, reason="task complete")

    yield {
        "kind": "result",
        "text": "✓ Batch job finished and lease released",
        "data": {"released_at_seconds_remaining": lease.seconds_remaining},
    }
