from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import AccessDenied
from src.db_proxy import DBProxy
from src.seed import seed_db, seed_policies
from src.vault import MiniVault


def _setup() -> tuple[MiniVault, DBProxy]:
    conn = sqlite3.connect(":memory:")
    vault = MiniVault()
    seed_policies(vault)
    seed_db(conn)
    return vault, DBProxy(conn, vault)


def test_scope_enforcement_wrong_op_logs_access_denied() -> None:
    vault, proxy = _setup()
    token, _lease = vault.request_lease("alice@corp", "customer-readonly", requested_ttl=60)

    with pytest.raises(AccessDenied, match="operation 'write' not allowed"):
        proxy.insert(
            table="customers",
            row={
                "name": "New Person",
                "email": "new@example.com",
                "plan": "basic",
                "balance": 0.0,
            },
            token=token,
        )

    denied = [event for event in vault.audit_log.tail(50) if event.action == "access_denied"]
    assert denied
    last = denied[-1]
    assert last.details["op"] == "write"
    assert last.details["table"] == "customers"
    assert "operation 'write' not allowed" in last.details["reason"]


def test_scope_enforcement_wrong_table_on_existing_table() -> None:
    vault, proxy = _setup()
    token, _lease = vault.request_lease("alice@corp", "customer-readonly", requested_ttl=60)

    with pytest.raises(AccessDenied, match="table 'internal_secrets' not allowed"):
        proxy.read(table="internal_secrets", token=token)

    denied = [event for event in vault.audit_log.tail(50) if event.action == "access_denied"]
    assert denied
    last = denied[-1]
    assert last.details == {
        "reason": "table 'internal_secrets' not allowed",
        "op": "read",
        "table": "internal_secrets",
    }


def test_delete_requires_where_before_db_mutation_and_is_audited() -> None:
    vault, proxy = _setup()
    token, _lease = vault.request_lease("alice@corp", "customer-admin", requested_ttl=60)

    with pytest.raises(ValueError, match="delete requires at least one condition"):
        proxy.delete(table="customers", where={}, token=token)

    denied = [event for event in vault.audit_log.tail(50) if event.action == "access_denied"]
    assert denied
    last = denied[-1]
    assert last.details == {
        "reason": "delete requires at least one condition",
        "op": "delete",
        "table": "customers",
    }


def test_successful_read_emits_access_granted() -> None:
    vault, proxy = _setup()
    token, _lease = vault.request_lease("alice@corp", "customer-readonly", requested_ttl=60)

    rows = proxy.read(table="customers", token=token, where={"id": 1})
    assert len(rows) == 1

    granted = [event for event in vault.audit_log.tail(50) if event.action == "access_granted"]
    assert granted
    last = granted[-1]
    assert last.details["op"] == "read"
    assert last.details["table"] == "customers"
