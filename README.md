# codex-swap

[![CI](https://github.com/aneym/codex-swap/actions/workflows/ci.yml/badge.svg)](https://github.com/aneym/codex-swap/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/codex-swap.svg)](https://pypi.org/project/codex-swap/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Pick the ChatGPT Pro account with the lowest usage every time you launch [Codex CLI](https://github.com/openai/codex). One command, no thinking.

```
$ cx
cx: using slot 2 (alex@example.com, 5h 4%, 7d 12%)
╭─── OpenAI Codex (v0.128.0) ───╮
│ model: gpt-5.5  fast          │
╰────────────────────────────────╯
```

If you have multiple Codex Pro accounts and you keep hitting the 5-hour cap on whichever one you happened to be logged into, this is for you. It's the Codex equivalent of [`cswap`](https://pypi.org/project/claude-swap/) for Claude Code.

## What it does

- Saves a snapshot of each account's `~/.codex/auth.json` into its own slot.
- Before each `cx` launch, scans your local Codex rollouts to learn each account's primary (5-hour) and secondary (7-day) usage percent.
- Swaps `auth.json` to the slot with the lowest usage, then `exec`s `codex`.
- Snapshots back any refreshed tokens so the rotation chain never breaks.

## Install

Recommended — installs two commands (`codex-swap` and `cx`) into `~/.local/bin`, using PyPI when available and falling back to the latest GitHub release:

```bash
curl -fsSL https://raw.githubusercontent.com/aneym/codex-swap/main/scripts/install.sh | bash
```

Or pick a package manager directly:

```bash
# Recommended (faster, isolated):
uv tool install codex-swap

# or:
pipx install codex-swap
```

Until codex-swap is on PyPI, install the latest GitHub release:

```bash
uv tool install git+https://github.com/aneym/codex-swap@v0.1.1
# or:
pipx install git+https://github.com/aneym/codex-swap@v0.1.1
```

Make sure `~/.local/bin` is on your `PATH`. If not:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
exec zsh
```

Verify:

```bash
codex-swap --version
cx --help
```

More install, upgrade, and shell-helper options live in [`docs/INSTALL.md`](docs/INSTALL.md).

## First-time setup

You need to be logged into Codex with one of your ChatGPT Pro accounts already (`codex login`). Then:

```bash
# 1. Save the account you're already logged into as slot 1.
codex-swap add

# 2. Add the rest of your accounts. codex-swap will pop a browser per account.
codex-swap onboard 2

# 3. Confirm everything works.
codex-swap verify
```

Output of `verify` should be all `ok` (or `rate_limited` if a window is currently capped — that's fine, auth is still healthy). If a row says `error`, the probe failed for a local Codex/model/config reason rather than a dead refresh token.

If you already have Codex profile directories, import them instead of logging in again:

```bash
codex-swap import-profile personal
codex-swap import-profile work --label work
```

`import-profile` accepts a profile name under `~/.codex-profiles`, a profile directory, or an `auth.json` path. It supports both ChatGPT OAuth profiles and API-key profiles; API-key profiles do not expose 5-hour/7-day ChatGPT usage telemetry, so they show as unknown usage and are best pinned explicitly when needed.

## Daily use

Replace `codex` with `cx` in your workflow:

```bash
cx                # auto-pick lowest-usage slot, then run codex
cx exec "fix bug" # all codex args are forwarded
```

That's the whole interface.

## When something goes wrong

If a slot's refresh token dies (you ran `codex logout` somewhere, the token aged out, etc.), `cx` will still try to use it and codex will print "refresh token was already used" or similar. Fix everything in one shot:

```bash
codex-swap reconnect    # finds dead slots, walks you through fresh logins
```

If you want to fix one specific slot:

```bash
codex-swap reauth 1     # opens browser, log in to that slot's account
```

## All commands

| Command | What it does |
|---------|--------------|
| `cx` | Auto-pick lowest-usage slot and exec codex (this is what you'll use) |
| `codex-swap add` | Save the currently logged-in account as a new slot |
| `codex-swap import-profile <profile>` | Save an existing `~/.codex-profiles/<profile>/auth.json` or auth file as a slot |
| `codex-swap remove <slot>` | Remove a slot |
| `codex-swap list` | Show all slots with usage % |
| `codex-swap status` | Show which slot is active right now |
| `codex-swap switch [<slot>]` | Switch to a slot (no arg → rotate to next) |
| `codex-swap reauth <slot>` | Re-mint a slot via fresh `codex login` |
| `codex-swap reconnect` | Verify all slots, then reauth every broken one |
| `codex-swap onboard [N]` | Guided login for N accounts in a row |
| `codex-swap verify` | Test every slot with a real `codex exec` call |
| `codex-swap usage` | Refresh & print the per-slot usage cache |
| `codex-swap stash` | Snapshot live `auth.json` back into its slot |
| `codex-swap purge --yes` | Delete all codex-swap state |

`<slot>` accepts a slot number, an email, or an account_id.

### Pinning and bypass

```bash
CXSWAP_SLOT=2 cx       # force a specific slot for this run
CXSWAP_SKIP_AUTO=1 cx  # skip auto-pick (use whatever's currently in auth.json)
```

The explicit names `CODEX_SWAP_SLOT` and `CODEX_SWAP_SKIP_AUTO` work too.

## Optional shell aliases

If you like shorter names, add to your `~/.zshrc`:

```bash
cxraw()       { CXSWAP_SKIP_AUTO=1 cx "$@"; }
cxslot()      { CXSWAP_SLOT="$1" cx "${@:2}"; }
cxaccounts()  { codex-swap list "$@"; }
cxstatus()    { codex-swap status "$@"; }
cxverify()    { codex-swap verify "$@"; }
cxreauth()    { codex-swap reauth "$@"; }
cxreconnect() { codex-swap reconnect "$@"; }
```

Reload with `exec zsh`.

## How "lowest usage" is computed

After every Codex turn, the CLI persists a `token_count` event with `rate_limits.primary` (5-hour window) and `rate_limits.secondary` (7-day window) into `~/.codex/sessions/**/*.jsonl`. codex-swap correlates conversation IDs to account IDs via `~/.codex/logs_2.sqlite` (`user.account_id="..."` + `conversation.id=...` in the otel log bodies), then for each managed slot pulls the latest snapshot from a rollout owned by that slot. The picker sorts by `(5h%, 7d%, slot#)`.

A slot with no usage data sorts as if it were 101% — it'll be picked only after the others have logged usage.

## Critical: never run `codex logout`

`codex logout` calls a server-side revoke that **invalidates the refresh token** at the OAuth provider. Every other slot whose snapshot pre-dates that revoke is then permanently dead. codex-swap's onboarding and reauth flows use `rm ~/.codex/auth.json` instead — same effect locally, no server-side blast radius.

If a slot ever goes bad (you ran `codex logout` by hand, or the token aged out), `codex-swap reconnect` will detect and fix it.

## Refresh token rotation, briefly

ChatGPT issues single-use refresh tokens that rotate on every successful refresh. codex-swap snapshots the live `auth.json` back into its slot before every swap-out, so the slot's snapshot always carries the latest rotated token. You only get into trouble if you run `codex` twice on the same slot in parallel — both refresh independently, one of them ends up with a token the server has already burned.

**Safe:** sequential `cx` runs, even across many accounts.
**Unsafe:** two terminals running `cx` against the same slot at the same time.

## Files

```
~/.codex-swap/
├── accounts/<N>/auth.json   # per-slot snapshots (chmod 600)
├── sequence.json            # slot order + email/account_id metadata
├── state.json               # last switched slot + timestamp
└── cache/usage.json         # cached rate-limit snapshots
```

`~/.codex/auth.json` is the live file Codex reads. codex-swap only ever swaps that one file in and out.

## Caveats

- macOS only right now.
- Requires `codex` v0.122 or newer (the rollout schema with `rate_limits.primary/secondary` was added around that time). If multiple Codex installs exist on `PATH`, codex-swap chooses the newest detected binary.
- `OPENAI_API_KEY` in your environment will override `auth.json`. codex-swap unsets it when running `codex login` so the OAuth path wins; if you want `cx` to do the same for the launched session, wrap it: `alias cx='env -u OPENAI_API_KEY codex-swap launch'`.

## Uninstall

```bash
uv tool uninstall codex-swap        # or: pipx uninstall codex-swap
codex-swap purge --yes              # before uninstall, removes ~/.codex-swap
```

## Development

```bash
git clone https://github.com/aneym/codex-swap
cd codex-swap
bash scripts/install-dev.sh     # installs editable via uv tool
pytest -q                       # run the unit tests
ruff check .                    # lint
```

## Releasing

Maintainer flow:

```bash
# 1. Move bullet points into the [Unreleased] block of CHANGELOG.md
# 2. Cut the release:
scripts/release.sh 0.1.1
```

The script runs the full packaging gate, bumps `src/codex_swap/__init__.py`, promotes `[Unreleased]` into a versioned section, tags `v0.1.1`, and pushes. A successful `main` CI run also auto-creates a missing version tag, so release publication stays automated even when maintainers only push the release commit. The `publish.yml` workflow builds, checks, uploads to PyPI via Trusted Publishing, and creates a GitHub release with the changelog notes attached. No long-lived API tokens involved.

See [`docs/RELEASE.md`](docs/RELEASE.md) for the exact automation path.

### One-time PyPI Trusted Publisher setup

Before the first publish runs cleanly:

1. Reserve the package name on PyPI by uploading any 0.0.x build manually (or have a maintainer claim it).
2. On PyPI → *Manage project* → *Publishing* → add a GitHub publisher:
   - Owner: `aneym`
   - Repository: `codex-swap`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. On GitHub → repo *Settings* → *Environments* → create `pypi` (no secrets needed — the OIDC token handles auth).

After that, every `git push` of a `vX.Y.Z` tag publishes automatically.

## License

MIT
