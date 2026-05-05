"""Slot CRUD: add, remove, list, switch, reauth."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from .auth import (
    atomic_write_json,
    auth_fingerprint,
    auth_identity,
    current_auth,
    read_json,
)
from .codex import codex_env, find_real_codex
from .paths import (
    ACCOUNTS_DIR,
    AUTH_PATH,
    SEQUENCE_PATH,
    STATE_PATH,
)


def load_sequence() -> dict:
    data = read_json(SEQUENCE_PATH) or {}
    data.setdefault("sequence", [])
    data.setdefault("accounts", {})
    return data


def save_sequence(data: dict) -> None:
    atomic_write_json(SEQUENCE_PATH, data)


def load_state() -> dict:
    return read_json(STATE_PATH) or {}


def save_state(data: dict) -> None:
    atomic_write_json(STATE_PATH, data)


def slot_for_account_id(seq: dict, account_id: str) -> str | None:
    if not account_id:
        return None
    for slot, acc in seq.get("accounts", {}).items():
        if acc.get("account_id") == account_id:
            return str(slot)
    return None


def slot_for_auth(seq: dict, auth: dict) -> str | None:
    if not auth:
        return None
    _, account_id, _ = auth_identity(auth)
    slot = slot_for_account_id(seq, account_id)
    if slot:
        return slot
    fingerprint = auth_fingerprint(auth)
    if not fingerprint:
        return None
    for slot, acc in seq.get("accounts", {}).items():
        if acc.get("auth_fingerprint") == fingerprint:
            return str(slot)
    return None


def current_slot(seq: dict | None = None) -> str | None:
    seq = seq or load_sequence()
    auth = current_auth()
    if not auth:
        return None
    return slot_for_auth(seq, auth)


def next_free_slot(seq: dict) -> str:
    used = {int(s) for s in seq.get("accounts", {}) if str(s).isdigit()}
    n = 1
    while n in used:
        n += 1
    return str(n)


def stash_active(seq: dict) -> None:
    """Snapshot the live auth.json into its slot dir.

    Codex rotates the refresh_token on every successful refresh. Stashing
    before any other write keeps the slot's snapshot in sync, so the next
    swap-in won't replay a single-use token.
    """
    auth = current_auth()
    if not auth:
        return
    slot = slot_for_auth(seq, auth)
    if not slot:
        return
    target = ACCOUNTS_DIR / slot / "auth.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUTH_PATH, target)
    os.chmod(target, 0o600)


def add_current() -> tuple[int, str]:
    """Snapshot the live login as a new slot. Returns (rc, message)."""
    return add_auth_file(AUTH_PATH, mark_active=True)


def add_auth_file(
    auth_path: Path,
    *,
    mark_active: bool = False,
    source_label: str = "",
) -> tuple[int, str]:
    """Snapshot an auth.json file as a new slot. Returns (rc, message)."""
    auth_path = Path(auth_path).expanduser()
    auth = read_json(auth_path)
    path_label = str(auth_path)
    if not auth:
        return 1, f"No auth.json at {path_label}. Run `codex login` first."
    email, account_id, plan_type = auth_identity(auth)
    fingerprint = auth_fingerprint(auth)
    if not (account_id or fingerprint):
        return 1, "auth.json has no recognizable Codex account identity."

    seq = load_sequence()
    existing = slot_for_auth(seq, auth)
    if existing:
        label = email or source_label or account_id or fingerprint
        return 1, f"Account {label} already saved as slot {existing}."

    slot = next_free_slot(seq)
    target = ACCOUNTS_DIR / slot / "auth.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(auth_path, target)
    os.chmod(target, 0o600)

    seq["accounts"][slot] = {
        "email": email,
        "account_id": account_id,
        "auth_fingerprint": fingerprint,
        "auth_mode": auth.get("auth_mode", ""),
        "plan_type": plan_type,
        "label": source_label,
        "added_at": time.time(),
    }
    seq["sequence"] = sorted(set(seq["sequence"] + [slot]), key=int)
    save_sequence(seq)

    if mark_active:
        state = load_state()
        state["active_slot"] = slot
        state["last_switched_at"] = time.time()
        save_state(state)
    mode = auth.get("auth_mode", "") or "unknown auth"
    label = email or source_label or account_id or fingerprint
    return 0, f"Added slot {slot}: {label} ({plan_type or mode})"


def remove(target: str) -> tuple[int, str]:
    seq = load_sequence()
    slot = _resolve(seq, target)
    if slot is None:
        return 1, f"No matching slot for '{target}'."
    seq["accounts"].pop(slot, None)
    seq["sequence"] = [s for s in seq["sequence"] if str(s) != slot]
    save_sequence(seq)
    slot_dir = ACCOUNTS_DIR / slot
    if slot_dir.exists():
        shutil.rmtree(slot_dir)
    return 0, f"Removed slot {slot}."


def switch_to(target: str) -> tuple[int, str]:
    seq = load_sequence()
    slot = _resolve(seq, target)
    if slot is None:
        return 1, f"No matching slot for '{target}'."
    src = ACCOUNTS_DIR / slot / "auth.json"
    if not src.exists():
        return 1, f"Snapshot missing at {src}."
    stash_active(seq)
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, AUTH_PATH)
    os.chmod(AUTH_PATH, 0o600)
    state = load_state()
    state["active_slot"] = slot
    state["last_switched_at"] = time.time()
    save_state(state)
    acc = seq["accounts"][slot]
    return 0, f"Switched to slot {slot}: {acc.get('email') or '(no email)'}"


def rotate() -> tuple[int, str]:
    seq = load_sequence()
    if not seq["sequence"]:
        return 1, "No accounts configured."
    sequence = [str(s) for s in seq["sequence"]]
    cur = current_slot(seq)
    idx = (sequence.index(cur) + 1) % len(sequence) if cur in sequence else 0
    return switch_to(sequence[idx])


def reauth(target: str) -> tuple[int, str]:
    """Re-mint a slot via 'codex login' without server-side revoke.

    NEVER call 'codex logout' here — it revokes the refresh token at the
    OAuth provider, killing every other slot whose snapshot pre-dates the
    revoke. We just clear the local auth.json and run a fresh login.
    """
    seq = load_sequence()
    slot = _resolve(seq, target)
    if slot is None:
        return 1, f"No matching slot for '{target}'."
    expected_email = seq["accounts"][slot].get("email") or ""
    expected_account_id = seq["accounts"][slot].get("account_id") or ""

    stash_active(seq)
    if AUTH_PATH.exists():
        AUTH_PATH.unlink()

    real = find_real_codex()
    print(f"\nRe-minting slot {slot} ({expected_email or 'unknown'}).")
    print("A browser will open. Sign in to that ChatGPT Pro account.")
    print("If you sign in to a different account this slot will be rejected.\n")

    rc = subprocess.run([real, "login"], env=codex_env()).returncode
    if rc != 0:
        return rc, "codex login exited non-zero. Slot snapshot left unchanged."
    if not AUTH_PATH.exists():
        return 1, "codex login finished but auth.json was not created."

    new_email, new_account_id, new_plan = auth_identity(current_auth() or {})
    if expected_email and new_email and new_email != expected_email:
        return 2, (
            f"Email mismatch: expected {expected_email}, got {new_email}.\n"
            f"Slot {slot}'s snapshot left untouched. Run `codex-swap switch {slot}` to roll back, "
            "or `codex-swap add` to register the new email as a separate slot."
        )

    target_path = ACCOUNTS_DIR / slot / "auth.json"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUTH_PATH, target_path)
    os.chmod(target_path, 0o600)

    note = ""
    if expected_account_id and new_account_id and new_account_id != expected_account_id:
        note = f" (account_id changed: {expected_account_id[:8]}… → {new_account_id[:8]}…)"
    seq["accounts"][slot]["email"] = new_email or expected_email
    seq["accounts"][slot]["account_id"] = new_account_id or expected_account_id
    if new_plan:
        seq["accounts"][slot]["plan_type"] = new_plan
    save_sequence(seq)

    state = load_state()
    state["active_slot"] = slot
    state["last_switched_at"] = time.time()
    save_state(state)
    return 0, f"Slot {slot} re-minted: {new_email}{note}"


# Phrases that ONLY fire when codex's basic auth refresh is dead.
# Drops broad strings like '401 Unauthorized' (which the codex_apps MCP also
# emits when its separate connector OAuth is revoked — non-fatal for codex).
_BAD_TOKEN_PHRASES = (
    "Failed to refresh token",
    "refresh_token_reused",
    "refresh_token_revoked",
    "Your refresh token has already been used",
    "Your refresh token was revoked",
    "your refresh token was already used",
    "your refresh token was revoked",
    "token_invalidated",
)


def _looks_broken(text: str) -> str | None:
    for phrase in _BAD_TOKEN_PHRASES:
        if phrase in text:
            return phrase
    return None


_RATE_LIMIT_PHRASES = (
    "You've hit your usage limit",
    "rate_limit_reached",
    "usage limit. Visit",
    "limit_reached_type",
)


def _probe_slot(real_codex: str, timeout: float = 10.0) -> tuple[str, str]:
    """Probe the active slot. Returns (status, detail).

    Status is one of:
      - 'ok'           - auth refreshes, responses stream
      - 'rate_limited' - auth fine, but window quota exhausted
      - 'broken'       - refresh_token is dead, needs `codex-swap reauth`
    """
    """Run a real auth-exercising probe against the active slot.

    Spawns `codex exec "ok"` with a hard timeout. Codex must refresh the
    access token before any API call, so a dead refresh_token surfaces in
    stderr within the first second or two as one of the
    codex_login::auth::manager error phrases. Costs ~50 tokens on success.

    A timeout without a known-bad phrase means codex is happily streaming
    a response and basic auth is fine.
    """
    verify_model = os.environ.get("CODEX_SWAP_VERIFY_MODEL", "gpt-5.4-mini")
    cmd = [
        real_codex,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
    ]
    if verify_model:
        cmd.extend(["-m", verify_model])
    cmd.append("Reply exactly ok and do not use tools.")
    try:
        proc = subprocess.run(
            cmd,
            env=codex_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        combined = _as_text(proc.stdout) + "\n" + _as_text(proc.stderr)
        rc = proc.returncode
    except subprocess.TimeoutExpired as exc:
        combined = _as_text(exc.stdout) + "\n" + _as_text(exc.stderr)
        rc = None  # streaming, no exit yet

    bad = _looks_broken(combined)
    if bad:
        return "broken", _line_with(combined, bad)
    if any(p in combined for p in _RATE_LIMIT_PHRASES):
        return "rate_limited", _line_with(combined, _first_match(combined, _RATE_LIMIT_PHRASES))
    if rc is None:
        return "ok", "auth ok (response was streaming when timeout fired)"
    if rc == 0:
        return "ok", "auth ok"
    last_err = ""
    for line in reversed(combined.splitlines()):
        if line.strip():
            last_err = line.strip()
            break
    return "error", f"probe exited {rc}: {last_err[:120]}"


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _first_match(text: str, phrases) -> str:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return ""


def _line_with(text: str, phrase: str) -> str:
    for line in text.splitlines():
        if phrase in line:
            return line.strip()[:140]
    return phrase


def verify_all() -> list[tuple[str, str, str]]:
    """Switch into each slot, exercise auth with a real call, report status.

    Returns [(slot, status, detail), ...]. Status is 'ok', 'rate_limited',
    'broken', or 'error'.
    Restores the active slot afterwards. Each successful probe also captures
    any rotated tokens via stash_active so snapshots stay current.
    """
    seq = load_sequence()
    if not seq.get("accounts"):
        return []
    real = find_real_codex()
    starting = current_slot(seq)
    results: list[tuple[str, str, str]] = []
    for slot in sorted(seq["accounts"], key=lambda s: int(s)):
        rc, _ = switch_to(slot)
        if rc != 0:
            results.append((slot, "switch_failed", ""))
            continue
        status, detail = _probe_slot(real)
        # Capture rotated tokens before we move to the next slot.
        stash_active(load_sequence())
        results.append((slot, status, detail))

    if starting and starting in seq["accounts"]:
        switch_to(starting)
    return results


def reconnect_broken() -> tuple[int, list[str], list[str]]:
    """Verify every slot, then reauth any that came back broken.

    Returns (overall_rc, fixed, still_broken). The user is prompted to log
    into each broken slot's expected account in turn.
    """
    results = verify_all()
    broken_slots = [slot for slot, status, _ in results if status == "broken"]
    if not broken_slots:
        return 0, [], []

    seq = load_sequence()
    print(f"\nFound {len(broken_slots)} broken slot(s). Walking you through a fresh login for each.")
    print("(We'll never call 'codex logout', so your other slots stay safe.)\n")

    fixed: list[str] = []
    still_broken: list[str] = []
    for slot in broken_slots:
        email = seq["accounts"].get(slot, {}).get("email") or "(unknown email)"
        print(f"\n--- Slot {slot}: {email} ---")
        rc, msg = reauth(slot)
        print(msg)
        if rc == 0:
            fixed.append(slot)
        else:
            still_broken.append(slot)

    return (1 if still_broken else 0), fixed, still_broken


def _resolve(seq: dict, target: str) -> str | None:
    target = str(target)
    for slot, acc in seq["accounts"].items():
        if (
            str(slot) == target
            or acc.get("email") == target
            or acc.get("account_id") == target
            or acc.get("auth_fingerprint") == target
            or acc.get("label") == target
        ):
            return str(slot)
    return None
