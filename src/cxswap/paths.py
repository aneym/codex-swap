"""Well-known filesystem paths for cxswap and Codex."""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()

# Codex CLI's home (overridable)
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or HOME / ".codex")
AUTH_PATH = CODEX_HOME / "auth.json"
SESSIONS_DIRS = [CODEX_HOME / "sessions", CODEX_HOME / "archived_sessions"]
LOGS_DB = CODEX_HOME / "logs_2.sqlite"

# cxswap's own state — overridable for testing
SWAP_ROOT = Path(os.environ.get("CXSWAP_ROOT") or HOME / ".codex-swap")
ACCOUNTS_DIR = SWAP_ROOT / "accounts"
SEQUENCE_PATH = SWAP_ROOT / "sequence.json"
USAGE_CACHE = SWAP_ROOT / "cache" / "usage.json"
STATE_PATH = SWAP_ROOT / "state.json"

USAGE_CACHE_TTL_SECONDS = 60
