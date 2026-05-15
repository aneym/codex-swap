"""Minimal ANSI styling with TTY detection — no third-party deps.

Lifted verbatim from the original `codex_swap.cli` module so output is byte-identical.
"""

from __future__ import annotations

import os
import sys


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CODEX_SWAP_FORCE_COLOR") or os.environ.get("SWAP_FORCE_COLOR"):
        return True
    return bool(sys.stdout.isatty())


class Style:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled or not text:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, t: str) -> str:
        return self._wrap("1", t)

    def dim(self, t: str) -> str:
        return self._wrap("2", t)

    def green(self, t: str) -> str:
        return self._wrap("32", t)

    def yellow(self, t: str) -> str:
        return self._wrap("33", t)

    def red(self, t: str) -> str:
        return self._wrap("31", t)

    def cyan(self, t: str) -> str:
        return self._wrap("36", t)

    def bold_red(self, t: str) -> str:
        return self._wrap("1;31", t)


def color_pct(style: Style, pct: float | None, text: str) -> str:
    """Severity-color a percent string. None and 0 render dim."""
    if pct is None:
        return style.dim(text)
    if pct <= 0:
        return style.dim(text)
    if pct < 50:
        return style.green(text)
    if pct < 80:
        return style.yellow(text)
    return style.red(text)
