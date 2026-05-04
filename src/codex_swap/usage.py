"""Compute per-slot Codex rate-limit usage from local rollouts."""

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
        # logs.ts is in seconds. Cover both rate-limit windows.
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


def compute_usage() -> dict:
    """Return {slot: {primary, secondary, plan_type, scanned_at, source_rollout}}."""
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
        found[slot] = {
            "primary": rl.get("primary"),
            "secondary": rl.get("secondary"),
            "plan_type": rl.get("plan_type"),
            "source_rollout": str(path),
            "scanned_at": time.time(),
        }
        if len(found) == len(by_account):
            break
    return found


def refresh_cache() -> dict:
    data = compute_usage()
    payload = {"timestamp": time.time(), "data": data}
    atomic_write_json(USAGE_CACHE, payload)
    return payload


def cached(max_age: int) -> dict:
    raw = read_json(USAGE_CACHE)
    if not raw or not isinstance(raw.get("data"), dict):
        return {}
    ts = raw.get("timestamp")
    if not isinstance(ts, (int, float)):
        return {}
    if (time.time() - ts) >= max_age:
        return {}
    return raw["data"]
