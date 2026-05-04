#!/usr/bin/env bash
# Local dev install via uv tool — no venv juggling.
# Re-run after edits to refresh the installed entry points.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if command -v uv >/dev/null 2>&1; then
  uv tool install --reinstall --from "$ROOT" cxswap
elif command -v pipx >/dev/null 2>&1; then
  pipx install --force "$ROOT"
else
  echo "Need either uv or pipx. Install one:" >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "  brew install pipx" >&2
  exit 1
fi

echo
echo "Installed. Verify with:"
echo "  cxswap --version"
echo "  cx --help"
