"""One-time migrators for legacy data layouts.

The original codex-swap stored state at `~/.codex-swap/`. The new package puts
each provider under `~/.swap/<provider>/`. The migrator runs on every command
entry; the second run is a no-op.

`CODEX_SWAP_ROOT` (and any future `<PROVIDER>_SWAP_ROOT`) override the
target. The migrator honors those overrides by reading them at call time.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .paths import provider_root


def migrate_codex_legacy(*, quiet: bool = False) -> bool:
    """Move `~/.codex-swap/` to the provider's root, atomically. Idempotent.

    Returns True iff a migration actually happened. The user can set
    `CODEX_SWAP_ROOT` to override the target root; if so, we move into that.
    If the legacy directory doesn't exist, or the target already does, no-op.
    """
    legacy = Path(os.environ.get("CODEX_SWAP_LEGACY_ROOT") or Path.home() / ".codex-swap")
    target = provider_root("codex")
    if not legacy.exists():
        return False
    if target.exists():
        # Both exist — don't clobber. The user is on the new layout already; the
        # legacy dir is stale state they can clean up by hand.
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target))
    if not quiet and not os.environ.get("SWAP_MIGRATE_QUIET"):
        sys.stderr.write(f"swap: migrated {legacy} -> {target}\n")
    return True


def run_all_migrations(*, quiet: bool = False) -> None:
    """Run every one-time migrator. Called early in every CLI entry point."""
    migrate_codex_legacy(quiet=quiet)
