"""Per-slot Claude usage — Anthropic ``/api/oauth/usage`` endpoint + cache.

Unlike Codex, Claude has no on-disk rollout logs we can scan. We refresh
usage by:
1. Reading each slot's stored credentials.
2. If the access token is expired (or missing), POSTing the refresh token to
   ``https://platform.claude.com/v1/oauth/token`` and rotating the slot
   snapshot to the new tokens.
3. Hitting ``GET https://api.anthropic.com/api/oauth/usage`` with the (now
   fresh) access token.
4. Normalizing into the same shape as codex's persisted store:
   ``{primary: {used_percent, resets_at}, secondary: {...}, plan_type,
   scanned_at, source, source_path}``.

OAuth constants are ported verbatim from the upstream ``claude-swap`` PyPI
package's ``oauth.py``.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ...core.jsonio import atomic_write_json, read_json
from ...core.paths import provider_paths
from ...core.sequence import load_sequence

OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
OAUTH_BETA_HEADER = "oauth-2025-04-20"
OAUTH_EXPIRY_BUFFER_MS = 5 * 60 * 1000
USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"

_logger = logging.getLogger("claude-swap")


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------


def _paths() -> dict:
    return provider_paths("claude")


def _usage_cache() -> Path:
    return _paths()["usage_cache"]


# ---------------------------------------------------------------------------
# token plumbing
# ---------------------------------------------------------------------------


def _slot_credentials_path(slot: str) -> Path:
    return _paths()["accounts_dir"] / slot / "credentials.json"


def _read_slot_creds(slot: str) -> dict | None:
    path = _slot_credentials_path(slot)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_slot_creds(slot: str, creds: dict) -> None:
    path = _slot_credentials_path(slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(creds), encoding="utf-8")
    import os

    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def _is_expired(expires_at: object) -> bool:
    if not isinstance(expires_at, (int, float)):
        return False
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return now_ms + OAUTH_EXPIRY_BUFFER_MS >= int(expires_at)


def _refresh_access_token(creds: dict) -> dict | None:
    """Refresh the OAuth access token in-place. Returns updated creds or None."""
    oauth = creds.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        return None
    refresh_token = oauth.get("refreshToken")
    if not refresh_token:
        return None

    body = json.dumps(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
        }
    ).encode()

    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "claude-swap/0.2",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        _logger.debug("Claude OAuth refresh failed: %r", exc)
        return None

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    oauth["accessToken"] = payload["access_token"]
    oauth["expiresAt"] = now_ms + payload["expires_in"] * 1000
    if payload.get("refresh_token"):
        oauth["refreshToken"] = payload["refresh_token"]
    if payload.get("scope"):
        oauth["scopes"] = payload["scope"].split()
    creds["claudeAiOauth"] = oauth
    return creds


# ---------------------------------------------------------------------------
# usage API
# ---------------------------------------------------------------------------


def _fetch_usage(access_token: str) -> dict | None:
    """Call the Anthropic usage endpoint. Returns the raw dict or None."""
    req = urllib.request.Request(
        USAGE_API_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "anthropic-beta": OAUTH_BETA_HEADER,
            "User-Agent": "claude-swap/0.2",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        _logger.debug("Claude usage fetch failed: %r", exc)
        return None


def _resets_at_to_epoch(value: object) -> float | None:
    """Convert an ISO-8601 timestamp to a UNIX epoch (seconds)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        # Python <3.11 doesn't grok trailing 'Z'; normalize.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value).timestamp()
    except (ValueError, OSError):
        return None


def _window(api_block: dict | None) -> dict | None:
    if not isinstance(api_block, dict):
        return None
    util = api_block.get("utilization")
    used_percent: float | None = None
    if util is not None:
        try:
            used_percent = float(util)
        except (TypeError, ValueError):
            used_percent = None
    resets_at = _resets_at_to_epoch(api_block.get("resets_at"))
    window: dict = {}
    if used_percent is not None:
        window["used_percent"] = used_percent
    if resets_at is not None:
        window["resets_at"] = resets_at
    return window or None


