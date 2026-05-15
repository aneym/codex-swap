"""Atomic JSON read/write helpers used everywhere.

Lifted from the original codex_swap.auth module so providers and the core can
share it without circular imports.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def atomic_write_json(path: Path, data: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.chmod(tmp, mode)
    tmp.replace(path)
