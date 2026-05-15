"""Locate the real Claude Code CLI binary on PATH.

Mirrors ``swap.providers.codex.binary`` shape, but no ``--version`` parsing
(every release returns a stable string; we don't pick best-of-N).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Stuff like Superset wrappers; skip if found on PATH so we never invoke the
# proxy when we really want the real `claude` binary.
SKIP_DIRS = ("/.superset/", "/.superset-")


def find_binary() -> str:
    """Return the first real ``claude`` binary on PATH."""
    explicit = os.environ.get("CLAUDE_SWAP_REAL_CLAUDE")
    if explicit and Path(explicit).exists():
        return explicit

    for directory in os.environ.get("PATH", "").split(":"):
        if not directory or any(s in directory for s in SKIP_DIRS):
            continue
        candidate = Path(directory) / "claude"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    fallback = shutil.which("claude")
    if fallback:
        return fallback
    sys.stderr.write("claude-swap: claude binary not found on PATH\n")
    sys.exit(127)


def binary_env() -> dict:
    """Env dict to spawn ``claude`` with.

    Drops ``ANTHROPIC_API_KEY`` so claude-code falls back to OAuth (which is
    what claude-swap manages). Leaves everything else alone.
    """
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
