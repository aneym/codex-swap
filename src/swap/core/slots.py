"""Generic slot CRUD: add, remove, switch, rotate, list, stash.

Delegates everything provider-specific (credentials I/O, identity parsing,
fingerprinting, slot snapshot copy) to the Provider object.
"""

from __future__ import annotations

import concurrent.futures
import shutil
import sys
import time
from pathlib import Path

from .provider import Provider
from .sequence import (
    load_sequence,
    load_state,
    next_free_slot,
    resolve_slot,
    save_sequence,
    save_state,
    slot_for_account_id,
)


def slot_for_credentials(provider: Provider, seq: dict, creds: dict) -> str | None:
    """Find the slot matching a credentials blob via identity or fingerprint."""
    if not creds:
        return None
    _, account_id, _ = provider.credentials_identity(creds)
    slot = slot_for_account_id(seq, account_id)
    if slot:
        return slot
    fingerprint = provider.credentials_fingerprint(creds)
    if not fingerprint:
        return None
    for slot, acc in seq.get("accounts", {}).items():
        if acc.get("auth_fingerprint") == fingerprint:
            return str(slot)
    return None


def current_slot(provider: Provider, paths: dict, seq: dict | None = None) -> str | None:
    seq = seq if seq is not None else load_sequence(paths["sequence"])
    creds = provider.read_live_credentials()
    if not creds:
        return None
    return slot_for_credentials(provider, seq, creds)


def stash_active(provider: Provider, paths: dict, seq: dict) -> None:
    """Snapshot the live creds back into their slot.

    Codex (and other OAuth flows) rotate refresh tokens on every successful
    refresh. Stashing before any swap-out keeps the slot's snapshot in sync.
    """
    creds = provider.read_live_credentials()
    if not creds:
        return
    slot = slot_for_credentials(provider, seq, creds)
    if not slot:
        return
    slot_dir = paths["accounts_dir"] / slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    provider.snapshot_to_slot(slot_dir)


def add_current(provider: Provider, paths: dict) -> tuple[int, str]:
    """Snapshot the live login as a new slot."""
    creds = provider.read_live_credentials()
    if not creds:
        return 1, f"No live credentials for {provider.display_name}. Run login first."
    return _add_from_credentials(provider, paths, creds, mark_active=True, source_label="")


def add_auth_file(
    provider: Provider,
    paths: dict,
    auth_path: Path,
    *,
    mark_active: bool = False,
    source_label: str = "",
) -> tuple[int, str]:
    """Snapshot an auth.json-like credentials file as a new slot.

    Codex-specific today; the path-based import flow is exposed via
    ExtraCommand for providers that have an "import-profile" notion.
    """
    from .jsonio import read_json

    auth_path = Path(auth_path).expanduser()
    creds = read_json(auth_path)
    if not creds:
        return 1, f"No credentials at {auth_path}. Run login first."

    seq = load_sequence(paths["sequence"])
    existing = slot_for_credentials(provider, seq, creds)
    if existing:
        email, account_id, _ = provider.credentials_identity(creds)
        fingerprint = provider.credentials_fingerprint(creds)
        label = email or source_label or account_id or fingerprint
        return 1, f"Account {label} already saved as slot {existing}."

    return _add_from_credentials(
        provider,
        paths,
        creds,
        mark_active=mark_active,
        source_label=source_label,
        source_path=auth_path,
    )


def _add_from_credentials(
    provider: Provider,
    paths: dict,
    creds: dict,
    *,
    mark_active: bool,
    source_label: str,
    source_path: Path | None = None,
) -> tuple[int, str]:
    email, account_id, plan_type = provider.credentials_identity(creds)
    fingerprint = provider.credentials_fingerprint(creds)
    if not (account_id or fingerprint):
        return 1, f"Credentials have no recognizable {provider.display_name} account identity."

    seq = load_sequence(paths["sequence"])
    existing = slot_for_credentials(provider, seq, creds)
    if existing:
        label = email or source_label or account_id or fingerprint
        return 1, f"Account {label} already saved as slot {existing}."

    slot = next_free_slot(seq)
    slot_dir = paths["accounts_dir"] / slot
    slot_dir.mkdir(parents=True, exist_ok=True)

    if source_path is not None:
        # Importing from a path; do a direct copy then sanitize via snapshot.
        # The snapshot callable handles per-provider naming.
        _import_from_path(provider, slot_dir, source_path)
    else:
        provider.snapshot_to_slot(slot_dir)

    seq["accounts"][slot] = {
        "email": email,
        "account_id": account_id,
        "auth_fingerprint": fingerprint,
        "auth_mode": creds.get("auth_mode", "") if isinstance(creds, dict) else "",
        "plan_type": plan_type,
        "label": source_label,
        "added_at": time.time(),
    }
    seq["sequence"] = sorted(set(seq["sequence"] + [slot]), key=int)
    save_sequence(paths["sequence"], seq)

    if mark_active:
        state = load_state(paths["state"])
        state["active_slot"] = slot
        state["last_switched_at"] = time.time()
        save_state(paths["state"], state)

    mode = (creds.get("auth_mode", "") if isinstance(creds, dict) else "") or "unknown auth"
    label = email or source_label or account_id or fingerprint
    return 0, f"Added slot {slot}: {label} ({plan_type or mode})"


