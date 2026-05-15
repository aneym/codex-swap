"""Per-provider sequence.json and state.json IO.

The sequence file lists slots in order and carries non-secret identity metadata
per slot (email, account_id, plan_type, label, auth_fingerprint, added_at).
state.json carries `active_slot` + `last_switched_at`.
"""

from __future__ import annotations

from pathlib import Path

from .jsonio import atomic_write_json, read_json


def load_sequence(sequence_path: Path) -> dict:
    data = read_json(sequence_path) or {}
    data.setdefault("sequence", [])
    data.setdefault("accounts", {})
    return data


def save_sequence(sequence_path: Path, data: dict) -> None:
    atomic_write_json(sequence_path, data)


def load_state(state_path: Path) -> dict:
    return read_json(state_path) or {}


def save_state(state_path: Path, data: dict) -> None:
    atomic_write_json(state_path, data)


def slot_for_account_id(seq: dict, account_id: str) -> str | None:
    if not account_id:
        return None
    for slot, acc in seq.get("accounts", {}).items():
        if acc.get("account_id") == account_id:
            return str(slot)
    return None


def slot_for_fingerprint(seq: dict, fingerprint: str) -> str | None:
    if not fingerprint:
        return None
    for slot, acc in seq.get("accounts", {}).items():
        if acc.get("auth_fingerprint") == fingerprint:
            return str(slot)
    return None


def next_free_slot(seq: dict) -> str:
    used = {int(s) for s in seq.get("accounts", {}) if str(s).isdigit()}
    n = 1
    while n in used:
        n += 1
    return str(n)


def resolve_slot(seq: dict, target: str) -> str | None:
    """Resolve any slot reference — number, email, account_id, fingerprint, label."""
    target = str(target)
    for slot, acc in seq.get("accounts", {}).items():
        if (
            str(slot) == target
            or acc.get("email") == target
            or acc.get("account_id") == target
            or acc.get("auth_fingerprint") == target
            or acc.get("label") == target
        ):
            return str(slot)
    return None
