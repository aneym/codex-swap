"""Compat shim — re-export from `swap.providers.codex.auth`."""

from swap.core.jsonio import atomic_write_json, read_json
from swap.providers.codex.auth import (
    AUTH_PATH,
    auth_fingerprint,
    auth_identity,
    clear_live_credentials,
    current_auth,
    decode_jwt_payload,
    restore_from_slot,
    snapshot_to_slot,
)


def current_identity():
    return auth_identity(current_auth() or {})


__all__ = [
    "AUTH_PATH",
    "atomic_write_json",
    "auth_fingerprint",
    "auth_identity",
    "clear_live_credentials",
    "current_auth",
    "current_identity",
    "decode_jwt_payload",
    "read_json",
    "restore_from_slot",
    "snapshot_to_slot",
]
