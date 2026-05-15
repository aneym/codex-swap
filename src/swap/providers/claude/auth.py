"""Read, write, and decode Claude Code credentials + identity metadata.

Claude Code stores its OAuth credentials in two places:

1. **Credentials** — the raw OAuth blob ({"claudeAiOauth": {accessToken, ...}}).
   - macOS: Keychain, service ``Claude Code-credentials``, account = ``$USER``.
   - Linux/WSL/Windows: file at ``~/.claude/.credentials.json``.
2. **Identity** — ``oauthAccount`` block inside ``~/.claude.json`` (or
   ``$CLAUDE_CONFIG_DIR/.claude.json``), with ``emailAddress``,
   ``accountUuid``, ``organizationUuid``, ``organizationName``.

Switching a slot in requires patching ``~/.claude.json``'s ``oauthAccount``
block AND writing the credentials back to the keychain/file — both must be
restored together. We never overwrite the rest of ``.claude.json`` (it holds
projects, MCP servers, settings).

References:
- claude-swap (upstream PyPI) ``switcher.py`` for the macOS keychain CLI shape.
- claude-code's own ``getStoragePath`` / ``getGlobalClaudeFile`` resolution.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
KEYRING_SERVICE = "Claude Code-credentials"


# ---------------------------------------------------------------------------
# path resolution (mirrors claude-code at call time so tests can monkeypatch)
# ---------------------------------------------------------------------------


def claude_config_home() -> Path:
    """``$CLAUDE_CONFIG_DIR`` if set, else ``~/.claude``."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else HOME / ".claude"


def claude_global_config_path() -> Path:
    """Where ``oauthAccount`` lives.

    Legacy ``<config_home>/.config.json`` wins when it exists; otherwise
    ``$CLAUDE_CONFIG_DIR/.claude.json`` (or ``~/.claude.json`` if unset).
    """
    legacy = claude_config_home() / ".config.json"
    if legacy.exists():
        return legacy
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(env) if env else HOME
    return base / ".claude.json"


def claude_credentials_path() -> Path:
    """File location of credentials on Linux/Windows."""
    return claude_config_home() / ".credentials.json"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _keychain_user() -> str:
    return os.environ.get("USER", "user")


# ---------------------------------------------------------------------------
# raw credentials I/O (keychain on macOS, file elsewhere)
# ---------------------------------------------------------------------------


def _read_keychain_credentials() -> str | None:
    """Read the raw credentials JSON string from the macOS keychain.

    Returns the JSON string on success, ``""`` if the keychain item is
    missing, ``None`` on unexpected failure.
    """
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                _keychain_user(),
                "-s",
                KEYRING_SERVICE,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        # `security` returns 44 when the item isn't found.
        if exc.returncode == 44:
            return ""
        return None


def _write_keychain_credentials(payload: str) -> None:
    result = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-s",
            KEYRING_SERVICE,
            "-a",
            _keychain_user(),
            "-w",
            payload,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude-swap: failed to write keychain credentials: "
            f"{result.stderr.strip() or 'unknown error'}"
        )


def _delete_keychain_credentials() -> None:
    """Remove the keychain entry. No-op if it's already gone."""
    subprocess.run(
        [
            "security",
            "delete-generic-password",
            "-a",
            _keychain_user(),
            "-s",
            KEYRING_SERVICE,
        ],
        capture_output=True,
    )


def _read_file_credentials() -> str | None:
    path = claude_credentials_path()
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _write_file_credentials(payload: str) -> None:
    path = claude_credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def _delete_file_credentials() -> None:
    path = claude_credentials_path()
    if path.exists():
        path.unlink()


def _read_raw_credentials() -> str | None:
    """Read the raw credentials JSON string from the active backend."""
    return _read_keychain_credentials() if _is_macos() else _read_file_credentials()


def _write_raw_credentials(payload: str) -> None:
    if _is_macos():
        _write_keychain_credentials(payload)
    else:
        _write_file_credentials(payload)


def _delete_raw_credentials() -> None:
    if _is_macos():
        _delete_keychain_credentials()
    else:
        _delete_file_credentials()


# ---------------------------------------------------------------------------
# parsed credentials helpers
# ---------------------------------------------------------------------------


def _parse_creds(payload: str | None) -> dict | None:
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def read_live_credentials() -> dict | None:
    """Read live credentials and merge identity from ``oauthAccount``.

    The provider protocol passes the result of this function through
    ``credentials_identity`` and ``credentials_fingerprint``. We embed the
    parsed ``oauthAccount`` block under ``_oauth_account`` so those callables
    don't need to re-read ``~/.claude.json`` themselves.
    """
    raw = _read_raw_credentials()
    if raw is None:
        return None
    if raw == "":
        return None
    parsed = _parse_creds(raw)
    if parsed is None:
        return None
    oauth_account = _read_oauth_account_block()
    if isinstance(oauth_account, dict):
        parsed["_oauth_account"] = copy.deepcopy(oauth_account)
    return parsed


def clear_live_credentials() -> None:
    """Wipe live credentials. NEVER call ``claude auth logout`` — that
    revokes the refresh token server-side, killing every other slot.

    We leave ``~/.claude.json``'s ``oauthAccount`` block in place; on the next
    login claude-code will overwrite it with the new account's info.
    """
    _delete_raw_credentials()


