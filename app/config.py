"""Local database configuration (data stays on your machine)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

# sqlite = works without Docker/MySQL (default)
# mysql = optional if you run docker compose up -d
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()

DATA_DIR = _ROOT / "data"
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(DATA_DIR / "budget.db")))

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "budget")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "budget")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "budget_app")

CLIENT_COLUMNS = (
    "name",
    "company_name",
    "contact_person",
    "email",
    "phone",
    "street",
    "postal_code",
    "city",
    "country",
    "tax_id",
    "vat_id",
    "iban",
    "notes",
)
