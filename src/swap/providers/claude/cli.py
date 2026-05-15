"""Claude CLI entry points.

``main()`` powers the ``claude-swap`` console script.
``cs_main()`` powers the ``cs`` console script — v0.1 stub.

v0.1 explicitly omits a launcher. The provider task brief calls out that
``cs`` should print an unimplemented message and exit 1 rather than do
anything clever, because the launcher (slot picker + exec) needs a working
probe + usage flow that v0.1 doesn't have yet.
"""

from __future__ import annotations

import sys

from ...core.cli_base import run as core_run
from . import CLAUDE


def main(argv: list[str] | None = None) -> int:
    return core_run(CLAUDE, argv)


def cs_main(argv: list[str] | None = None) -> int:
    _ = argv
    sys.stderr.write(
        "claude-swap: `cs` launcher not implemented in v0.1. "
        "Run `claude-swap switch <slot>` then `claude` directly.\n"
    )
    return 1
