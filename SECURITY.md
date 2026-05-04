# Security

## What codex-swap stores

Per-slot snapshots of `~/.codex/auth.json` under `~/.codex-swap/accounts/<N>/auth.json`. Each snapshot is `chmod 600` (owner read/write only) and contains:

- An OAuth access token (short-lived, used as a bearer for chatgpt.com API calls)
- An OAuth refresh token (single-use, rotates on every refresh)
- An ID token (JWT — used to extract email and account_id for display)
- The associated `account_id`

These are the same fields Codex itself stores in `~/.codex/auth.json`. We are not creating new credentials — only snapshotting existing ones into per-account slots.

`~/.codex-swap/sequence.json` is `chmod 600` and stores email + account_id metadata for each slot. No secrets.

## What it does NOT store

- Credit card / billing information
- Passwords
- Any data outside what Codex itself already writes to `~/.codex/`

## Network traffic

`codex-swap` makes no network requests of its own. The `verify` and `reauth` subcommands invoke the `codex` binary, which talks to OpenAI's servers exactly as it would when invoked directly.

## Token revocation safety

The single most important rule: **`codex-swap` never calls `codex logout`.** That command revokes the refresh token at OpenAI's OAuth provider, which would silently invalidate every snapshot taken before it ran. All onboarding and re-auth flows clear `~/.codex/auth.json` locally and then run `codex login` for a fresh OAuth grant.

## Reporting a vulnerability

Open an issue at https://github.com/aneym/codex-swap/issues. For sensitive disclosures, use GitHub's private security advisory feature on the same repo.
