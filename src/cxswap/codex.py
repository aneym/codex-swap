"""Locate the real Codex CLI binary, bypassing wrappers like Superset."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SKIP_DIRS = ("/.superset/", "/.superset-")


def find_real_codex() -> str:
    """Return the first 'codex' on PATH that isn't a Superset wrapper.

    Codex inside Superset terminals is usually a thin bash wrapper at
    ~/.superset/bin/codex that forwards to the real binary on PATH. We
    skip those wrapper dirs so cxswap's own swap logic isn't double-wrapped.
    """
    explicit = os.environ.get("CXSWAP_REAL_CODEX")
    if explicit and Path(explicit).exists():
        return explicit
    for directory in os.environ.get("PATH", "").split(":"):
        if not directory or any(s in directory for s in SKIP_DIRS):
            continue
        candidate = Path(directory) / "codex"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    fallback = shutil.which("codex")
    if fallback:
        return fallback
    sys.stderr.write("cxswap: codex binary not found on PATH\n")
    sys.exit(127)


def codex_env() -> dict:
    """Env without OPENAI_API_KEY so Codex prefers ChatGPT auth from auth.json."""
    return {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
