#!/usr/bin/env bash
# Production installer for codex-swap.
#
# Default behavior:
#   - use uv when available, otherwise pipx, otherwise a private Python venv
#   - try PyPI first, then the latest GitHub release wheel, then GitHub main as last resort
#   - do not mutate shell rc files unless --shell-helpers is passed

set -euo pipefail

PACKAGE="codex-swap"
REPO_URL="https://github.com/aneym/codex-swap"
GIT_MAIN_SPEC="git+${REPO_URL}"
SOURCE="${CODEX_SWAP_INSTALL_SOURCE:-auto}"
DRY_RUN=0
CHECK_PATH=1
SHELL_HELPERS=0

usage() {
  cat <<'USAGE'
Install codex-swap.

Usage:
  scripts/install.sh [options]

Options:
  --source auto|pypi|release|git   Install source. Default: auto.
  --shell-helpers          Append cx helper functions to ~/.zshrc or ~/.bashrc.
  --no-path-check          Skip ~/.local/bin PATH warning.
  --dry-run                Print the chosen install command without running it.
  -h, --help               Show this help.

Examples:
  curl -fsSL https://github.com/aneym/codex-swap/releases/latest/download/install.sh | bash
  curl -fsSL https://github.com/aneym/codex-swap/releases/latest/download/install.sh | bash -s -- --source release
  scripts/install.sh --shell-helpers
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --source)
      SOURCE="${2:-}"
      shift 2
      ;;
    --shell-helpers)
      SHELL_HELPERS=1
      shift
      ;;
    --no-path-check)
      CHECK_PATH=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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

run_cmd() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

installer_name() {
  if command -v uv >/dev/null 2>&1; then
    echo "uv"
  elif command -v pipx >/dev/null 2>&1; then
    echo "pipx"
  elif command -v python3 >/dev/null 2>&1; then
    echo "venv"
  else
    echo "Need uv, pipx, or python3 to install codex-swap." >&2
    echo "Install uv:   curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    echo "Install pipx: brew install pipx" >&2
    echo "Install Python 3: https://www.python.org/downloads/" >&2
    exit 1
  fi
}

venv_dir() {
  if [ -n "${CODEX_SWAP_VENV_DIR:-}" ]; then
    echo "$CODEX_SWAP_VENV_DIR"
  else
    echo "${XDG_DATA_HOME:-$HOME/.local/share}/codex-swap/venv"
  fi
}

install_spec() {
  local installer="$1"
  local spec="$2"
  if [ "$installer" = "uv" ]; then
    run_cmd uv tool install --force "$spec"
  elif [ "$installer" = "pipx" ]; then
    run_cmd pipx install --force "$spec"
  else
    local venv
    local bin_dir
    venv="$(venv_dir)"
    bin_dir="$(installer_bin_dir "$installer")"
    run_cmd python3 -m venv "$venv"
    run_cmd "$venv/bin/python" -m pip install --upgrade "$spec"
    run_cmd mkdir -p "$bin_dir"
    run_cmd ln -sf "$venv/bin/codex-swap" "$bin_dir/codex-swap"
    run_cmd ln -sf "$venv/bin/cx" "$bin_dir/cx"
  fi
}

installer_bin_dir() {
  local installer="$1"
  if [ "$installer" = "uv" ]; then
    echo "${UV_TOOL_BIN_DIR:-$HOME/.local/bin}"
  elif [ "$installer" = "pipx" ]; then
    echo "${PIPX_BIN_DIR:-$HOME/.local/bin}"
  else
    echo "${CODEX_SWAP_BIN_DIR:-$HOME/.local/bin}"
  fi
}

latest_release_tag() {
  if [ -n "${CODEX_SWAP_INSTALL_RELEASE_TAG:-}" ]; then
    echo "$CODEX_SWAP_INSTALL_RELEASE_TAG"
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi
  curl -fsSL "https://api.github.com/repos/aneym/codex-swap/releases/latest" |
    sed -nE 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' |
    head -1
}

release_spec() {
  local tag
  tag="$(latest_release_tag || true)"
  if [ -z "$tag" ]; then
    return 1
  fi
  echo "${REPO_URL}/releases/download/${tag}/codex_swap-${tag#v}-py3-none-any.whl"
}

