"""Local persistence — SQLite by default (no Docker required)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from app.config import (
    CLIENT_COLUMNS,
    DATA_DIR,
    DB_BACKEND,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
    SQLITE_PATH,
)

_USE_MYSQL = DB_BACKEND == "mysql"

CLIENT_SELECT = (
    "id, name, company_name, contact_person, email, phone, "
    "street, postal_code, city, country, tax_id, vat_id, iban, notes, created_at"
)


def db_label() -> str:
    return "mysql" if _USE_MYSQL else "sqlite"


@contextmanager
def get_connection() -> Generator[Any, None, None]:
    ctx = _mysql_connection() if _USE_MYSQL else _sqlite_connection()
    with ctx as conn:
        yield conn


@contextmanager
def _sqlite_connection() -> Generator[sqlite3.Connection, None, None]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _mysql_connection() -> Generator[Any, None, None]:
    import pymysql
    from pymysql.cursors import DictCursor

    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ph() -> str:
    return "%s" if _USE_MYSQL else "?"


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(row)


def init_db() -> None:
    if _USE_MYSQL:
        _init_mysql()
    else:
        _init_sqlite()


def _init_sqlite() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _sqlite_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company_name TEXT NOT NULL DEFAULT '',
                contact_person TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                street TEXT NOT NULL DEFAULT '',
                postal_code TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT 'Germany',
                tax_id TEXT NOT NULL DEFAULT '',
                vat_id TEXT NOT NULL DEFAULT '',
                iban TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(name)
            );
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                monatlich_mode TEXT NOT NULL DEFAULT 'div12',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(client_id, year),
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                budget_id INTEGER NOT NULL,
                line_key TEXT NOT NULL,
                month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
                amount REAL NOT NULL DEFAULT 0,
                UNIQUE(budget_id, line_key, month),
                FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS category_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_label TEXT NOT NULL UNIQUE,
                line_key TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                message TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
            );
            """
        )
        _sqlite_migrate_client_columns(conn)
        _sqlite_fix_budget_schema(conn)