def _record_from_usage(data: dict, plan_type: str) -> dict:
    return {
        "primary": _window(data.get("five_hour")),
        "secondary": _window(data.get("seven_day")),
        "plan_type": plan_type,
        "scanned_at": time.time(),
        "source": "anthropic-usage-api",
        "source_path": USAGE_API_URL,
    }


# ---------------------------------------------------------------------------
# persisted store (mirrors codex usage.py shape)
# ---------------------------------------------------------------------------


def load_persisted() -> dict[str, dict]:
    raw = read_json(_usage_cache()) or {}
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def save_persisted(data: dict[str, dict]) -> None:
    payload = {"timestamp": time.time(), "data": data}
    atomic_write_json(_usage_cache(), payload)


def merge_into_persisted(updates: dict[str, dict]) -> dict[str, dict]:
    persisted = load_persisted()
    changed = False
    for slot, rec in updates.items():
        if not isinstance(rec, dict):
            continue
        existing = persisted.get(slot) or {}
        new_ts = float(rec.get("scanned_at") or 0)
        old_ts = float(existing.get("scanned_at") or 0)
        if new_ts >= old_ts:
            persisted[slot] = rec
            changed = True
    if changed:
        save_persisted(persisted)
    return persisted


def drop_slot_record(slot: str) -> None:
    persisted = load_persisted()
    if str(slot) in persisted:
        persisted.pop(str(slot), None)
        save_persisted(persisted)


# ---------------------------------------------------------------------------
# decay + exhaustion (matches the codex shape exactly so launcher policy reuses)
# ---------------------------------------------------------------------------


def effective_used_percent(window: dict | None, now: float | None = None) -> float | None:
    if not isinstance(window, dict):
        return None
    pct = window.get("used_percent")
    if pct is None:
        return None
    resets_at = window.get("resets_at")
    if isinstance(resets_at, (int, float)):
        if (now if now is not None else time.time()) >= float(resets_at):
            return 0.0
    try:
        return float(pct)
    except (TypeError, ValueError):
        return None


def is_exhausted(rec: dict | None) -> bool:
    """Claude doesn't surface an explicit ``exhausted`` flag; treat 100%+
    on either window after decay as exhausted.
    """
    if not isinstance(rec, dict):
        return False
    if rec.get("exhausted"):
        return True
    for key in ("primary", "secondary"):
        eff = effective_used_percent(rec.get(key))
        if eff is not None and eff >= 100.0:
            return True
    return False


# ---------------------------------------------------------------------------
# refresh entry point
# ---------------------------------------------------------------------------


def refresh_from_rollouts() -> dict[str, dict]:
    """Walk every slot, refresh-if-needed, query the usage API, merge in.

    Name preserved for protocol compat with codex (which scans rollout logs).
    For Claude this just hits an HTTPS endpoint per slot.
    """
    seq = load_sequence(_paths()["sequence"])
    accounts = seq.get("accounts", {}) or {}
    if not accounts:
        return load_persisted()

    updates: dict[str, dict] = {}
    for slot in sorted(accounts, key=lambda s: int(s)):
        creds = _read_slot_creds(slot)
        if not creds:
            continue
        oauth = creds.get("claudeAiOauth")
        if not isinstance(oauth, dict):
            continue
        if _is_expired(oauth.get("expiresAt")):
            refreshed = _refresh_access_token(creds)
            if refreshed:
                creds = refreshed
                _write_slot_creds(slot, creds)
                oauth = creds.get("claudeAiOauth") or {}

        access_token = oauth.get("accessToken")
        if not access_token:
            continue
        raw = _fetch_usage(access_token)
        if not isinstance(raw, dict):
            continue
        plan_type = accounts.get(slot, {}).get("plan_type") or ""
        updates[slot] = _record_from_usage(raw, plan_type)

    if updates:
        return merge_into_persisted(updates)
    return load_persisted()
