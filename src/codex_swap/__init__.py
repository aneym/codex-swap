"""codex-swap — multi-account switcher for the Codex CLI.

This package is a compatibility shim. The implementation lives in
`swap.core` (generic) and `swap.providers.codex` (Codex adapter). Any callsite
that imports `codex_swap.*` keeps working; new code should import from `swap.*`.
"""

from swap import __version__

__all__ = ["__version__"]
