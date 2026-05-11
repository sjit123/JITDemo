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
from src.personas import agent, app, human
from src.seed import seed_db, seed_policies
from src.vault import MiniVault


def _setup() -> tuple[MiniVault, DBProxy]:
    conn = sqlite3.connect(":memory:")
    vault = MiniVault()
    seed_policies(vault)
    seed_db(conn)
    vault.lease_manager.start_sweeper(interval=0.1)
    return vault, DBProxy(conn, vault)


def _collect_events(generator) -> list[dict]:
    events = []
    for event in generator:
        assert isinstance(event, dict), "yield must be a dict"
        assert "kind" in event, "event must have 'kind'"
        assert "text" in event, "event must have 'text'"
        assert event["kind"] in ("thought", "action", "result", "error"), f"invalid kind: {event['kind']}"
        events.append(event)
    return events


def test_human_persona_yields_required_contract() -> None:
    vault, proxy = _setup()
    try:
        gen = human.run(
            vault=vault,
            db_proxy=proxy,
            subject="alice@corp",
            policy_name="customer-readonly",
            task_description="Check all customer records",
            think_delay=0.0,
        )
        events = _collect_events(gen)

        assert len(events) >= 6
        kinds = [e["kind"] for e in events]
        assert "thought" in kinds
        assert "action" in kinds
        assert "result" in kinds
    finally:
        vault.lease_manager.stop_sweeper()


def test_human_persona_releases_lease_early() -> None:
    vault, proxy = _setup()
    try:
        gen = human.run(
            vault=vault,
            db_proxy=proxy,
            subject="alice@corp",
            policy_name="customer-readonly",
            task_description="Check all customer records",
            think_delay=0.0,
        )
        events = _collect_events(gen)

        lease_id_str = None
        for event in events:
            if event.get("data", {}).get("lease_id"):
                lease_id_str = event["data"]["lease_id"]
                break

        assert lease_id_str is not None
        from uuid import UUID
        lease_id = UUID(lease_id_str)
        lease = vault.lease_manager.get(lease_id)
        assert lease is not None
        assert lease.revoked is True
        assert lease.revocation_reason == "task complete"
    finally:
        vault.lease_manager.stop_sweeper()


def test_app_persona_yields_required_contract() -> None:
    vault, proxy = _setup()
    try:
        gen = app.run(
            vault=vault,
            db_proxy=proxy,
            think_delay=0.0,
        )
        events = _collect_events(gen)

        assert len(events) >= 4
        kinds = [e["kind"] for e in events]
        assert "thought" in kinds or "action" in kinds
    finally:
        vault.lease_manager.stop_sweeper()


def test_app_persona_releases_lease_early() -> None:
    vault, proxy = _setup()
    try:
        gen = app.run(
            vault=vault,
            db_proxy=proxy,
            think_delay=0.0,
        )
        events = _collect_events(gen)

        lease_id_str = None
        for event in events:
            if event.get("data", {}).get("lease_id"):
                lease_id_str = event["data"]["lease_id"]
                break

        assert lease_id_str is not None
        from uuid import UUID
        lease_id = UUID(lease_id_str)
        lease = vault.lease_manager.get(lease_id)
        assert lease is not None
        assert lease.revoked is True
        assert lease.revocation_reason == "task complete"
    finally:
        vault.lease_manager.stop_sweeper()


def test_agent_happy_path_yields_required_contract() -> None:
    vault, proxy = _setup()
    try:
        gen = agent.run_happy_path(
            vault=vault,
            db_proxy=proxy,
            think_delay=0.0,
        )
        events = _collect_events(gen)

        assert len(events) >= 6
        kinds = [e["kind"] for e in events]
        assert "thought" in kinds
        assert "action" in kinds
        assert "result" in kinds
    finally:
        vault.lease_manager.stop_sweeper()


def test_agent_denial_path_yields_error_without_raising() -> None:
    vault, proxy = _setup()
    try:
        gen = agent.run_denial_path(
            vault=vault,
            db_proxy=proxy,
            think_delay=0.0,
        )

        events = []
        raised = False
        try:
            for event in gen:
                assert isinstance(event, dict), "yield must be a dict"
                assert "kind" in event, "event must have 'kind'"
                assert "text" in event, "event must have 'text'"
                events.append(event)
        except StopIteration:
            pass
        except Exception:
            raised = True
            raise

        assert not raised, "generator should not raise"
        assert len(events) >= 1

        error_events = [e for e in events if e["kind"] == "error"]
        assert len(error_events) >= 1
        assert "operation 'write' not allowed" in error_events[0]["text"]

        access_denied = [
            event for event in vault.audit_log.tail(100) 
            if event.action == "access_denied"
        ]
        assert len(access_denied) >= 1
    finally:
        vault.lease_manager.stop_sweeper()
