# Install codex-swap

`codex-swap` installs two commands:

- `codex-swap` for account setup and diagnostics
- `cx` for daily use; it picks the best slot, then execs `codex`

## Recommended

```bash
curl -fsSL https://github.com/aneym/codex-swap/releases/latest/download/install.sh | bash
```

The installer uses `uv` when available, otherwise `pipx`, otherwise a private Python venv under `~/.local/share/codex-swap/venv`. It tries PyPI first, then the latest GitHub release wheel, then GitHub `main` as a last-resort fallback.

## Stable Package

Install directly from PyPI with your preferred isolated Python tool manager:

```bash
uv tool install codex-swap
# or
pipx install codex-swap
```

## GitHub Release

Use this when PyPI is unavailable but you want the latest stable release without requiring Git:

```bash
uv tool install --force https://github.com/aneym/codex-swap/releases/download/v0.1.2/codex_swap-0.1.2-py3-none-any.whl
# or
pipx install --force https://github.com/aneym/codex-swap/releases/download/v0.1.2/codex_swap-0.1.2-py3-none-any.whl
```

The installer can discover the latest release automatically:

```bash
curl -fsSL https://github.com/aneym/codex-swap/releases/latest/download/install.sh | bash -s -- --source release
```

The installer verifies the GitHub release wheel against the published checksums before installing it. Release checksums are published beside the artifacts:

```bash
curl -fsSL https://github.com/aneym/codex-swap/releases/latest/download/SHA256SUMS
```

## GitHub Main

Use this when you want the latest unreleased build:

```bash
uv tool install --force git+https://github.com/aneym/codex-swap
# or
pipx install --force git+https://github.com/aneym/codex-swap
```

## Shell Helpers

To add `cxslot`, `cxaccounts`, `cxstatus`, `cxverify`, and related helpers:

```bash
curl -fsSL https://github.com/aneym/codex-swap/releases/latest/download/install.sh | bash -s -- --shell-helpers
```

## Verify

```bash
codex-swap --version
codex-swap add
codex-swap onboard 2
codex-swap verify
```

`verify` should report `ok` or `rate_limited` for each slot. `broken` means the refresh token needs `codex-swap reconnect`; `error` means the local Codex install/model/config needs attention before auth can be judged.

Maintainers can smoke-test every installer backend with:

```bash
bash scripts/smoke-install.sh --source release
```

## Upgrade

```bash
uv tool install --upgrade codex-swap
# or, to use the release installer fallback chain:
curl -fsSL https://github.com/aneym/codex-swap/releases/latest/download/install.sh | bash
```

## Uninstall

```bash
codex-swap purge --yes
uv tool uninstall codex-swap
```

Run `purge` before uninstall if you want to remove local slot snapshots. If you installed through the fallback venv path instead of `uv` or `pipx`, remove the venv and shims:

```bash
rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/codex-swap/venv"
rm -f ~/.local/bin/codex-swap ~/.local/bin/cx
```

If you already uninstalled, remove `~/.codex-swap/` manually.
