"""Compat shim — re-export the original `codex_swap.paths` constants.

Resolves Codex paths at import time. New code should call
`swap.core.paths.provider_paths('codex')` instead.
"""

from __future__ import annotations

import os
from pathlib import Path

from swap.core.paths import provider_paths
from swap.providers.codex.auth import AUTH_PATH

HOME = Path.home()

CODEX_HOME = Path(os.environ.get("CODEX_HOME") or HOME / ".codex")
SESSIONS_DIRS = [CODEX_HOME / "sessions", CODEX_HOME / "archived_sessions"]
LOGS_DB = CODEX_HOME / "logs_2.sqlite"

_paths = provider_paths("codex")
SWAP_ROOT = _paths["root"]
ACCOUNTS_DIR = _paths["accounts_dir"]
SEQUENCE_PATH = _paths["sequence"]
USAGE_CACHE = _paths["usage_cache"]
STATE_PATH = _paths["state"]
POLICY_PATH = _paths["policy"]

USAGE_CACHE_TTL_SECONDS = 60

__all__ = [
    "ACCOUNTS_DIR",
    "AUTH_PATH",
    "CODEX_HOME",
    "HOME",
    "LOGS_DB",
    "POLICY_PATH",
    "SEQUENCE_PATH",
    "SESSIONS_DIRS",
    "STATE_PATH",
    "SWAP_ROOT",
    "USAGE_CACHE",
    "USAGE_CACHE_TTL_SECONDS",
]
