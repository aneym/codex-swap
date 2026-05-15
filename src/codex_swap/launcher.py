"""Compat shim — re-export launcher helpers with the codex provider pre-bound."""

from __future__ import annotations

from swap.core.launcher import (
    _label as _core_label,
)
from swap.core.launcher import (
    _policy_score as _core_policy_score,
)
from swap.core.launcher import (
    _primary_is_usable as _core_primary_is_usable,
)
from swap.core.launcher import (
    _slot_score as _core_slot_score,
)
from swap.core.launcher import (
    _unknown_slots,
)
from swap.core.launcher import (
    choose as _core_choose,
)
from swap.core.launcher import (
    launch as _core_launch,
)
from swap.core.launcher import (
    maybe_switch as _core_maybe_switch,
)
from swap.core.paths import provider_paths
from swap.providers.codex import CODEX as _CODEX

NEAR_CAP_PERCENT = _CODEX.near_cap_percent


def _slot_score(slot, usage):
    return _core_slot_score(_CODEX, slot, usage)


def _policy_score(slot, usage, reserve_slots):
    return _core_policy_score(_CODEX, slot, usage, reserve_slots)


def _primary_is_usable(slot, usage, policy):
    return _core_primary_is_usable(_CODEX, slot, usage, policy)


def _choose(seq, usage, policy=None):
    return _core_choose(_CODEX, seq, usage, policy)


def _label(seq, slot, usage):
    return _core_label(_CODEX, seq, slot, usage)


def maybe_switch(skip_auto=False, pinned_slot=None):
    return _core_maybe_switch(_CODEX, provider_paths("codex"), skip_auto=skip_auto, pinned_slot=pinned_slot)


def launch(args, skip_auto=False, pinned_slot=None):
    return _core_launch(_CODEX, provider_paths("codex"), args, skip_auto=skip_auto, pinned_slot=pinned_slot)


__all__ = [
    "NEAR_CAP_PERCENT",
    "_choose",
    "_label",
    "_policy_score",
    "_primary_is_usable",
    "_slot_score",
    "_unknown_slots",
    "launch",
    "maybe_switch",
]
