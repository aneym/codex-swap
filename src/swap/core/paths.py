"""Per-provider filesystem layout under `~/.swap/<provider>/`.

A provider's data root looks like:

    ~/.swap/<provider>/
      accounts/<N>/...           # per-slot snapshot directory
      sequence.json              # slot order + identity metadata
      state.json                 # last-switched slot + timestamp
      policy.json                # optional sticky-primary / reserve policy
      cache/usage.json           # durable per-slot usage store

Codex historically lived at `~/.codex-swap/`. The migrator at
`swap.core.migrate` is the only path that touches the legacy directory.
"""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()


def swap_root_base() -> Path:
    """Top-level root of all providers' swap state.

    `SWAP_ROOT` overrides for tests; otherwise it's `~/.swap/`.
    """
    override = os.environ.get("SWAP_ROOT")
    if override:
        return Path(override)
    return HOME / ".swap"


def provider_root(name: str) -> Path:
    """Return `~/.swap/<name>/`, or a per-provider env override.

    Per-provider overrides (e.g. `CODEX_SWAP_ROOT`) are honored when set; tests
    and the legacy migrator rely on them.
    """
    env_key = f"{name.upper()}_SWAP_ROOT"
    override = os.environ.get(env_key)
    if override:
        return Path(override)
    return swap_root_base() / name


def provider_paths(name: str) -> dict:
    """All well-known paths for a provider's swap state."""
    root = provider_root(name)
    return {
        "root": root,
        "accounts_dir": root / "accounts",
        "sequence": root / "sequence.json",
        "state": root / "state.json",
        "policy": root / "policy.json",
        "usage_cache": root / "cache" / "usage.json",
    }
