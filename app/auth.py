"""Local login, session cookies, and password management."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from app.paths import user_data_dir

SESSION_COOKIE = "budget_session"
SESSION_TTL_SEC = 12 * 3600  # re-login after long idle; new browser session still requires login
PBKDF2_ITERATIONS = 200_000

_sessions: dict[str, dict[str, Any]] = {}


def auth_file_path() -> Path:
    override = os.getenv("BUDGET_AUTH_PATH")
    if override:
        path = Path(override)
    else:
        path = user_data_dir() / "data" / "auth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def hash_secret(value: str, salt: bytes | None = None) -> dict[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", value.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return {"salt": salt.hex(), "hash": digest.hex()}


def verify_secret(value: str, record: dict[str, str]) -> bool:
    try:
        salt = bytes.fromhex(record["salt"])
        expected = record["hash"]
    except (KeyError, ValueError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", value.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return secrets.compare_digest(digest.hex(), expected)


def load_auth_config() -> dict[str, Any]:
    path = auth_file_path()
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_auth_config(config: dict[str, Any]) -> None:
    path = auth_file_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def ensure_auth_config() -> dict[str, Any]:
    """Create auth.json on first run (hashed secrets only)."""
    config = load_auth_config()
    if config.get("username") and config.get("password") and config.get("reset_code"):
        return config

    username = os.getenv("BUDGET_AUTH_USER", "duggireddy")
    password = os.getenv("BUDGET_AUTH_PASSWORD", "gangaBabu$208")
    reset_code = os.getenv("BUDGET_RESET_CODE", "12345")
    config = {
        "username": username,
        "password": hash_secret(password),
        "reset_code": hash_secret(reset_code),
    }
    save_auth_config(config)
    return config


def verify_login(username: str, password: str) -> bool:
    config = ensure_auth_config()
    if username.strip() != config.get("username"):
        return False
    return verify_secret(password, config.get("password", {}))


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"username": username, "expires": time.time() + SESSION_TTL_SEC}
    return token


def verify_session(token: str | None) -> dict[str, Any] | None:
    if not token or token not in _sessions:
        return None
    sess = _sessions[token]
    if sess["expires"] < time.time():
        _sessions.pop(token, None)
        return None
    return sess


def revoke_session(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)


def change_password(
    reset_code: str, new_password: str, new_username: str | None = None
) -> None:
    if len(new_password) < 4:
        raise ValueError("New password must be at least 4 characters")
    config = ensure_auth_config()
    if not verify_secret(reset_code, config.get("reset_code", {})):
        raise ValueError("Invalid reset code")
    config["password"] = hash_secret(new_password)
    if new_username and new_username.strip():
        config["username"] = new_username.strip()
    save_auth_config(config)
    _sessions.clear()
