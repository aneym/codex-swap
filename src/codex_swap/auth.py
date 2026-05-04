"""Read, write, and decode Codex's auth.json."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from .paths import AUTH_PATH


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def atomic_write_json(path: Path, data: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.chmod(tmp, mode)
    tmp.replace(path)


def decode_jwt_payload(token: str) -> dict | None:
    if not token:
        return None
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        pad = "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(parts[1] + pad))
    except Exception:
        return None


def auth_identity(auth: dict) -> tuple[str, str, str]:
    """Return (email, account_id, plan_type) from a parsed auth.json blob."""
    if not isinstance(auth, dict):
        return "", "", ""
    tokens = auth.get("tokens", {}) or {}
    account_id = tokens.get("account_id", "") or ""
    payload = decode_jwt_payload(tokens.get("id_token", "") or "")
    email = ""
    plan_type = ""
    if payload:
        email = payload.get("email", "") or ""
        chatgpt = payload.get("https://api.openai.com/auth", {})
        if isinstance(chatgpt, dict):
            plan_type = chatgpt.get("chatgpt_plan_type", "") or ""
    return email, account_id, plan_type


def current_auth() -> dict | None:
    return read_json(AUTH_PATH)


def current_identity() -> tuple[str, str, str]:
    return auth_identity(current_auth() or {})
