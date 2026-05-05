#!/usr/bin/env bash
# Exercise production install routes in isolated temp homes.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLER="${CODEX_SWAP_INSTALLER:-$ROOT/scripts/install.sh}"
SOURCE="${CODEX_SWAP_SMOKE_SOURCE:-release}"
MODE="all"

usage() {
  cat <<'USAGE'
Smoke-test codex-swap installer routes.

Usage:
  scripts/smoke-install.sh [options]

Options:
  --source auto|pypi|release|git   Installer source to test. Default: release.
  --mode all|uv|pipx|venv          Installer backend to force. Default: all.
  --installer <path-or-url>         Installer script to run. Default: scripts/install.sh.
  -h, --help                       Show this help.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --source)
      SOURCE="${2:-}"
      shift 2
      ;;
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --installer)
      INSTALLER="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$SOURCE" in
  auto|pypi|release|git) ;;
  *)
    echo "--source must be auto, pypi, release, or git." >&2
    exit 2
    ;;
esac

case "$MODE" in
  all|uv|pipx|venv) ;;
  *)
    echo "--mode must be all, uv, pipx, or venv." >&2
    exit 2
    ;;
esac

run_installer() {
  if [[ "$INSTALLER" == http://* || "$INSTALLER" == https://* ]]; then
    curl -LfsS "$INSTALLER" | bash -s -- --source "$SOURCE" --no-path-check
  else
    bash "$INSTALLER" --source "$SOURCE" --no-path-check
  fi
}

verify_bin_dir() {
  local bin_dir="$1"
  "$bin_dir/codex-swap" --version
  "$bin_dir/codex-swap" --help >/dev/null
  test -x "$bin_dir/cx"
}

run_uv_smoke() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "Skipping uv smoke: uv is not on PATH." >&2
    return 0
  fi

  local dir="$TMP_ROOT/uv"
  mkdir -p "$dir"
  echo "==> installer smoke: uv"
  UV_TOOL_DIR="$dir/tools" \
    UV_TOOL_BIN_DIR="$dir/bin" \
    run_installer
  verify_bin_dir "$dir/bin"
}

run_pipx_smoke() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Skipping pipx smoke: python3 is not on PATH." >&2
    return 0
  fi

  local dir="$TMP_ROOT/pipx"
  mkdir -p "$dir/bin"
  python3 -m venv "$dir/runner"
  "$dir/runner/bin/python" -m pip install --upgrade pip >/dev/null
  "$dir/runner/bin/python" -m pip install pipx >/dev/null
  ln -sf "$dir/runner/bin/pipx" "$dir/bin/pipx"

  echo "==> installer smoke: pipx"
  PIPX_HOME="$dir/home" \
    PIPX_BIN_DIR="$dir/apps" \
    PATH="$dir/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    run_installer
  verify_bin_dir "$dir/apps"
}

run_venv_smoke() {
  local python_bin
  python_bin="$(command -v python3 || true)"
  if [ -z "$python_bin" ]; then
    echo "Skipping venv smoke: python3 is not on PATH." >&2
    return 0
  fi

  local dir="$TMP_ROOT/venv"
  mkdir -p "$dir/bin"
  ln -sf "$python_bin" "$dir/bin/python3"

  echo "==> installer smoke: venv"
  CODEX_SWAP_VENV_DIR="$dir/app-venv" \
    CODEX_SWAP_BIN_DIR="$dir/apps" \
    PATH="$dir/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    run_installer
  verify_bin_dir "$dir/apps"
}

TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

case "$MODE" in
  all)
    run_uv_smoke
    run_pipx_smoke
    run_venv_smoke
    ;;
  uv)
    run_uv_smoke
    ;;
  pipx)
    run_pipx_smoke
    ;;
  venv)
    run_venv_smoke
    ;;
esac

echo "==> installer smoke passed"
