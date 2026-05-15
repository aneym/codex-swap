"""Generic reauth / verify-all / reconnect-broken flows.

Login is provider-specific (`provider.start_login`); the orchestration around
it (stash, clear, run login, re-snapshot, verify metadata) lives here.
"""

from __future__ import annotations

import time

from .provider import Provider
from .sequence import (
    load_sequence,
    load_state,
    resolve_slot,
    save_sequence,
    save_state,
)
from .slots import current_slot, stash_active, switch_to


def reauth(provider: Provider, paths: dict, target: str) -> tuple[int, str]:
    """Re-mint a slot via the provider's interactive login flow.

    NEVER calls provider-side logout — that revokes refresh tokens server-side,
    killing every other slot whose snapshot pre-dates the revoke. We clear the
    local creds and run a fresh login.
    """
    seq = load_sequence(paths["sequence"])
    slot = resolve_slot(seq, target)
    if slot is None:
        return 1, f"No matching slot for '{target}'."
    expected_email = seq["accounts"][slot].get("email") or ""
    expected_account_id = seq["accounts"][slot].get("account_id") or ""

    stash_active(provider, paths, seq)
    provider.clear_live_credentials()

    print(f"\nRe-minting slot {slot} ({expected_email or 'unknown'}).")
    print(f"A browser will open. Sign in to that {provider.display_name} account.")
    print("If you sign in to a different account this slot will be rejected.\n")

    rc = provider.start_login()
    if rc != 0:
        return rc, f"{provider.display_name} login exited non-zero. Slot snapshot left unchanged."

    creds = provider.read_live_credentials()
    if not creds:
        return 1, f"{provider.display_name} login finished but credentials were not created."

    new_email, new_account_id, new_plan = provider.credentials_identity(creds)
    if expected_email and new_email and new_email != expected_email:
        return 2, (
            f"Email mismatch: expected {expected_email}, got {new_email}.\n"
            f"Slot {slot}'s snapshot left untouched. Run `{provider.cli_prog} switch {slot}` to roll back, "
            f"or `{provider.cli_prog} add` to register the new email as a separate slot."
        )

    slot_dir = paths["accounts_dir"] / slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    provider.snapshot_to_slot(slot_dir)

    note = ""
    if expected_account_id and new_account_id and new_account_id != expected_account_id:
        note = f" (account_id changed: {expected_account_id[:8]}… → {new_account_id[:8]}…)"
    seq["accounts"][slot]["email"] = new_email or expected_email
    seq["accounts"][slot]["account_id"] = new_account_id or expected_account_id
    if new_plan:
        seq["accounts"][slot]["plan_type"] = new_plan
    save_sequence(paths["sequence"], seq)

    state = load_state(paths["state"])
    state["active_slot"] = slot
    state["last_switched_at"] = time.time()
    save_state(paths["state"], state)
    return 0, f"Slot {slot} re-minted: {new_email}{note}"


def verify_all(provider: Provider, paths: dict) -> list[tuple[str, str, str]]:
    """Switch into each slot, probe, report status. Restore prior slot after."""
    seq = load_sequence(paths["sequence"])
    if not seq.get("accounts"):
        return []
    starting = current_slot(provider, paths, seq)
    results: list[tuple[str, str, str]] = []
    for slot in sorted(seq["accounts"], key=lambda s: int(s)):
        rc, _ = switch_to(provider, paths, slot)
        if rc != 0:
            results.append((slot, "switch_failed", ""))
            continue
        status, detail = provider.probe_active_slot()
        # Capture rotated tokens before we move to the next slot.
        stash_active(provider, paths, load_sequence(paths["sequence"]))
        results.append((slot, status, detail))

    if starting and starting in seq["accounts"]:
        switch_to(provider, paths, starting)
    return results


def reconnect_broken(provider: Provider, paths: dict) -> tuple[int, list[str], list[str]]:
    """Verify every slot, then walk the user through reauth for each broken one."""
    results = verify_all(provider, paths)
    broken_slots = [slot for slot, status, _ in results if status == "broken"]
    if not broken_slots:
        return 0, [], []

    seq = load_sequence(paths["sequence"])
    print(f"\nFound {len(broken_slots)} broken slot(s). Walking you through a fresh login for each.")
    print(f"(We'll never call '{provider.name} logout', so your other slots stay safe.)\n")

    fixed: list[str] = []
    still_broken: list[str] = []
    for slot in broken_slots:
        email = seq["accounts"].get(slot, {}).get("email") or "(unknown email)"
        print(f"\n--- Slot {slot}: {email} ---")
        rc, msg = reauth(provider, paths, slot)
        print(msg)
        if rc == 0:
            fixed.append(slot)
        else:
            still_broken.append(slot)

    return (1 if still_broken else 0), fixed, still_broken
