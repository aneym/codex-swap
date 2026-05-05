"""Locate the real Codex CLI binary, bypassing wrappers like Superset."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = ("/.superset/", "/.superset-")
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def find_real_codex() -> str:
    """Return the newest usable 'codex' binary on PATH.

    Several local setups have multiple Codex installs. Prefer the newest
    executable over PATH order so a stale Homebrew install does not shadow a
    newer bun/npm install.
    """
    explicit = os.environ.get("CODEX_SWAP_REAL_CODEX")
    if explicit and Path(explicit).exists():
        return explicit

    candidates = _codex_candidates()
    versioned = []
    for candidate in candidates:
        version = _codex_version(candidate)
        if version:
            versioned.append((version, candidate))
    if versioned:
        return str(max(versioned, key=lambda item: item[0])[1])
    if candidates:
        return str(candidates[0])

    fallback = shutil.which("codex")
    if fallback:
        return fallback
    sys.stderr.write("codex-swap: codex binary not found on PATH\n")
    sys.exit(127)


def _codex_candidates() -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for directory in os.environ.get("PATH", "").split(":"):
        if not directory or any(s in directory for s in SKIP_DIRS):
            continue
        candidate = Path(directory) / "codex"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            key = str(candidate.resolve())
            if key not in seen:
                seen.add(key)
                found.append(candidate)
    return found


def _codex_version(path: Path) -> tuple[int, int, int] | None:
    try:
        proc = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    match = VERSION_RE.search(text)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def codex_env() -> dict:
    """Env without OPENAI_API_KEY so Codex prefers ChatGPT auth from auth.json."""
    return {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
