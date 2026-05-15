"""Codex CLI entry points.

`main()` powers the `codex-swap` console script.
`cx_main()` powers the `cx` console script (auto-launch shim with env knobs).
"""

from __future__ import annotations

import os
import sys

from ...core.cli_base import run as core_run
from ...core.launcher import launch as core_launch
from ...core.migrate import run_all_migrations
from ...core.paths import provider_paths
from . import CODEX


def main(argv: list[str] | None = None) -> int:
    return core_run(CODEX, argv)


def cx_main(argv: list[str] | None = None) -> int:
    """Entry point for `cx` — equivalent to `codex-swap launch`.

    Pre-parses `--codex-swap-slot` and `--codex-swap-skip-auto` so the user can
    pass them without colliding with codex's own flag namespace. Env vars
    `CODEX_SWAP_SLOT`, `CXSWAP_SLOT`, `CODEX_SWAP_SKIP_AUTO`, `CXSWAP_SKIP_AUTO`
    override CLI flags.
    """
    run_all_migrations()
    args = list(sys.argv[1:] if argv is None else argv)
    skip_auto = False
    pinned = None
    forwarded: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--codex-swap-slot" and i + 1 < len(args):
            pinned = args[i + 1]
            i += 2
            continue
        if a == "--codex-swap-skip-auto":
            skip_auto = True
            i += 1
            continue
        forwarded.append(a)
        i += 1

    env = os.environ
    if "CODEX_SWAP_SKIP_AUTO" in env or "CXSWAP_SKIP_AUTO" in env:
        skip_auto = True
    env_slot = env.get("CODEX_SWAP_SLOT") or env.get("CXSWAP_SLOT")
    if env_slot:
        pinned = env_slot

    core_launch(
        CODEX,
        provider_paths("codex"),
        forwarded,
        skip_auto=skip_auto,
        pinned_slot=pinned,
    )
    return 0
