"""Compat shim — re-exports from `swap.core.slots` and `swap.providers.codex`.

The original `codex_swap.slots` exposed a flat module surface with implicit
codex provider context. This shim keeps the function signatures the same and
binds the codex provider for callers that haven't migrated to `swap.*` yet.
"""

from __future__ import annotations

import subprocess as _subprocess

from swap.core.paths import provider_paths
from swap.core.reauth import (
    reauth as _core_reauth,
)
from swap.core.reauth import (
    reconnect_broken as _core_reconnect_broken,
)
from swap.core.reauth import (
    verify_all as _core_verify_all,
)
from swap.core.sequence import (
    load_sequence as _core_load_sequence,
)
from swap.core.sequence import (
    load_state as _core_load_state,
)
from swap.core.sequence import (
    next_free_slot,
    resolve_slot,
    slot_for_account_id,
)
from swap.core.sequence import (
    save_sequence as _core_save_sequence,
)
from swap.core.sequence import (
    save_state as _core_save_state,
)
from swap.core.slots import (
    add_auth_file as _core_add_auth_file,
)
from swap.core.slots import (
    add_current as _core_add_current,
)
from swap.core.slots import (
    current_slot as _core_current_slot,
)
from swap.core.slots import (
    remove as _core_remove,
)
from swap.core.slots import (
    rotate as _core_rotate,
)
from swap.core.slots import (
    seed_slots as _core_seed_slots,
)
from swap.core.slots import (
    slot_for_credentials,
)
from swap.core.slots import (
    stash_active as _core_stash_active,
)
from swap.core.slots import (
    switch_to as _core_switch_to,
)
from swap.providers.codex import CODEX as _CODEX
from swap.providers.codex import oauth as _oauth

# Tests do `monkeypatch.setattr(slots.subprocess, "run", ...)`. Re-bind so the
# patch propagates to the provider's oauth module.
subprocess = _subprocess
_oauth.subprocess = _subprocess  # ensure module-attr patching works


def _paths_now():
    """Resolve paths fresh each call so tests can monkeypatch module-level constants."""
    return {
        "root": provider_paths("codex")["root"],
        "accounts_dir": ACCOUNTS_DIR,
        "sequence": SEQUENCE_PATH,
        "state": STATE_PATH,
        "policy": provider_paths("codex")["policy"],
        "usage_cache": provider_paths("codex")["usage_cache"],
    }


# Mutable module-level constants — tests monkeypatch these on the module.
_paths_initial = provider_paths("codex")
ACCOUNTS_DIR = _paths_initial["accounts_dir"]
SEQUENCE_PATH = _paths_initial["sequence"]
STATE_PATH = _paths_initial["state"]
AUTH_PATH = None  # populated lazily below

from swap.providers.codex.auth import AUTH_PATH  # noqa: E402, F811

# --- public API (delegating to core, but honoring monkeypatched constants) ---


def load_sequence():
    return _core_load_sequence(SEQUENCE_PATH)


def save_sequence(data):
    _core_save_sequence(SEQUENCE_PATH, data)


def load_state():
    return _core_load_state(STATE_PATH)


def save_state(data):
    _core_save_state(STATE_PATH, data)


def current_slot(seq=None):
    return _core_current_slot(_CODEX, _paths_now(), seq)


def stash_active(seq):
    _core_stash_active(_CODEX, _paths_now(), seq)


def add_current():
    return _core_add_current(_CODEX, _paths_now())


def add_auth_file(auth_path, *, mark_active=False, source_label=""):
    return _core_add_auth_file(
        _CODEX, _paths_now(), auth_path, mark_active=mark_active, source_label=source_label
    )


def remove(target):
    return _core_remove(_CODEX, _paths_now(), target)


def switch_to(target):
    return _core_switch_to(_CODEX, _paths_now(), target)


def rotate():
    return _core_rotate(_CODEX, _paths_now())


def reauth(target):
    return _core_reauth(_CODEX, _paths_now(), target)


def verify_all():
    return _core_verify_all(_CODEX, _paths_now())


def reconnect_broken():
    return _core_reconnect_broken(_CODEX, _paths_now())


def seed_slots(slots_list, max_concurrency=4, probe_timeout=30.0):
    return _core_seed_slots(
        _CODEX,
        _paths_now(),
        slots_list,
        max_concurrency=max_concurrency,
        probe_timeout=probe_timeout,
    )


def slot_for_auth(seq, auth):
    return slot_for_credentials(_CODEX, seq, auth)


# --- internal probes (used directly by tests) --------------------------------


def _probe_slot(real_codex, timeout=10.0):
    """Probe the active slot. Returns (status, detail)."""
    return _oauth.probe_active_slot(timeout=timeout)


def _probe_slot_isolated(slot, snapshot_path, real_codex, timeout=30.0):
    """Compatibility wrapper — takes the old (slot, snapshot_path, ...) shape.

    The original signature passed an `auth.json` path; the new core protocol
    passes a slot directory. We accept either to support older callers/tests.
    """
    from pathlib import Path
    p = Path(snapshot_path)
    snapshot_dir = p.parent if p.name == "auth.json" else p
    return _oauth.probe_slot_isolated(slot, snapshot_dir, real_codex, timeout=timeout)


def _resolve(seq, target):
    return resolve_slot(seq, target)


__all__ = [
    "ACCOUNTS_DIR",
    "AUTH_PATH",
    "SEQUENCE_PATH",
    "STATE_PATH",
    "_probe_slot",
    "_probe_slot_isolated",
    "_resolve",
    "add_auth_file",
    "add_current",
    "current_slot",
    "load_sequence",
    "load_state",
    "next_free_slot",
    "reauth",
    "reconnect_broken",
    "remove",
    "resolve_slot",
    "rotate",
    "save_sequence",
    "save_state",
    "seed_slots",
    "slot_for_account_id",
    "slot_for_auth",
    "stash_active",
    "subprocess",
    "switch_to",
    "verify_all",
]