def _sqlite_fix_budget_schema(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='budgets'"
    ).fetchone()
    if not cur:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(budgets)").fetchall()}
    if "client_id" in cols:
        return
    conn.executescript(
        """
        DROP TABLE IF EXISTS entries;
        DROP TABLE IF EXISTS budgets;
        CREATE TABLE budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            monatlich_mode TEXT NOT NULL DEFAULT 'div12',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(client_id, year),
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        );
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER NOT NULL,
            line_key TEXT NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            amount REAL NOT NULL DEFAULT 0,
            UNIQUE(budget_id, line_key, month),
            FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        "UPDATE budgets SET monatlich_mode = 'div12' WHERE monatlich_mode = 'motion_div12'"
    )


def _sqlite_migrate_client_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(clients)")
    existing = {r[1] for r in cur.fetchall()}
    alters = {
        "company_name": "TEXT NOT NULL DEFAULT ''",
        "contact_person": "TEXT NOT NULL DEFAULT ''",
        "email": "TEXT NOT NULL DEFAULT ''",
        "phone": "TEXT NOT NULL DEFAULT ''",
        "street": "TEXT NOT NULL DEFAULT ''",
        "postal_code": "TEXT NOT NULL DEFAULT ''",
        "city": "TEXT NOT NULL DEFAULT ''",
        "country": "TEXT NOT NULL DEFAULT 'Germany'",
        "tax_id": "TEXT NOT NULL DEFAULT ''",
        "vat_id": "TEXT NOT NULL DEFAULT ''",
        "iban": "TEXT NOT NULL DEFAULT ''",
        "notes": "TEXT NOT NULL DEFAULT ''",
    }
    for col, typedef in alters.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE clients ADD COLUMN {col} {typedef}")


def _init_mysql() -> None:
    import pymysql

    root = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset="utf8mb4",
    )
    try:
        with root.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        root.close()

    with _mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    company_name VARCHAR(255) NOT NULL DEFAULT '',
                    contact_person VARCHAR(255) NOT NULL DEFAULT '',
                    email VARCHAR(255) NOT NULL DEFAULT '',
                    phone VARCHAR(64) NOT NULL DEFAULT '',
                    street VARCHAR(255) NOT NULL DEFAULT '',
                    postal_code VARCHAR(32) NOT NULL DEFAULT '',
                    city VARCHAR(128) NOT NULL DEFAULT '',
                    country VARCHAR(128) NOT NULL DEFAULT 'Germany',
                    tax_id VARCHAR(64) NOT NULL DEFAULT '',
                    vat_id VARCHAR(64) NOT NULL DEFAULT '',
                    iban VARCHAR(64) NOT NULL DEFAULT '',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_client_name (name)
                ) ENGINE=InnoDB
                """
            )
            for col, typedef in [
                ("company_name", "VARCHAR(255) NOT NULL DEFAULT ''"),
                ("contact_person", "VARCHAR(255) NOT NULL DEFAULT ''"),
                ("email", "VARCHAR(255) NOT NULL DEFAULT ''"),
                ("phone", "VARCHAR(64) NOT NULL DEFAULT ''"),
                ("street", "VARCHAR(255) NOT NULL DEFAULT ''"),
                ("postal_code", "VARCHAR(32) NOT NULL DEFAULT ''"),
                ("city", "VARCHAR(128) NOT NULL DEFAULT ''"),
                ("country", "VARCHAR(128) NOT NULL DEFAULT 'Germany'"),
                ("tax_id", "VARCHAR(64) NOT NULL DEFAULT ''"),
                ("vat_id", "VARCHAR(64) NOT NULL DEFAULT ''"),
                ("iban", "VARCHAR(64) NOT NULL DEFAULT ''"),
                ("notes", "TEXT"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE clients ADD COLUMN {col} {typedef}")
                except Exception:
                    pass
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS budgets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    client_id INT NOT NULL,
                    year INT NOT NULL,
                    monatlich_mode VARCHAR(20) DEFAULT 'div12',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_client_year (client_id, year),
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    budget_id INT NOT NULL,
                    line_key VARCHAR(128) NOT NULL,
                    month INT NOT NULL,
                    amount DOUBLE NOT NULL DEFAULT 0,
                    UNIQUE KEY uq_budget_line_month (budget_id, line_key, month),
                    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
                    CHECK (month BETWEEN 1 AND 12)
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS category_mappings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    file_label VARCHAR(512) NOT NULL,
                    line_key VARCHAR(128) NOT NULL,
                    UNIQUE KEY uq_file_label (file_label)
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS import_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    client_id INT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message TEXT NOT NULL,
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
                ) ENGINE=InnoDB
                """
            )


def _normalize_client_payload(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in CLIENT_COLUMNS:
        val = data.get(col, "")
        out[col] = str(val).strip() if val is not None else ""
    if not out["name"]:
        raise ValueError("Client name is required")
    if not out["country"]:
        out["country"] = "Germany"
    return out


def list_clients() -> list[dict[str, Any]]:
    ph = _ph()
    sql = f"""
        SELECT c.id, c.name, c.company_name, c.contact_person, c.email, c.phone,
               c.street, c.postal_code, c.city, c.country, c.tax_id, c.vat_id,
               c.iban, c.notes, c.created_at,
               COUNT(DISTINCT b.year) AS budget_years
        FROM clients c
        LEFT JOIN budgets b ON b.client_id = c.id
        GROUP BY c.id
        ORDER BY c.name
    """
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(sql)
                return [_row_to_dict(r) for r in cur.fetchall()]
        rows = conn.execute(sql).fetchall()
        return [_row_to_dict(r) for r in rows]


def create_client(data: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_client_payload(data)
    cols = ", ".join(CLIENT_COLUMNS)
    placeholders = ", ".join([_ph()] * len(CLIENT_COLUMNS))
    values = [payload[c] for c in CLIENT_COLUMNS]
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO clients ({cols}) VALUES ({placeholders})",
                    values,
                )
                cid = cur.lastrowid
                cur.execute(f"SELECT {CLIENT_SELECT} FROM clients WHERE id = %s", (cid,))
                return _row_to_dict(cur.fetchone())
        cur = conn.execute(
            f"INSERT INTO clients ({cols}) VALUES ({placeholders})",
            values,
        )
        cid = cur.lastrowid
        row = conn.execute(
            f"SELECT {CLIENT_SELECT} FROM clients WHERE id = ?", (cid,)
        ).fetchone()
        return _row_to_dict(row)


def update_client(client_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    payload = _normalize_client_payload(data)
    sets = ", ".join(f"{c} = {_ph()}" for c in CLIENT_COLUMNS)
    values = [payload[c] for c in CLIENT_COLUMNS] + [client_id]
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE clients SET {sets} WHERE id = %s", values)
                if cur.rowcount == 0:
                    return None
                cur.execute(f"SELECT {CLIENT_SELECT} FROM clients WHERE id = %s", (client_id,))
                return _row_to_dict(cur.fetchone())
        cur = conn.execute(f"UPDATE clients SET {sets} WHERE id = ?", values)
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            f"SELECT {CLIENT_SELECT} FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        return _row_to_dict(row)


def get_client(client_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {CLIENT_SELECT} FROM clients WHERE id = %s", (client_id,))
                row = cur.fetchone()
                return _row_to_dict(row) if row else None
        row = conn.execute(
            f"SELECT {CLIENT_SELECT} FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None


def delete_client(client_id: int) -> bool:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
                return cur.rowcount > 0
        cur = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        return cur.rowcount > 0


def get_or_create_budget(client_id: int, year: int = 2026) -> int:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM budgets WHERE client_id = %s AND year = %s",
                    (client_id, year),
                )
                row = cur.fetchone()
                if row:
                    return int(row["id"])
                cur.execute(
                    "INSERT INTO budgets (client_id, year) VALUES (%s, %s)",
                    (client_id, year),
                )
                return int(cur.lastrowid)
        row = conn.execute(
            "SELECT id FROM budgets WHERE client_id = ? AND year = ?",
            (client_id, year),
        ).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO budgets (client_id, year) VALUES (?, ?)",
            (client_id, year),
        )
        return int(cur.lastrowid)


def get_settings(budget_id: int) -> dict:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute("SELECT monatlich_mode FROM budgets WHERE id = %s", (budget_id,))
                row = cur.fetchone()
        else:
            row = conn.execute(
                "SELECT monatlich_mode FROM budgets WHERE id = ?", (budget_id,)
            ).fetchone()
    if not row:
        return {"monatlich_mode": "div12"}
    mode = row["monatlich_mode"] if isinstance(row, dict) else row[0]
    return {"monatlich_mode": mode or "div12"}


def set_monatlich_mode(budget_id: int, mode: str) -> None:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE budgets SET monatlich_mode = %s WHERE id = %s",
                    (mode, budget_id),
                )
        else:
            conn.execute(
                "UPDATE budgets SET monatlich_mode = ? WHERE id = ?",
                (mode, budget_id),
            )


def load_entries(budget_id: int) -> dict[str, list[float]]:
    from app.categories import ALL_EDITABLE_KEYS

    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT line_key, month, amount FROM entries WHERE budget_id = %s",
                    (budget_id,),
                )
                rows = cur.fetchall()
        else:
            rows = conn.execute(
                "SELECT line_key, month, amount FROM entries WHERE budget_id = ?",
                (budget_id,),
            ).fetchall()

    entries: dict[str, list[float]] = {k: [0.0] * 12 for k in ALL_EDITABLE_KEYS}
    for row in rows:
        r = _row_to_dict(row)
        key = r["line_key"]
        if key not in entries:
            entries[key] = [0.0] * 12
        entries[key][int(r["month"]) - 1] = float(r["amount"])
    return entries


def upsert_entry(budget_id: int, line_key: str, month: int, amount: float) -> None:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO entries (budget_id, line_key, month, amount)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE amount = VALUES(amount)
                    """,
                    (budget_id, line_key, month, amount),
                )
        else:
            conn.execute(
                """
                INSERT INTO entries (budget_id, line_key, month, amount)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(budget_id, line_key, month) DO UPDATE SET amount = excluded.amount
                """,
                (budget_id, line_key, month, amount),
            )


