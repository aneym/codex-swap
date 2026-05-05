# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

- Add `import-profile` for saving existing `~/.codex-profiles/*/auth.json` snapshots, including API-key auth profiles identified by non-secret fingerprints.
- Pick the newest detected Codex binary on `PATH` so stale installs do not shadow newer ones.
- Harden `verify` so timeout output is decoded safely, non-auth probe failures are not mislabeled as broken refresh tokens, and probes use an explicit lightweight model/prompt.
- Honor both `CXSWAP_*` and `CODEX_SWAP_*` launcher environment variables.

## 0.1.0 — initial release

- Per-slot snapshots of `~/.codex/auth.json` (`add`, `remove`, `list`, `status`).
- `cx` smart-launcher auto-picks the lowest-usage slot before exec'ing `codex`.
- Usage scanner reads rollouts under `~/.codex/sessions/**/*.jsonl` and correlates conversation IDs to account IDs via `~/.codex/logs_2.sqlite`.
- `verify` runs a real `codex exec` per slot and reports `ok` / `rate_limited` / `broken`.
- `reconnect` walks the user through fresh OAuth logins for every broken slot.
- `onboard <N>` for first-time multi-account setup.
- Onboarding and reauth flows never call `codex logout` — they clear `~/.codex/auth.json` locally to avoid revoking the refresh token server-side.
- Real-codex resolver bypasses the Superset CLI wrapper on macOS.
