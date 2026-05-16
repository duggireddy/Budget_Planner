"""Shared isolated SQLite database for all tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_test_db = Path(__file__).resolve().parent / "_test_budget.db"
_test_auth = Path(__file__).resolve().parent / "_test_auth.json"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = str(_test_db)
os.environ["BUDGET_AUTH_PATH"] = str(_test_auth)
os.environ["BUDGET_AUTH_USER"] = "testuser"
os.environ["BUDGET_AUTH_PASSWORD"] = "testpass"
os.environ["BUDGET_RESET_CODE"] = "12345"


@pytest.fixture(autouse=True)
def isolated_db():
    if _test_db.exists():
        _test_db.unlink()
    from app.database import init_db

    init_db()
    yield
    if _test_db.exists():
        _test_db.unlink()


@pytest.fixture(autouse=True)
def isolated_auth():
    from app import auth as auth_mod
    from app.auth import ensure_auth_config

    if _test_auth.exists():
        _test_auth.unlink()
    auth_mod._sessions.clear()
    ensure_auth_config()
    yield
    auth_mod._sessions.clear()
    if _test_auth.exists():
        _test_auth.unlink()


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert r.status_code == 200
    return client
