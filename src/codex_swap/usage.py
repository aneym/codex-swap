"""Compat shim — re-exports from `swap.providers.codex.usage`."""

# Tests do `monkeypatch.setattr(usage_mod, "USAGE_CACHE", tmp_path / "usage.json")`.
# We need the module-level constant to be a real attribute that mutates the
# provider module's cache target. Easiest: thread it through a property-style
# shim that the underlying module reads at call time.
from swap.providers.codex import usage as _provider_usage  # noqa: E402
from swap.providers.codex.usage import (
    ACCOUNT_RE,
    CONV_RE,
    MAX_ROLLOUTS_SCAN,
    _build_record,
    _is_useful_snapshot,  # noqa: F401
    _merge_record,
    cached,
    compute_usage,
    drop_slot_record,
    effective_record,
    effective_used_percent,
    is_exhausted,
    is_exhaustion_signal,
    latest_rate_limits,
    load_persisted,
    merge_into_persisted,
    recent_rollouts,
    refresh_cache,
    refresh_from_rollouts,
    save_persisted,
    scan_rollouts_for_usage,
    session_account_map,
    session_id_from_path,
)

# Tests reassign `USAGE_CACHE` on this shim; we mirror the assignment back into
# the provider module by overriding its `_usage_cache()` resolver.
USAGE_CACHE = _provider_usage._usage_cache()


def _shim_usage_cache():
    return USAGE_CACHE


_provider_usage._usage_cache = _shim_usage_cache  # type: ignore[attr-defined]

__all__ = [
    "ACCOUNT_RE",
    "CONV_RE",
    "MAX_ROLLOUTS_SCAN",
    "USAGE_CACHE",
    "_build_record",
    "_is_useful_snapshot",
    "_merge_record",
    "cached",
    "compute_usage",
    "drop_slot_record",
    "effective_record",
    "effective_used_percent",
    "is_exhausted",
    "is_exhaustion_signal",
    "latest_rate_limits",
    "load_persisted",
    "merge_into_persisted",
    "recent_rollouts",
    "refresh_cache",
    "refresh_from_rollouts",
    "save_persisted",
    "scan_rollouts_for_usage",
    "session_account_map",
    "session_id_from_path",
]
