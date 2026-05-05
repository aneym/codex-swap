#!/usr/bin/env bash
# Production packaging gate: lint, test, build, metadata-check, and wheel-install smoke.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "Need uv to run release checks: https://docs.astral.sh/uv/" >&2
  exit 1
fi

echo "==> Python tests"
uv run --extra dev pytest -q

echo "==> Ruff"
uv run --extra dev ruff check .

echo "==> Shell syntax"
bash -n scripts/install.sh scripts/release.sh scripts/check-release.sh scripts/smoke-install.sh

echo "==> Build sdist + wheel"
uv build --clear

echo "==> Check package metadata"
uvx --from twine twine check dist/*

echo "==> Smoke install wheel"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
python3 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/python" -m pip install --upgrade pip >/dev/null
wheel="$(find dist -maxdepth 1 -name 'codex_swap-*.whl' | sort | tail -1)"
if [ -z "$wheel" ]; then
  echo "No codex_swap wheel found in dist/." >&2
  exit 1
fi
"$tmp_dir/venv/bin/python" -m pip install "$wheel" >/dev/null
"$tmp_dir/venv/bin/codex-swap" --version
"$tmp_dir/venv/bin/codex-swap" --help >/dev/null
"$tmp_dir/venv/bin/python" -m codex_swap --version

echo "==> Release checks passed"
