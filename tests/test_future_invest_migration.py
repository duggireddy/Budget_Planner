"""Ensure client_future_investments exists on legacy SQLite databases."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest


def test_sqlite_migration_adds_future_investments_table(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(db_path))

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE client_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            monthly_payment REAL NOT NULL DEFAULT 0,
            interest_rate_annual REAL NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.close()

    assert (
        sqlite3.connect(db_path)
        .execute(
            "SELECT name FROM sqlite_master WHERE name='client_future_investments'"
        )
        .fetchone()
        is None
    )

    import app.database as db_mod

    monkeypatch.setattr(db_mod, "SQLITE_PATH", str(db_path))
    db_mod.init_db()

    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE name='client_future_investments'"
    ).fetchone()
    conn.close()