install_package() {
  local installer="$1"
  local spec
  case "$SOURCE" in
    pypi)
      install_spec "$installer" "$PACKAGE"
      ;;
    release)
      spec="$(release_spec)" || {
        echo "Could not discover latest GitHub release." >&2
        exit 1
      }
      install_spec "$installer" "$spec"
      ;;
    git)
      install_spec "$installer" "$GIT_MAIN_SPEC"
      ;;
    auto)
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "# auto: try PyPI, then latest GitHub release wheel, then GitHub main"
        install_spec "$installer" "$PACKAGE"
        spec="$(release_spec || true)"
        if [ -n "$spec" ]; then
          install_spec "$installer" "$spec"
        else
          echo "# latest GitHub release could not be discovered"
        fi
        install_spec "$installer" "$GIT_MAIN_SPEC"
      elif ! install_spec "$installer" "$PACKAGE"; then
        echo "PyPI install failed; falling back to latest GitHub release." >&2
        spec="$(release_spec || true)"
        if [ -n "$spec" ] && install_spec "$installer" "$spec"; then
          return 0
        fi
        echo "GitHub release install failed; falling back to GitHub main." >&2
        install_spec "$installer" "$GIT_MAIN_SPEC"
      fi
      ;;
  esac
}

shell_rc() {
  case "${SHELL:-}" in
    */zsh) echo "$HOME/.zshrc" ;;
    */bash) echo "$HOME/.bashrc" ;;
    *) echo "$HOME/.profile" ;;
  esac
}

append_shell_helpers() {
  local rc_file="$1"
  mkdir -p "$(dirname "$rc_file")"
  touch "$rc_file"
  if grep -q '>>> codex-swap >>>' "$rc_file"; then
    echo "Shell helpers already present in $rc_file"
    return 0
  fi
  cat >> "$rc_file" <<'EOF'

# >>> codex-swap >>>
export PATH="$HOME/.local/bin:$PATH"
cxraw()       { CODEX_SWAP_SKIP_AUTO=1 command cx "$@"; }
cxslot()      { CODEX_SWAP_SLOT="$1" command cx "${@:2}"; }
cxaccounts()  { command codex-swap list "$@"; }
cxstatus()    { command codex-swap status "$@"; }
cxverify()    { command codex-swap verify "$@"; }
cxreconnect() { command codex-swap reconnect "$@"; }
# <<< codex-swap <<<
EOF
  echo "Added codex-swap shell helpers to $rc_file"
}

warn_if_codex_missing_or_old() {
  if ! command -v codex >/dev/null 2>&1; then
    echo "Warning: codex is not on PATH. Install OpenAI Codex CLI before running cx." >&2
    return 0
  fi
  local version
  version="$(codex --version 2>/dev/null | sed -nE 's/.* ([0-9]+)\.([0-9]+)\.([0-9]+).*/\1 \2 \3/p' | head -1)"
  if [ -z "$version" ]; then
    echo "Warning: could not parse codex version from: $(codex --version 2>/dev/null)" >&2
    return 0
  fi
  set -- $version
  if [ "$1" -eq 0 ] && [ "$2" -lt 122 ]; then
    echo "Warning: codex $(codex --version) is older than recommended 0.122+." >&2
  fi
}

print_installed_version() {
  local bin_dir="$1"
  if command -v codex-swap >/dev/null 2>&1; then
    codex-swap --version
  elif [ -x "$bin_dir/codex-swap" ]; then
    "$bin_dir/codex-swap" --version
  else
    echo "Installed, but codex-swap is not on PATH yet." >&2
  fi
}

main() {
  local installer
  installer="$(installer_name)"
  local bin_dir
  bin_dir="$(installer_bin_dir "$installer")"
  echo "Installing codex-swap with $installer (source: $SOURCE)"
  install_package "$installer"

  if [ "$CHECK_PATH" -eq 1 ]; then
    case ":$PATH:" in
      *":$bin_dir:"*) ;;
      *)
        echo "Warning: $bin_dir is not on PATH. Add:" >&2
        echo "  export PATH=\"$bin_dir:\$PATH\"" >&2
        ;;
    esac
  fi

  if [ "$SHELL_HELPERS" -eq 1 ]; then
    append_shell_helpers "$(shell_rc)"
  fi

  if [ "$DRY_RUN" -eq 0 ]; then
    print_installed_version "$bin_dir"
    warn_if_codex_missing_or_old
    echo "Installed. Next: codex-swap add && codex-swap onboard 2 && codex-swap verify"
  fi
}

main
