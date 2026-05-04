# Changelog

## 0.1.0 — initial release

- Per-slot snapshots of `~/.codex/auth.json` (`add`, `remove`, `list`, `status`).
- `cx` smart-launcher auto-picks the lowest-usage slot before exec'ing `codex`.
- Usage scanner reads rollouts under `~/.codex/sessions/**/*.jsonl` and correlates conversation IDs to account IDs via `~/.codex/logs_2.sqlite`.
- `verify` runs a real `codex exec` per slot and reports `ok` / `rate_limited` / `broken`.
- `reconnect` walks the user through fresh OAuth logins for every broken slot.
- `onboard <N>` for first-time multi-account setup.
- Onboarding and reauth flows never call `codex logout` — they clear `~/.codex/auth.json` locally to avoid revoking the refresh token server-side.
- Real-codex resolver bypasses the Superset CLI wrapper on macOS.
