"""Compat shim — re-export from `swap.providers.codex.binary`."""

# Tests patch `codex.subprocess.run`; the original module imported subprocess at
# top-level. Re-import it here so that pattern still works.
from swap.providers.codex import binary as _binary  # noqa: E402
from swap.providers.codex.binary import (
    SKIP_DIRS,
    VERSION_RE,
    _codex_candidates,
    _codex_version,
)
from swap.providers.codex.binary import (
    binary_env as codex_env,
)
from swap.providers.codex.binary import (
    find_binary as find_real_codex,
)

subprocess = _binary.subprocess

__all__ = [
    "SKIP_DIRS",
    "VERSION_RE",
    "_codex_candidates",
    "_codex_version",
    "codex_env",
    "find_real_codex",
    "subprocess",
]
