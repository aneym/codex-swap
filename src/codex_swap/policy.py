"""Sticky routing policy for the Codex launcher."""

from __future__ import annotations

from .auth import atomic_write_json, read_json
from .paths import POLICY_PATH

DEFAULT_SPILLOVER_PRIMARY_PERCENT = 80.0
DEFAULT_SPILLOVER_SECONDARY_PERCENT = 95.0


def load_policy() -> dict:
    raw = read_json(POLICY_PATH) or {}
    if not isinstance(raw, dict):
        return {}
    return _normalize(raw)


def save_policy(policy: dict) -> dict:
    normalized = _normalize(policy)
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(POLICY_PATH, normalized)
    return normalized


def clear_policy() -> None:
    try:
        POLICY_PATH.unlink()
    except FileNotFoundError:
        pass


def policy_enabled(policy: dict | None) -> bool:
    return bool(policy and (policy.get("primary_slot") or policy.get("reserve_slots")))


def _normalize(raw: dict) -> dict:
    primary = raw.get("primary_slot")
    reserve_slots = raw.get("reserve_slots") or []
    if isinstance(reserve_slots, str):
        reserve_slots = [reserve_slots]

    out: dict = {
        "primary_slot": str(primary) if primary not in (None, "") else None,
        "reserve_slots": sorted({str(s) for s in reserve_slots if str(s)}, key=_slot_sort_key),
        "spillover_primary_percent": _pct(
            raw.get("spillover_primary_percent"),
            DEFAULT_SPILLOVER_PRIMARY_PERCENT,
        ),
        "spillover_secondary_percent": _pct(
            raw.get("spillover_secondary_percent"),
            DEFAULT_SPILLOVER_SECONDARY_PERCENT,
        ),
    }
    return out


def _pct(value, default: float) -> float:
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(100.0, pct))


def _slot_sort_key(slot: str) -> tuple[int, str]:
    return (0, f"{int(slot):08d}") if slot.isdigit() else (1, slot)
