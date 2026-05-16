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
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
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
    _init_balance_tables()


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


def _init_balance_tables() -> None:
    if _USE_MYSQL:
        with _mysql_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS client_assets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        client_id INT NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        asset_type VARCHAR(32) NOT NULL DEFAULT 'other',
                        amount DOUBLE NOT NULL DEFAULT 0,
                        notes TEXT,
                        sort_order INT NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS client_debts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        client_id INT NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        amount DOUBLE NOT NULL DEFAULT 0,
                        monthly_payment DOUBLE NOT NULL DEFAULT 0,
                        interest_rate_annual DOUBLE NOT NULL DEFAULT 0,
                        notes TEXT,
                        sort_order INT NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS client_future_investments (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        client_id INT NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        investment_type VARCHAR(32) NOT NULL DEFAULT 'other',
                        current_amount DOUBLE NOT NULL DEFAULT 0,
                        target_amount DOUBLE NOT NULL DEFAULT 0,
                        monthly_contribution DOUBLE NOT NULL DEFAULT 0,
                        expected_return_annual DOUBLE NOT NULL DEFAULT 0,
                        target_year INT NULL,
                        notes TEXT,
                        sort_order INT NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB
                    """
                )
                _mysql_migrate_debt_columns(cur)
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS custom_lines (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        budget_id INT NOT NULL,
                        section_id VARCHAR(64) NOT NULL,
                        line_key VARCHAR(128) NOT NULL,
                        label_de VARCHAR(255) NOT NULL,
                        label_en VARCHAR(255) NOT NULL,
                        line_type VARCHAR(16) NOT NULL DEFAULT 'expense',
                        sort_order INT NOT NULL DEFAULT 0,
                        UNIQUE KEY uq_budget_line_key (budget_id, line_key),
                        FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB
                    """
                )
    else:
        with _sqlite_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS client_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL DEFAULT 'other',
                    amount REAL NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS client_debts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    amount REAL NOT NULL DEFAULT 0,
                    monthly_payment REAL NOT NULL DEFAULT 0,
                    interest_rate_annual REAL NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS client_future_investments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    investment_type TEXT NOT NULL DEFAULT 'other',
                    current_amount REAL NOT NULL DEFAULT 0,
                    target_amount REAL NOT NULL DEFAULT 0,
                    monthly_contribution REAL NOT NULL DEFAULT 0,
                    expected_return_annual REAL NOT NULL DEFAULT 0,
                    target_year INTEGER,
                    notes TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS custom_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    budget_id INTEGER NOT NULL,
                    section_id TEXT NOT NULL,
                    line_key TEXT NOT NULL,
                    label_de TEXT NOT NULL,
                    label_en TEXT NOT NULL,
                    line_type TEXT NOT NULL DEFAULT 'expense',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(budget_id, line_key),
                    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE
                );
                """
            )
            _sqlite_migrate_debt_columns(conn)
            _sqlite_ensure_future_invest_table(conn)


def _sqlite_ensure_future_invest_table(conn: sqlite3.Connection) -> None:
    """Create future-investments table on DBs that predate this feature."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='client_future_investments'"
    ).fetchone()
    if cur:
        return
    conn.execute(
        """
        CREATE TABLE client_future_investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            investment_type TEXT NOT NULL DEFAULT 'other',
            current_amount REAL NOT NULL DEFAULT 0,
            target_amount REAL NOT NULL DEFAULT 0,
            monthly_contribution REAL NOT NULL DEFAULT 0,
            expected_return_annual REAL NOT NULL DEFAULT 0,
            target_year INTEGER,
            notes TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
        """
    )


def _sqlite_migrate_debt_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='client_debts'"
    ).fetchone()
    if not cur:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(client_debts)").fetchall()}
    if "monthly_payment" not in cols:
        conn.execute(
            "ALTER TABLE client_debts ADD COLUMN monthly_payment REAL NOT NULL DEFAULT 0"
        )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(client_debts)").fetchall()}
    if "interest_rate_annual" not in cols:
        conn.execute(
            "ALTER TABLE client_debts ADD COLUMN interest_rate_annual REAL NOT NULL DEFAULT 0"
        )


