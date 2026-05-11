from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any, Callable

from src import AccessDenied
from src.models import AuditEvent, TokenScope
from src.vault import MiniVault


class DBProxy:
    """Security boundary that enforces token scope before every DB operation."""

    def __init__(self, conn: sqlite3.Connection, vault: MiniVault) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._vault = vault

    def read(self, table: str, token: str, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        op = "read"
        where = where or {}

        def do_read() -> list[dict[str, Any]]:
            where_sql, params = _build_where_clause(where)
            # SQLite does not support placeholders for identifiers. This interpolation is
            # safe because table is allowlisted from vault-issued token scope before query.
            sql = f"SELECT * FROM {table}{where_sql}"
            cursor = self._conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

        return self._run_with_audit(op=op, table=table, token=token, action=do_read)

    def insert(self, table: str, row: dict[str, Any], token: str) -> int:
        op = "write"

        def do_insert() -> int:
            if not row:
                raise ValueError("insert requires at least one column")
            columns = list(row.keys())
            placeholders = ", ".join(["?"] * len(columns))
            column_sql = ", ".join(columns)
            # See read(): table interpolation is safe after scope allowlist check.
            sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
            cursor = self._conn.execute(sql, [row[column] for column in columns])
            self._conn.commit()
            return int(cursor.lastrowid)

        return self._run_with_audit(op=op, table=table, token=token, action=do_insert)

    def update(
        self,
        table: str,
        set_values: dict[str, Any],
        where: dict[str, Any],
        token: str,
    ) -> int:
        op = "write"

        def do_update() -> int:
            if not set_values:
                raise ValueError("update requires at least one set value")
            if not where:
                raise ValueError("update requires at least one condition")

            set_columns = list(set_values.keys())
            set_sql = ", ".join(f"{column} = ?" for column in set_columns)
            where_sql, where_params = _build_where_clause(where)
            # See read(): table interpolation is safe after scope allowlist check.
            sql = f"UPDATE {table} SET {set_sql}{where_sql}"
            params = [set_values[column] for column in set_columns] + where_params
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return int(cursor.rowcount)

        return self._run_with_audit(op=op, table=table, token=token, action=do_update)

    def delete(self, table: str, where: dict[str, Any], token: str) -> int:
        op = "delete"

        def do_delete() -> int:
            if not where:
                raise ValueError("delete requires at least one condition")
            where_sql, params = _build_where_clause(where)
            # See read(): table interpolation is safe after scope allowlist check.
            sql = f"DELETE FROM {table}{where_sql}"
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return int(cursor.rowcount)

        return self._run_with_audit(op=op, table=table, token=token, action=do_delete)

    def _run_with_audit(
        self,
        op: str,
        table: str,
        token: str,
        action: Callable[[], Any],
    ) -> Any:
        actor = "db_proxy"
        try:
            scope = self._vault.validate(token)
            _enforce_scope(scope, op=op, table=table)
            result = action()
            self._vault.audit_log.append(
                AuditEvent(
                    timestamp=datetime.now(UTC),
                    actor=actor,
                    action="access_granted",
                    resource=table,
                    outcome="success",
                    details={"op": op, "table": table},
                )
            )
            return result
        except Exception as exc:  # noqa: BLE001
            self._vault.audit_log.append(
                AuditEvent(
                    timestamp=datetime.now(UTC),
                    actor=actor,
                    action="access_denied",
                    resource=table,
                    outcome="denied",
                    details={"reason": str(exc), "op": op, "table": table},
                )
            )
            raise


def _enforce_scope(scope: TokenScope, op: str, table: str) -> None:
    if op not in scope.ops:
        raise AccessDenied(f"operation '{op}' not allowed")
    if table not in scope.tables:
        raise AccessDenied(f"table '{table}' not allowed")


def _build_where_clause(where: dict[str, Any]) -> tuple[str, list[Any]]:
    if not where:
        return "", []

    columns = list(where.keys())
    sql = " AND ".join(f"{column} = ?" for column in columns)
    return f" WHERE {sql}", [where[column] for column in columns]
