# Install codex-swap

`codex-swap` installs two commands:

- `codex-swap` for account setup and diagnostics
- `cx` for daily use; it picks the best slot, then execs `codex`

## Recommended

```bash
curl -fsSL https://raw.githubusercontent.com/aneym/codex-swap/main/scripts/install.sh | bash
```

The installer uses `uv` when available, otherwise `pipx`. It tries PyPI first and falls back to GitHub while the first PyPI release is bootstrapping.

## Stable Package

After the PyPI release is available:

```bash
uv tool install codex-swap
# or
pipx install codex-swap
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
curl -fsSL https://raw.githubusercontent.com/aneym/codex-swap/main/scripts/install.sh | bash -s -- --shell-helpers
```

## Verify

```bash
codex-swap --version
codex-swap add
codex-swap onboard 2
codex-swap verify
```

`verify` should report `ok` or `rate_limited` for each slot. `broken` means the refresh token needs `codex-swap reconnect`; `error` means the local Codex install/model/config needs attention before auth can be judged.

## Upgrade

```bash
uv tool install --upgrade codex-swap
# or, before PyPI is live:
uv tool install --force git+https://github.com/aneym/codex-swap
```

## Uninstall

```bash
codex-swap purge --yes
uv tool uninstall codex-swap
```

Run `purge` before uninstall if you want to remove local slot snapshots. If you already uninstalled, remove `~/.codex-swap/` manually.