def _mysql_migrate_debt_columns(cur: Any) -> None:
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'client_debts'
        AND COLUMN_NAME = 'interest_rate_annual'
        """
    )
    row = cur.fetchone()
    count = row["c"] if isinstance(row, dict) else row[0]
    if not count:
        cur.execute(
            "ALTER TABLE client_debts ADD COLUMN interest_rate_annual DOUBLE NOT NULL DEFAULT 0"
        )


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

    custom_keys = [ln["line_key"] for ln in list_custom_lines(budget_id)]
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
    for k in custom_keys:
        if k not in entries:
            entries[k] = [0.0] * 12
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


# --- Client assets & debts (balance sheet, per client) ---

ASSET_TYPES = (
    "savings",
    "gold",
    "silver",
    "etf",
    "fd",
    "property",
    "stocks",
    "crypto",
    "other",
)

INVESTMENT_TYPES = (
    "etf",
    "pension",
    "savings",
    "property",
    "stocks",
    "crypto",
    "other",
)


def list_assets(client_id: int) -> list[dict[str, Any]]:
    ph = _ph()
    sql = f"""
        SELECT id, client_id, name, asset_type, amount, notes, sort_order
        FROM client_assets WHERE client_id = {ph}
        ORDER BY sort_order, id
    """
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(sql, (client_id,))
                return [_row_to_dict(r) for r in cur.fetchall()]
        rows = conn.execute(sql.replace("%s", "?"), (client_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]


def list_debts(client_id: int) -> list[dict[str, Any]]:
    ph = _ph()
    sql = f"""
        SELECT id, client_id, name, amount, monthly_payment, interest_rate_annual, notes, sort_order
        FROM client_debts WHERE client_id = {ph}
        ORDER BY sort_order, id
    """
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(sql, (client_id,))
                return [_row_to_dict(r) for r in cur.fetchall()]
        rows = conn.execute(sql.replace("%s", "?"), (client_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]


def create_asset(client_id: int, data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Asset name is required")
    asset_type = str(data.get("asset_type", "other")).strip() or "other"
    if asset_type not in ASSET_TYPES:
        asset_type = "other"
    amount = float(data.get("amount") or 0)
    notes = str(data.get("notes") or "")
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO client_assets (client_id, name, asset_type, amount, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (client_id, name, asset_type, amount, notes),
                )
                aid = int(cur.lastrowid)
        else:
            cur = conn.execute(
                """
                INSERT INTO client_assets (client_id, name, asset_type, amount, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (client_id, name, asset_type, amount, notes),
            )
            aid = int(cur.lastrowid)
    return _get_asset(aid)


