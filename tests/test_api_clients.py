"""API tests (SQLite — no external database required)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Use isolated DB for tests
_test_db = Path(__file__).resolve().parent / "_test_budget.db"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = str(_test_db)


@pytest.fixture(autouse=True)
def clean_db():
    if _test_db.exists():
        _test_db.unlink()
    from app.database import init_db

    init_db()
    yield
    if _test_db.exists():
        _test_db.unlink()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def test_health_sqlite(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["database"] == "sqlite"


def test_create_and_list_client(client):
    r = client.post(
        "/api/clients",
        json={
            "name": "Acme Finance",
            "company_name": "Acme GmbH",
            "street": "Hauptstr. 5",
            "postal_code": "80331",
            "city": "München",
            "country": "Germany",
            "email": "finance@acme.de",
            "tax_id": "143/123/45678",
        },
    )
    assert r.status_code == 200
    c = r.json()["client"]
    assert c["name"] == "Acme Finance"
    assert c["city"] == "München"

    listed = client.get("/api/clients").json()["clients"]
    assert any(x["name"] == "Acme Finance" for x in listed)


def test_update_client(client):
    created = client.post("/api/clients", json={"name": "Old Name"}).json()["client"]
    cid = created["id"]
    r = client.put(
        f"/api/clients/{cid}",
        json={"name": "New Name", "iban": "DE89370400440532013000"},
    )
    assert r.status_code == 200
    assert r.json()["client"]["name"] == "New Name"
    assert r.json()["client"]["iban"] == "DE89370400440532013000"


def test_duplicate_name_409(client):
    client.post("/api/clients", json={"name": "Unique Co"})
    r = client.post("/api/clients", json={"name": "Unique Co"})
    assert r.status_code == 409


def test_budget_for_client(client):
    from app.seed import ensure_sample_client

    cid = ensure_sample_client()
    b = client.get(f"/api/clients/{cid}/budget/2026")
    assert b.status_code == 200
    assert b.json()["entries"]["na_net"][6] == 1987.0
