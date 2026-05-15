"""Compat shim — re-export from `swap.core.policy` with codex paths."""

from __future__ import annotations

from swap.core.paths import provider_paths
from swap.core.policy import (
    DEFAULT_SPILLOVER_PRIMARY_PERCENT,
    DEFAULT_SPILLOVER_SECONDARY_PERCENT,
    _normalize,
    _pct,
    _slot_sort_key,
    policy_enabled,
)
from swap.core.policy import (
    clear_policy as _core_clear_policy,
)
from swap.core.policy import (
    load_policy as _core_load_policy,
)
from swap.core.policy import (
    save_policy as _core_save_policy,
)


def _policy_path():
    return provider_paths("codex")["policy"]


def load_policy():
    return _core_load_policy(_policy_path())


def save_policy(policy):
    return _core_save_policy(_policy_path(), policy)


def clear_policy():
    _core_clear_policy(_policy_path())


__all__ = [
    "DEFAULT_SPILLOVER_PRIMARY_PERCENT",
    "DEFAULT_SPILLOVER_SECONDARY_PERCENT",
    "_normalize",
    "_pct",
    "_slot_sort_key",
    "clear_policy",
    "load_policy",
    "policy_enabled",
    "save_policy",
]
