from __future__ import annotations

import sqlite3

from src.models import Policy
from src.vault import MiniVault


def seed_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            plan TEXT NOT NULL,
            balance REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS internal_secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            secret_value TEXT NOT NULL
        )
        """
    )

    customers = [
        ("Alice Brown", "alice@example.com", "pro", 120.50),
        ("Bob Chen", "bob@example.com", "basic", -15.25),
        ("Carla Diaz", "carla@example.com", "enterprise", 5200.00),
        ("Dev Patel", "dev@example.com", "basic", 0.00),
        ("Eve Singh", "eve@example.com", "pro", -4.75),
        ("Fay Li", "fay@example.com", "pro", 78.20),
        ("Gabe Ross", "gabe@example.com", "enterprise", 910.10),
        ("Hana Kim", "hana@example.com", "basic", 12.00),
        ("Ian Cole", "ian@example.com", "pro", 65.90),
        ("Jade Noor", "jade@example.com", "basic", -2.00),
        ("Kian Park", "kian@example.com", "pro", 188.15),
        ("Lia Meyer", "lia@example.com", "enterprise", 2300.00),
        ("Moe Quinn", "moe@example.com", "basic", 4.10),
        ("Nia Wu", "nia@example.com", "pro", 0.30),
        ("Omar Hale", "omar@example.com", "basic", 9.99),
        ("Pia Stone", "pia@example.com", "enterprise", 1450.00),
        ("Ravi Das", "ravi@example.com", "pro", -9.40),
        ("Sara Voss", "sara@example.com", "basic", 1.25),
        ("Tao Lin", "tao@example.com", "pro", 302.00),
        ("Uma Gray", "uma@example.com", "enterprise", 4880.75),
    ]

    conn.executemany(
        "INSERT INTO customers (name, email, plan, balance) VALUES (?, ?, ?, ?)",
        customers,
    )
    conn.executemany(
        "INSERT INTO internal_secrets (key, secret_value) VALUES (?, ?)",
        [
            ("prod_db_password", "not-for-customers"),
            ("admin_api_token", "rotate-me-now"),
        ],
    )
    conn.commit()


def seed_policies(vault: MiniVault) -> None:
    vault.register_policy(
        Policy(
            name="customer-readonly",
            description="Read-only access to customers",
            allowed_ops={"read"},
            allowed_tables={"customers"},
            max_ttl_seconds=300,
        )
    )
    vault.register_policy(
        Policy(
            name="customer-writer",
            description="Read and write access to customers",
            allowed_ops={"read", "write"},
            allowed_tables={"customers"},
            max_ttl_seconds=120,
        )
    )
    vault.register_policy(
        Policy(
            name="customer-admin",
            description="Read, write, and delete access to customers",
            allowed_ops={"read", "write", "delete"},
            allowed_tables={"customers"},
            max_ttl_seconds=60,
        )
    )
