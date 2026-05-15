"""swap — multi-account switcher with pluggable providers.

This package houses the provider-agnostic `swap.core` machinery plus per-provider
adapters under `swap.providers.*`. The original `codex_swap` package is preserved
as a thin compatibility shim that re-exports from here.
"""

__version__ = "0.2.0"
