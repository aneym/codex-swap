# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

- Prefer GitHub release wheel artifacts over `git+...@tag` installs when PyPI is unavailable, keeping bootstrap installs faster and independent of Git.
- Publish `install.sh` as a GitHub Release asset so the recommended install command can use the stable latest-release URL instead of raw branch content.
- Update GitHub workflows to `actions/checkout@v6` so main/release automation avoids the Node 20 deprecation path.
- Publish `SHA256SUMS` for GitHub release artifacts and document the checksum route.
- Keep README install/uninstall snippets aligned with the production installer and purge-before-uninstall flow.
- Add a private Python venv fallback so the release installer works even when `uv` and `pipx` are not installed.
- Add a reusable installer smoke test and CI job covering `uv`, `pipx`, and private-venv install backends.
- Verify GitHub release wheel checksums before installing release fallback artifacts.
- Keep README and install docs aligned with live PyPI publishing and GitHub release fallbacks.
- Spell out the PyPI pending-publisher setup fields required for first publish.

## 0.1.1 — 2026-05-05

- Add `import-profile` for saving existing `~/.codex-profiles/*/auth.json` snapshots, including API-key auth profiles identified by non-secret fingerprints.
- Pick the newest detected Codex binary on `PATH` so stale installs do not shadow newer ones.
- Harden `verify` so timeout output is decoded safely, non-auth probe failures are not mislabeled as broken refresh tokens, and probes use an explicit lightweight model/prompt.
- Honor both `CXSWAP_*` and `CODEX_SWAP_*` launcher environment variables.
- Add a production installer with PyPI/GitHub install routes, shell helpers, dry-run mode, and Codex version warnings.
- Add a reusable release packaging gate that lint/tests/builds/checks metadata and smoke-installs the wheel.
- Run package install checks in CI, run the same gate before PyPI publishing, create GitHub release artifacts from tags, and auto-tag new package versions after successful `main` CI.

## 0.1.0 — initial release

- Per-slot snapshots of `~/.codex/auth.json` (`add`, `remove`, `list`, `status`).
- `cx` smart-launcher auto-picks the lowest-usage slot before exec'ing `codex`.
- Usage scanner reads rollouts under `~/.codex/sessions/**/*.jsonl` and correlates conversation IDs to account IDs via `~/.codex/logs_2.sqlite`.
- `verify` runs a real `codex exec` per slot and reports `ok` / `rate_limited` / `broken`.
- `reconnect` walks the user through fresh OAuth logins for every broken slot.
- `onboard <N>` for first-time multi-account setup.
- Onboarding and reauth flows never call `codex logout` — they clear `~/.codex/auth.json` locally to avoid revoking the refresh token server-side.
- Real-codex resolver bypasses the Superset CLI wrapper on macOS.