def bulk_upsert(
    budget_id: int, line_key: str, start_month: int, end_month: int, amount: float
) -> None:
    for m in range(start_month, end_month + 1):
        upsert_entry(budget_id, line_key, m, amount)


def log_import(message: str, client_id: int | None = None) -> None:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO import_log (client_id, message) VALUES (%s, %s)",
                    (client_id, message),
                )
        else:
            conn.execute(
                "INSERT INTO import_log (client_id, message) VALUES (?, ?)",
                (client_id, message),
            )


def get_import_log(limit: int = 50) -> list[str]:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT message FROM import_log ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
                return [r["message"] for r in cur.fetchall()]
        rows = conn.execute(
            "SELECT message FROM import_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r[0] for r in rows]


def save_mapping(file_label: str, line_key: str) -> None:
    label = file_label.strip()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO category_mappings (file_label, line_key) VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE line_key = VALUES(line_key)
                    """,
                    (label, line_key),
                )
        else:
            conn.execute(
                """
                INSERT INTO category_mappings (file_label, line_key) VALUES (?, ?)
                ON CONFLICT(file_label) DO UPDATE SET line_key = excluded.line_key
                """,
                (label, line_key),
            )


def get_mappings() -> dict[str, str]:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute("SELECT file_label, line_key FROM category_mappings")
                return {r["file_label"]: r["line_key"] for r in cur.fetchall()}
        rows = conn.execute("SELECT file_label, line_key FROM category_mappings").fetchall()
        return {r[0]: r[1] for r in rows}
