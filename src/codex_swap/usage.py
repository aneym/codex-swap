"""Per-slot Codex rate-limit usage — durable persisted store with decay.

Design:
- One persisted record per slot, keyed by slot id, written to USAGE_CACHE.
- Records survive across launches; never wiped because a rescan didn't see them.
- A record's accuracy is preserved by `resets_at`-based decay: when the API's
  reset time has passed, `effective_used_percent` returns 0 for that window
  without re-measuring.
- Rollout scans merge new findings into the persisted store (highest
  `scanned_at` per slot wins). Seed probes also merge into the same store.
- The launcher reads the persisted store; it never auto-seeds. Seeding is
  explicit (`codex-swap seed`) or runs once on `onboard` / `add` finalize.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

from .auth import atomic_write_json, read_json
from .paths import LOGS_DB, SEQUENCE_PATH, SESSIONS_DIRS, USAGE_CACHE

ACCOUNT_RE = re.compile(r'user\.account_id="([0-9a-f-]{36})"')
CONV_RE = re.compile(r'conversation\.id=([0-9a-f-]{36})')

MAX_ROLLOUTS_SCAN = 80


def recent_rollouts(limit: int = MAX_ROLLOUTS_SCAN) -> list[Path]:
    """Most-recent rollouts under the user's CODEX_HOME (not isolated tmp dirs)."""
    files: list[Path] = []
    for root in SESSIONS_DIRS:
        if not root.exists():
            continue
        files.extend(root.rglob("rollout-*.jsonl"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def session_id_from_path(path: Path) -> str | None:
    parts = path.stem.split("-")
    if len(parts) < 5:
        return None
    return "-".join(parts[-5:])


def latest_rate_limits(path: Path) -> dict | None:
    """Return the latest non-null rate_limits snapshot in a rollout file."""
    snapshot: dict | None = None
    try:
        with path.open() as fh:
            for line in fh:
                if '"token_count"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = obj.get("payload") if isinstance(obj, dict) else None
                if not isinstance(payload, dict) or payload.get("type") != "token_count":
                    continue
                rl = payload.get("rate_limits")
                if isinstance(rl, dict) and (rl.get("primary") or rl.get("secondary")):
                    snapshot = rl
    except OSError:
        return None
    return snapshot


def session_account_map() -> dict[str, str]:
    """Map conversation_id -> account_id by scanning ~/.codex/logs_2.sqlite."""
    if not LOGS_DB.exists():
        return {}
    mapping: dict[str, str] = {}
    try:
        uri = f"file:{LOGS_DB}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        cutoff = int(time.time() - 8 * 86400)
        cur = conn.execute(
            "SELECT feedback_log_body FROM logs "
            "WHERE ts >= ? AND target = 'codex_otel.log_only' "
            "  AND feedback_log_body LIKE '%user.account_id=%' "
            "ORDER BY ts DESC LIMIT 4000",
            (cutoff,),
        )
        for (body,) in cur:
            if not body:
                continue
            am = ACCOUNT_RE.search(body)
            cm = CONV_RE.search(body)
            if not (am and cm):
                continue
            conv_id = cm.group(1)
            mapping.setdefault(conv_id, am.group(1))
        conn.close()
    except sqlite3.Error:
        pass
    return mapping


def scan_rollouts_for_usage() -> dict[str, dict]:
    """Find usage data per slot from local rollouts.

    Returns {slot: record} for every slot whose latest rollout had rate_limits.
    A "record" is the unified shape used by the persisted store:

        {primary, secondary, plan_type, scanned_at, source, source_path}
    """
    seq = read_json(SEQUENCE_PATH) or {}
    accounts = seq.get("accounts", {}) or {}
    if not accounts:
        return {}

    by_account = {acc.get("account_id"): slot for slot, acc in accounts.items() if acc.get("account_id")}
    sess_map = session_account_map()
    rollouts = recent_rollouts()

    found: dict[str, dict] = {}
    for path in rollouts:
        sid = session_id_from_path(path)
        if not sid:
            continue
        account_id = sess_map.get(sid)
        if not account_id:
            continue
        slot = by_account.get(account_id)
        if not slot or slot in found:
            continue
        rl = latest_rate_limits(path)
        if not rl:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = time.time()
        found[slot] = {
            "primary": rl.get("primary"),
            "secondary": rl.get("secondary"),
            "plan_type": rl.get("plan_type"),
            "scanned_at": mtime,
            "source": "rollout",
            "source_path": str(path),
        }
        if len(found) == len(by_account):
            break
    return found


# --- persisted store ----------------------------------------------------------


def load_persisted() -> dict[str, dict]:
    """Return the persisted per-slot usage store (mutable copy)."""
    raw = read_json(USAGE_CACHE) or {}
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def save_persisted(data: dict[str, dict]) -> None:
    """Atomically write the persisted store with a top-level timestamp."""
    payload = {"timestamp": time.time(), "data": data}
    atomic_write_json(USAGE_CACHE, payload)


def merge_into_persisted(updates: dict[str, dict]) -> dict[str, dict]:
    """Merge per-slot updates into the persisted store; higher scanned_at wins.

    Slots not present in `updates` keep their existing record. The picker
    therefore never loses sight of a slot just because the latest rescan
    didn't surface it.
    """
    persisted = load_persisted()
    changed = False
    for slot, new_rec in updates.items():
        if not isinstance(new_rec, dict):
            continue
        existing = persisted.get(slot) or {}
        new_ts = float(new_rec.get("scanned_at") or 0)
        old_ts = float(existing.get("scanned_at") or 0)
        if new_ts >= old_ts:
            persisted[slot] = new_rec
            changed = True
    if changed:
        save_persisted(persisted)
    return persisted


def drop_slot_record(slot: str) -> None:
    """Remove a single slot's record (used when a slot is removed from sequence)."""
    persisted = load_persisted()
    if str(slot) in persisted:
        persisted.pop(str(slot), None)
        save_persisted(persisted)


# --- decay --------------------------------------------------------------------


def effective_used_percent(window: dict | None, now: float | None = None) -> float | None:
    """`used_percent` corrected for the API's window reset.

    Once `resets_at` has passed, the window has reset server-side, so the
    persisted percent is stale; we report 0% for that window.
    Returns None when there's no data to decay.
    """
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


def effective_record(rec: dict | None, now: float | None = None) -> dict | None:
    """Return a copy of `rec` with decayed `used_percent` per window.

    The decayed value is written to a parallel `used_percent_effective` key
    so callers can compare to the raw value if needed.
    """
    if not isinstance(rec, dict):
        return None
    now = now if now is not None else time.time()
    out = dict(rec)
    for key in ("primary", "secondary"):
        window = rec.get(key)
        if not isinstance(window, dict):
            continue
        eff = effective_used_percent(window, now)
        new_window = dict(window)
        if eff is not None:
            new_window["used_percent_effective"] = eff
            if eff != window.get("used_percent"):
                new_window["window_reset"] = True
        out[key] = new_window
    return out


# --- public refresh entry points ---------------------------------------------


def refresh_from_rollouts() -> dict[str, dict]:
    """Cheap rollout scan; merges new findings into the persisted store."""
    fresh = scan_rollouts_for_usage()
    if fresh:
        return merge_into_persisted(fresh)
    return load_persisted()


# --- back-compat shims (used by older callsites and tests) -------------------


def compute_usage() -> dict:
    """Back-compat alias for the rollout scanner. Returns only freshly-found data."""
    return scan_rollouts_for_usage()


def refresh_cache() -> dict:
    """Back-compat alias mirroring the old return shape `{timestamp, data}`."""
    data = refresh_from_rollouts()
    return {"timestamp": time.time(), "data": data}


def cached(max_age: int) -> dict:
    """Back-compat: returns persisted data. `max_age` is ignored — the store
    is durable now and decays per-window via `effective_used_percent`."""
    _ = max_age
    return load_persisted()
