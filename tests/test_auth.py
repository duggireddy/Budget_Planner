"""Authentication API and middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import _sessions


def test_login_success(api_client: TestClient) -> None:
    r = api_client.get("/api/clients")
    assert r.status_code == 200


def test_login_failure() -> None:
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrong"},
    )
    assert r.status_code == 401


def test_unauthenticated_api_blocked() -> None:
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/clients")
    assert r.status_code == 401


def test_reset_password(api_client: TestClient) -> None:
    r = api_client.post(
        "/api/auth/reset-password",
        json={
            "reset_code": "12345",
            "new_password": "newsecret",
            "new_username": "",
        },
    )
    assert r.status_code == 200
    _sessions.clear()
    r2 = api_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "newsecret"},
    )
    assert r2.status_code == 200


def test_logout(api_client: TestClient) -> None:
    r = api_client.post("/api/auth/logout")
    assert r.status_code == 200
    r2 = api_client.get("/api/clients")
    assert r2.status_code == 401