def update_asset(asset_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    row = _get_asset(asset_id)
    if not row:
        return None
    name = str(data.get("name", row["name"])).strip()
    asset_type = str(data.get("asset_type", row["asset_type"])).strip() or "other"
    if asset_type not in ASSET_TYPES:
        asset_type = row["asset_type"]
    amount = float(data.get("amount", row["amount"]))
    notes = str(data.get("notes", row.get("notes") or ""))
    ph = _ph()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE client_assets SET name={ph}, asset_type={ph}, amount={ph}, notes={ph}
                    WHERE id={ph}
                    """,
                    (name, asset_type, amount, notes, asset_id),
                )
        else:
            conn.execute(
                """
                UPDATE client_assets SET name=?, asset_type=?, amount=?, notes=?
                WHERE id=?
                """,
                (name, asset_type, amount, notes, asset_id),
            )
    return _get_asset(asset_id)


def delete_asset(asset_id: int) -> bool:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM client_assets WHERE id = %s", (asset_id,))
                return cur.rowcount > 0
        cur = conn.execute("DELETE FROM client_assets WHERE id = ?", (asset_id,))
        return cur.rowcount > 0


def _get_asset(asset_id: int) -> dict[str, Any] | None:
    ph = _ph()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM client_assets WHERE id = {ph}", (asset_id,))
                row = cur.fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM client_assets WHERE id = ?", (asset_id,)
            ).fetchone()
    return _row_to_dict(row) if row else None


def create_debt(client_id: int, data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Debt name is required")
    amount = float(data.get("amount") or 0)
    monthly_payment = float(data.get("monthly_payment") or 0)
    interest_rate_annual = max(0.0, float(data.get("interest_rate_annual") or 0))
    notes = str(data.get("notes") or "")
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO client_debts
                    (client_id, name, amount, monthly_payment, interest_rate_annual, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (client_id, name, amount, monthly_payment, interest_rate_annual, notes),
                )
                did = int(cur.lastrowid)
        else:
            cur = conn.execute(
                """
                INSERT INTO client_debts
                (client_id, name, amount, monthly_payment, interest_rate_annual, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (client_id, name, amount, monthly_payment, interest_rate_annual, notes),
            )
            did = int(cur.lastrowid)
    return _get_debt(did)


def update_debt(debt_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    row = _get_debt(debt_id)
    if not row:
        return None
    name = str(data.get("name", row["name"])).strip()
    amount = float(data.get("amount", row["amount"]))
    monthly_payment = float(data.get("monthly_payment", row.get("monthly_payment") or 0))
    interest_rate_annual = max(
        0.0,
        float(
            data.get(
                "interest_rate_annual",
                row.get("interest_rate_annual") or 0,
            )
        ),
    )
    notes = str(data.get("notes", row.get("notes") or ""))
    ph = _ph()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE client_debts SET name={ph}, amount={ph}, monthly_payment={ph},
                    interest_rate_annual={ph}, notes={ph} WHERE id={ph}
                    """,
                    (name, amount, monthly_payment, interest_rate_annual, notes, debt_id),
                )
        else:
            conn.execute(
                """
                UPDATE client_debts SET name=?, amount=?, monthly_payment=?,
                interest_rate_annual=?, notes=? WHERE id=?
                """,
                (name, amount, monthly_payment, interest_rate_annual, notes, debt_id),
            )
    return _get_debt(debt_id)


def delete_debt(debt_id: int) -> bool:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM client_debts WHERE id = %s", (debt_id,))
                return cur.rowcount > 0
        cur = conn.execute("DELETE FROM client_debts WHERE id = ?", (debt_id,))
        return cur.rowcount > 0


def _get_debt(debt_id: int) -> dict[str, Any] | None:
    ph = _ph()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM client_debts WHERE id = {ph}", (debt_id,))
                row = cur.fetchone()
        else:
            row = conn.execute("SELECT * FROM client_debts WHERE id = ?", (debt_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_future_investments(client_id: int) -> list[dict[str, Any]]:
    ph = _ph()
    sql = f"""
        SELECT id, client_id, name, investment_type, current_amount, target_amount,
               monthly_contribution, expected_return_annual, target_year, notes, sort_order
        FROM client_future_investments WHERE client_id = {ph}
        ORDER BY sort_order, id
    """
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(sql, (client_id,))
                return [_row_to_dict(r) for r in cur.fetchall()]
        rows = conn.execute(sql.replace("%s", "?"), (client_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]


def create_future_investment(client_id: int, data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Investment name is required")
    investment_type = str(data.get("investment_type", "other")).strip() or "other"
    if investment_type not in INVESTMENT_TYPES:
        investment_type = "other"
    current_amount = float(data.get("current_amount") or 0)
    target_amount = float(data.get("target_amount") or 0)
    monthly_contribution = float(data.get("monthly_contribution") or 0)
    expected_return_annual = max(0.0, float(data.get("expected_return_annual") or 0))
    target_year = data.get("target_year")
    if target_year is not None and str(target_year).strip() == "":
        target_year = None
    elif target_year is not None:
        target_year = int(target_year)
    notes = str(data.get("notes") or "")
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO client_future_investments
                    (client_id, name, investment_type, current_amount, target_amount,
                     monthly_contribution, expected_return_annual, target_year, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        client_id,
                        name,
                        investment_type,
                        current_amount,
                        target_amount,
                        monthly_contribution,
                        expected_return_annual,
                        target_year,
                        notes,
                    ),
                )
                iid = int(cur.lastrowid)
        else:
            cur = conn.execute(
                """
                INSERT INTO client_future_investments
                (client_id, name, investment_type, current_amount, target_amount,
                 monthly_contribution, expected_return_annual, target_year, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    name,
                    investment_type,
                    current_amount,
                    target_amount,
                    monthly_contribution,
                    expected_return_annual,
                    target_year,
                    notes,
                ),
            )
            iid = int(cur.lastrowid)
    return _get_future_investment(iid)


def update_future_investment(
    investment_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    row = _get_future_investment(investment_id)
    if not row:
        return None
    name = str(data.get("name", row["name"])).strip()
    investment_type = str(data.get("investment_type", row["investment_type"])).strip() or "other"
    if investment_type not in INVESTMENT_TYPES:
        investment_type = row["investment_type"]
    current_amount = float(data.get("current_amount", row["current_amount"]))
    target_amount = float(data.get("target_amount", row["target_amount"]))
    monthly_contribution = float(
        data.get("monthly_contribution", row.get("monthly_contribution") or 0)
    )
    expected_return_annual = max(
        0.0,
        float(
            data.get(
                "expected_return_annual",
                row.get("expected_return_annual") or 0,
            )
        ),
    )
    target_year = data.get("target_year", row.get("target_year"))
    if target_year is not None and str(target_year).strip() == "":
        target_year = None
    elif target_year is not None:
        target_year = int(target_year)
    notes = str(data.get("notes", row.get("notes") or ""))
    ph = _ph()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE client_future_investments SET name={ph}, investment_type={ph},
                    current_amount={ph}, target_amount={ph}, monthly_contribution={ph},
                    expected_return_annual={ph}, target_year={ph}, notes={ph}
                    WHERE id={ph}
                    """,
                    (
                        name,
                        investment_type,
                        current_amount,
                        target_amount,
                        monthly_contribution,
                        expected_return_annual,
                        target_year,
                        notes,
                        investment_id,
                    ),
                )
        else:
            conn.execute(
                """
                UPDATE client_future_investments SET name=?, investment_type=?,
                current_amount=?, target_amount=?, monthly_contribution=?,
                expected_return_annual=?, target_year=?, notes=? WHERE id=?
                """,
                (
                    name,
                    investment_type,
                    current_amount,
                    target_amount,
                    monthly_contribution,
                    expected_return_annual,
                    target_year,
                    notes,
                    investment_id,
                ),
            )
    return _get_future_investment(investment_id)


def delete_future_investment(investment_id: int) -> bool:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM client_future_investments WHERE id = %s",
                    (investment_id,),
                )
                return cur.rowcount > 0
        cur = conn.execute(
            "DELETE FROM client_future_investments WHERE id = ?", (investment_id,)
        )
        return cur.rowcount > 0


def _get_future_investment(investment_id: int) -> dict[str, Any] | None:
    ph = _ph()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM client_future_investments WHERE id = {ph}",
                    (investment_id,),
                )
                row = cur.fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM client_future_investments WHERE id = ?", (investment_id,)
            ).fetchone()
    return _row_to_dict(row) if row else None


def compute_balance_sheet(client_id: int, year: int | None = None) -> dict[str, Any]:
    from app.calculations import compute_full_summary
    from app.debt_payoff import compute_debt_payoff
    from app.future_invest import compute_future_invest_plan

    assets = list_assets(client_id)
    debts = list_debts(client_id)
    total_assets = round(sum(float(a.get("amount") or 0) for a in assets), 2)
    total_debts = round(sum(float(d.get("amount") or 0) for d in debts), 2)
    plan_year = year if year is not None else 2026
    result: dict[str, Any] = {
        "assets": assets,
        "debts": debts,
        "total_assets": total_assets,
        "total_debts": total_debts,
        "net_worth": round(total_assets - total_debts, 2),
        "future_invest_plan": compute_future_invest_plan(
            list_future_investments(client_id), plan_year
        ),
    }
    if year is not None:
        bid = get_or_create_budget(client_id, year)
        entries = load_entries(bid)
        settings = get_settings(bid)
        ck = custom_line_keys_by_section(bid)
        summary = compute_full_summary(entries, settings["monatlich_mode"], ck)
        result["payoff"] = compute_debt_payoff(debts, summary)
        result["budget_year"] = year
    return result


# --- Custom budget lines (per budget year, per section) ---

def list_custom_lines(budget_id: int) -> list[dict[str, Any]]:
    ph = _ph()
    sql = f"""
        SELECT id, budget_id, section_id, line_key, label_de, label_en, line_type, sort_order
        FROM custom_lines WHERE budget_id = {ph}
        ORDER BY section_id, sort_order, id
    """
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(sql, (budget_id,))
                return [_row_to_dict(r) for r in cur.fetchall()]
        rows = conn.execute(sql.replace("%s", "?"), (budget_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]


def custom_lines_by_section(budget_id: int) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for ln in list_custom_lines(budget_id):
        grouped.setdefault(ln["section_id"], []).append(ln)
    return grouped


def custom_line_keys_by_section(budget_id: int) -> dict[str, list[str]]:
    return {
        sid: [ln["line_key"] for ln in lines]
        for sid, lines in custom_lines_by_section(budget_id).items()
    }


def create_custom_line(
    budget_id: int,
    section_id: str,
    label_de: str,
    label_en: str,
    line_type: str = "expense",
) -> dict[str, Any]:
    from app.categories import SECTION_BY_ID

    if section_id not in SECTION_BY_ID:
        raise ValueError(f"Unknown section: {section_id}")
    label_de = label_de.strip()
    label_en = (label_en or label_de).strip()
    if not label_de:
        raise ValueError("Label is required")
    if line_type not in ("income", "expense", "info"):
        line_type = "expense"
    import re
    import time

    slug = re.sub(r"[^a-z0-9]+", "_", label_en.lower())[:24].strip("_") or "line"
    line_key = f"cx_{section_id}_{slug}_{int(time.time() * 1000) % 1000000}"
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO custom_lines
                    (budget_id, section_id, line_key, label_de, label_en, line_type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (budget_id, section_id, line_key, label_de, label_en, line_type),
                )
                lid = int(cur.lastrowid)
        else:
            cur = conn.execute(
                """
                INSERT INTO custom_lines
                (budget_id, section_id, line_key, label_de, label_en, line_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (budget_id, section_id, line_key, label_de, label_en, line_type),
            )
            lid = int(cur.lastrowid)
    row = _get_custom_line(lid)
    assert row is not None
    return row


def delete_custom_line(budget_id: int, line_key: str) -> bool:
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM entries WHERE budget_id = %s AND line_key = %s",
                    (budget_id, line_key),
                )
                cur.execute(
                    "DELETE FROM custom_lines WHERE budget_id = %s AND line_key = %s",
                    (budget_id, line_key),
                )
                return cur.rowcount > 0
        conn.execute(
            "DELETE FROM entries WHERE budget_id = ? AND line_key = ?",
            (budget_id, line_key),
        )
        cur = conn.execute(
            "DELETE FROM custom_lines WHERE budget_id = ? AND line_key = ?",
            (budget_id, line_key),
        )
        return cur.rowcount > 0


def _get_custom_line(line_id: int) -> dict[str, Any] | None:
    ph = _ph()
    with get_connection() as conn:
        if _USE_MYSQL:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM custom_lines WHERE id = {ph}", (line_id,))
                row = cur.fetchone()
        else:
            row = conn.execute("SELECT * FROM custom_lines WHERE id = ?", (line_id,)).fetchone()
    return _row_to_dict(row) if row else None
