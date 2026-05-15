"""Compat shim — re-export the onboard flow with codex pre-bound."""

from __future__ import annotations

from swap.core.onboard import onboard as _core_onboard
from swap.core.paths import provider_paths
from swap.providers.codex import CODEX as _CODEX


def onboard(count: int) -> int:
    return _core_onboard(_CODEX, provider_paths("codex"), count)


__all__ = ["onboard"]
