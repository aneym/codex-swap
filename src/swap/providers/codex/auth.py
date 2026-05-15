"""Read, write, and decode Codex's auth.json.

Verbatim port of the original `codex_swap.auth`, with a couple of provider-shaped
helpers added so the Provider dataclass can bind to plain callables.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
from pathlib import Path

HOME = Path.home()
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or HOME / ".codex")
AUTH_PATH = CODEX_HOME / "auth.json"


def _codex_home() -> Path:
    """Always read CODEX_HOME at call time so tests can monkeypatch the env."""
    return Path(os.environ.get("CODEX_HOME") or HOME / ".codex")


def _auth_path() -> Path:
    return _codex_home() / "auth.json"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


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


def auth_fingerprint(auth: dict) -> str:
    """Return a stable, non-secret identifier for auth blobs without account_id."""
    if not isinstance(auth, dict):
        return ""
    tokens = auth.get("tokens", {}) or {}
    account_id = tokens.get("account_id", "") or ""
    if account_id:
        return f"chatgpt:{account_id}"

    api_key = auth.get("OPENAI_API_KEY", "") or ""
    if isinstance(api_key, str) and api_key:
        digest = hashlib.sha256(api_key.encode()).hexdigest()[:24]
        return f"apikey:{digest}"

    return ""


def current_auth() -> dict | None:
    return read_json(_auth_path())


def clear_live_credentials() -> None:
    """Remove the live auth.json. NEVER call `codex logout` — that revokes
    the refresh token at the OAuth provider, killing every other slot whose
    snapshot pre-dates the revoke.
    """
    path = _auth_path()
    if path.exists():
        path.unlink()


def snapshot_to_slot(slot_dir: Path) -> None:
    """Copy live auth.json into the slot dir."""
    src = _auth_path()
    if not src.exists():
        return
    target = slot_dir / "auth.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    os.chmod(target, 0o600)


def restore_from_slot(slot_dir: Path) -> None:
    """Copy `<slot_dir>/auth.json` to the live auth.json location."""
    src = slot_dir / "auth.json"
    if not src.exists():
        raise FileNotFoundError(f"No auth.json in slot dir {slot_dir}")
    target = _auth_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    os.chmod(target, 0o600)