# ---------------------------------------------------------------------------
# identity / fingerprint
# ---------------------------------------------------------------------------


def _read_oauth_account_block() -> dict | None:
    path = claude_global_config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    oauth = data.get("oauthAccount")
    return oauth if isinstance(oauth, dict) else None


def credentials_identity(creds: dict) -> tuple[str, str, str]:
    """Return ``(email, account_id, plan_type)`` for a parsed creds blob.

    ``account_id`` is the organizationUuid (matches cswap's composite-key
    convention so personal accounts get ``""`` and org accounts get the org
    UUID). ``plan_type`` is left empty here — claude-code surfaces it via
    the usage API, not via the creds blob. Filled in once we probe.
    """
    if not isinstance(creds, dict):
        return "", "", ""
    oauth_account = creds.get("_oauth_account")
    if not isinstance(oauth_account, dict):
        oauth_account = _read_oauth_account_block() or {}
    email = oauth_account.get("emailAddress") or ""
    account_id = oauth_account.get("organizationUuid") or ""
    plan_type = ""
    # The "subscriptionType" field in `claudeAiOauth` is occasionally absent.
    oauth = creds.get("claudeAiOauth")
    if isinstance(oauth, dict):
        plan_type = oauth.get("subscriptionType") or ""
    return email, account_id, plan_type


def credentials_fingerprint(creds: dict) -> str:
    """Stable, non-secret id for slots without an organizationUuid.

    Prefers ``accountUuid`` (also from ``oauthAccount``) since it's per-user;
    falls back to a SHA256 over the refresh token suffix so even a creds blob
    with no identity metadata gets a unique handle.
    """
    if not isinstance(creds, dict):
        return ""
    oauth_account = creds.get("_oauth_account")
    if not isinstance(oauth_account, dict):
        oauth_account = _read_oauth_account_block() or {}
    account_uuid = oauth_account.get("accountUuid") or ""
    if account_uuid:
        return f"claude:{account_uuid}"

    oauth = creds.get("claudeAiOauth")
    if isinstance(oauth, dict):
        refresh = oauth.get("refreshToken") or ""
        access = oauth.get("accessToken") or ""
        secret = refresh or access
        if isinstance(secret, str) and secret:
            digest = hashlib.sha256(secret.encode()).hexdigest()[:24]
            return f"claude:tok:{digest}"
    return ""


# ---------------------------------------------------------------------------
# slot snapshot I/O
# ---------------------------------------------------------------------------


def _write_slot_file(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def snapshot_to_slot(slot_dir: Path) -> None:
    """Write the live creds + oauthAccount block into ``slot_dir``.

    Produces two files:
    - ``slot_dir/credentials.json`` — the raw creds string from keychain/file.
    - ``slot_dir/oauth_account.json`` — the live ``oauthAccount`` block.

    Switching back requires both: creds determine which token is active,
    ``oauthAccount`` determines what claude-code thinks it's logged in as.
    """
    raw = _read_raw_credentials()
    if not raw:
        return
    slot_dir.mkdir(parents=True, exist_ok=True)
    _write_slot_file(slot_dir / "credentials.json", raw)
    oauth = _read_oauth_account_block()
    if isinstance(oauth, dict):
        _write_slot_file(
            slot_dir / "oauth_account.json",
            json.dumps(oauth, indent=2),
        )


def restore_from_slot(slot_dir: Path) -> None:
    """Inverse of ``snapshot_to_slot``: live creds + patched ``oauthAccount``."""
    creds_path = slot_dir / "credentials.json"
    if not creds_path.exists():
        raise FileNotFoundError(f"No credentials.json in slot dir {slot_dir}")
    payload = creds_path.read_text(encoding="utf-8")
    _write_raw_credentials(payload)

    oauth_path = slot_dir / "oauth_account.json"
    if oauth_path.exists():
        try:
            oauth = json.loads(oauth_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            oauth = None
        if isinstance(oauth, dict):
            _patch_oauth_account(oauth)


def _patch_oauth_account(oauth: dict) -> None:
    """Overwrite ``oauthAccount`` in ``~/.claude.json`` without touching
    anything else.

    Preserves projects, MCP servers, settings, etc. If the config file doesn't
    exist yet, we synthesize a minimal one containing only ``oauthAccount``.
    """
    path = claude_global_config_path()
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
    else:
        existing = {}
    existing["oauthAccount"] = oauth
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


# ---------------------------------------------------------------------------
# convenience for oauth.py: live backup + restore around a destructive login
# ---------------------------------------------------------------------------


def capture_live_state() -> tuple[str | None, dict | None]:
    """Snapshot the live creds + ``oauthAccount`` block to in-memory values.

    Used by ``oauth.start_login`` to roll back on failure.
    """
    raw = _read_raw_credentials()
    creds = raw if raw else None
    oauth = _read_oauth_account_block()
    return creds, copy.deepcopy(oauth) if isinstance(oauth, dict) else None


def restore_live_state(creds: str | None, oauth: dict | None) -> None:
    """Inverse of ``capture_live_state``."""
    if creds is None:
        _delete_raw_credentials()
    else:
        _write_raw_credentials(creds)
    if isinstance(oauth, dict):
        _patch_oauth_account(oauth)