def _import_from_path(provider: Provider, slot_dir: Path, source_path: Path) -> None:
    """For providers whose snapshot is a single file at a stable location.

    Codex stores `auth.json`. The provider's snapshot_to_slot copies the
    *live* credentials; importing from an arbitrary path requires a slightly
    different copy. We default to copying the file as `auth.json` in the slot
    dir — providers with multi-file slots should override via their CLI
    builder if/when they need import.
    """
    import os
    target = slot_dir / "auth.json"
    shutil.copy2(source_path, target)
    os.chmod(target, 0o600)


def remove(provider: Provider, paths: dict, target: str) -> tuple[int, str]:
    seq = load_sequence(paths["sequence"])
    slot = resolve_slot(seq, target)
    if slot is None:
        return 1, f"No matching slot for '{target}'."
    seq["accounts"].pop(slot, None)
    seq["sequence"] = [s for s in seq["sequence"] if str(s) != slot]
    save_sequence(paths["sequence"], seq)
    slot_dir = paths["accounts_dir"] / slot
    if slot_dir.exists():
        shutil.rmtree(slot_dir)
    provider.drop_slot_usage(slot)
    return 0, f"Removed slot {slot}."


def switch_to(provider: Provider, paths: dict, target: str) -> tuple[int, str]:
    seq = load_sequence(paths["sequence"])
    slot = resolve_slot(seq, target)
    if slot is None:
        return 1, f"No matching slot for '{target}'."
    slot_dir = paths["accounts_dir"] / slot
    if not slot_dir.exists():
        return 1, f"Snapshot missing at {slot_dir}."
    stash_active(provider, paths, seq)
    provider.restore_from_slot(slot_dir)
    state = load_state(paths["state"])
    state["active_slot"] = slot
    state["last_switched_at"] = time.time()
    save_state(paths["state"], state)
    acc = seq["accounts"][slot]
    return 0, f"Switched to slot {slot}: {acc.get('email') or '(no email)'}"


def rotate(provider: Provider, paths: dict) -> tuple[int, str]:
    seq = load_sequence(paths["sequence"])
    if not seq["sequence"]:
        return 1, "No accounts configured."
    sequence = [str(s) for s in seq["sequence"]]
    cur = current_slot(provider, paths, seq)
    idx = (sequence.index(cur) + 1) % len(sequence) if cur in sequence else 0
    return switch_to(provider, paths, sequence[idx])


def seed_slots(
    provider: Provider,
    paths: dict,
    slots: list[str],
    max_concurrency: int = 4,
    probe_timeout: float = 30.0,
) -> list[tuple[str, str, str]]:
    """Probe slots in parallel via isolated homes; merge results into usage store."""
    if not slots:
        return []
    seq = load_sequence(paths["sequence"])
    accounts = seq.get("accounts", {})
    targets = sorted({str(s) for s in slots if str(s) in accounts}, key=int)
    if not targets:
        return []

    real = provider.find_binary()
    workers = max(1, min(len(targets), max_concurrency))
    sys.stderr.write(
        f"{provider.cli_prog}: probing {len(targets)} slot(s) in parallel "
        f"(concurrency={workers}, timeout={probe_timeout:.0f}s)\n"
    )

    results: list[tuple[str, str, str]] = []
    seeds: dict[str, dict] = {}
    futures_map: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for slot in targets:
            snapshot = paths["accounts_dir"] / slot
            future = pool.submit(provider.probe_slot_isolated, slot, snapshot, real, probe_timeout)
            futures_map[future] = slot
        for future in concurrent.futures.as_completed(futures_map):
            slot = futures_map[future]
            try:
                slot, status, detail, record = future.result()
            except Exception as exc:  # noqa: BLE001
                status, detail, record = "error", f"probe raised: {exc!r}"[:200], None
            sys.stderr.write(f"{provider.cli_prog}: slot {slot}: {status} — {detail[:100]}\n")
            results.append((slot, status, detail))
            if isinstance(record, dict):
                seeds[slot] = record

    if seeds:
        provider.merge_into_persisted_usage(seeds)

    results.sort(key=lambda r: int(r[0]))
    return results
