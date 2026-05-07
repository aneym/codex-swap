# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

- `codex-swap usage` is now a multi-line, color-coded view per slot. Each slot prints a header (`slot N · plan · source`) plus a row per window with the effective percent (green/yellow/red by severity) and the explicit reset time (e.g. `resets Thu 8:35pm, in 4h`). Past resets render as `already reset` so an exhausted slot whose window has cleared is obvious. Exhausted slots get a `LIMIT REACHED — run codex-swap seed` callout in the header. ANSI is auto-suppressed when stdout is not a TTY (and via `NO_COLOR`); set `CODEX_SWAP_FORCE_COLOR=1` to force.

## 0.1.4 — 2026-05-07

- Detect rate-limit-reached rollouts so a tapped-out slot is no longer mistaken for "no new data". Codex writes `primary: null, secondary: null, credits.has_credits: false` once an account hits its weekly cap; the scanner used to drop that snapshot and leave the cache frozen on the last pre-limit reading (e.g. `7d=47%`), which made the picker keep choosing an exhausted slot.
- Persist exhaustion as an explicit `exhausted: true` flag on the slot record. Merge preserves prior `primary`/`secondary` window timing so the display can still report when the cap is expected to clear, and a fresh successful rollout fully replaces the exhaustion record.
- The picker drops exhausted slots into the worst bucket (synthetic `100%/100%`) so they rank below an unmeasured slot — same precedence as a known-near-cap slot.
- `codex-swap usage` and `codex-swap list` now surface "limit reached" inline so a tapped-out slot is obvious at a glance.
- Fix the `test_main_push_ci_auto_tags_and_publishes_release` regression that lingered after #7 split SHA256SUMS into a `cd dist` + append step.

## 0.1.3 — 2026-05-05

- Make the per-slot usage store durable: rollout scans now merge new findings into the persisted cache instead of overwriting it, so a slot's record is kept until something fresher replaces it.
- Apply `resets_at`-based decay to `used_percent` so the picker, `list`, and `usage` reflect window resets without needing a fresh probe.
- Fix the picker so a known-near-cap slot (≥ 80% on either window) ranks below an unmeasured slot — auto-rotation no longer gets stuck on a 90% slot just because the alternatives have no rollout history.
- Add `codex-swap seed [targets...]` to populate usage data in parallel via per-probe isolated `CODEX_HOME`s; defaults to slots with no record, `--all` re-seeds everything, `--concurrency` and `--timeout` configurable.
- Auto-seed at the end of `codex-swap onboard` so freshly onboarded accounts have usage data immediately.
- `codex-swap remove` now drops the slot's persisted usage record so re-adding at the same slot number cannot inherit prior data.
- `codex-swap list` and `codex-swap usage` render decayed effective percents and tag each row with its source (`rollout` or `probe`).
- The launcher no longer auto-probes on every `cx` launch; it does a cheap rollout-scan + merge, then prints a one-line tip pointing at `codex-swap seed` if any slot is still unmeasured.

## 0.1.2 — 2026-05-05

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
