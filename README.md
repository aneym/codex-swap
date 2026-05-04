# cxswap

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

Pick one — both install two commands (`cxswap` and `cx`) into `~/.local/bin`:

```bash
# Recommended (faster, isolated):
uv tool install cxswap

# or:
pipx install cxswap
```

Until cxswap is on PyPI, install from this repo:

```bash
uv tool install git+https://github.com/alexneyman/cxswap
# or:
pipx install git+https://github.com/alexneyman/cxswap
```

Make sure `~/.local/bin` is on your `PATH`. If not:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
exec zsh
```

Verify:

```bash
cxswap --version
cx --help
```

## First-time setup

You need to be logged into Codex with one of your ChatGPT Pro accounts already (`codex login`). Then:

```bash
# 1. Save the account you're already logged into as slot 1.
cxswap add

# 2. Add the rest of your accounts. cxswap will pop a browser per account.
cxswap onboard 2

# 3. Confirm everything works.
cxswap verify
```

Output of `verify` should be all `ok` (or `rate_limited` if a window is currently capped — that's fine, auth is still healthy).

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
cxswap reconnect    # finds dead slots, walks you through fresh logins
```

If you want to fix one specific slot:

```bash
cxswap reauth 1     # opens browser, log in to that slot's account
```

## All commands

| Command | What it does |
|---------|--------------|
| `cx` | Auto-pick lowest-usage slot and exec codex (this is what you'll use) |
| `cxswap add` | Save the currently logged-in account as a new slot |
| `cxswap remove <slot>` | Remove a slot |
| `cxswap list` | Show all slots with usage % |
| `cxswap status` | Show which slot is active right now |
| `cxswap switch [<slot>]` | Switch to a slot (no arg → rotate to next) |
| `cxswap reauth <slot>` | Re-mint a slot via fresh `codex login` |
| `cxswap reconnect` | Verify all slots, then reauth every broken one |
| `cxswap onboard [N]` | Guided login for N accounts in a row |
| `cxswap verify` | Test every slot with a real `codex exec` call |
| `cxswap usage` | Refresh & print the per-slot usage cache |
| `cxswap stash` | Snapshot live `auth.json` back into its slot |
| `cxswap purge --yes` | Delete all cxswap state |

`<slot>` accepts a slot number, an email, or an account_id.

### Pinning and bypass

```bash
CXSWAP_SLOT=2 cx       # force a specific slot for this run
CXSWAP_SKIP_AUTO=1 cx  # skip auto-pick (use whatever's currently in auth.json)
```

## Optional shell aliases

If you like shorter names, add to your `~/.zshrc`:

```bash
cxraw()       { CXSWAP_SKIP_AUTO=1 cx "$@"; }
cxslot()      { CXSWAP_SLOT="$1" cx "${@:2}"; }
cxaccounts()  { cxswap list "$@"; }
cxstatus()    { cxswap status "$@"; }
cxverify()    { cxswap verify "$@"; }
cxreauth()    { cxswap reauth "$@"; }
cxreconnect() { cxswap reconnect "$@"; }
```

Reload with `exec zsh`.

## How "lowest usage" is computed

After every Codex turn, the CLI persists a `token_count` event with `rate_limits.primary` (5-hour window) and `rate_limits.secondary` (7-day window) into `~/.codex/sessions/**/*.jsonl`. cxswap correlates conversation IDs to account IDs via `~/.codex/logs_2.sqlite` (`user.account_id="..."` + `conversation.id=...` in the otel log bodies), then for each managed slot pulls the latest snapshot from a rollout owned by that slot. The picker sorts by `(5h%, 7d%, slot#)`.

A slot with no usage data sorts as if it were 101% — it'll be picked only after the others have logged usage.

## Critical: never run `codex logout`

`codex logout` calls a server-side revoke that **invalidates the refresh token** at the OAuth provider. Every other slot whose snapshot pre-dates that revoke is then permanently dead. cxswap's onboarding and reauth flows use `rm ~/.codex/auth.json` instead — same effect locally, no server-side blast radius.

If a slot ever goes bad (you ran `codex logout` by hand, or the token aged out), `cxswap reconnect` will detect and fix it.

## Refresh token rotation, briefly

ChatGPT issues single-use refresh tokens that rotate on every successful refresh. cxswap snapshots the live `auth.json` back into its slot before every swap-out, so the slot's snapshot always carries the latest rotated token. You only get into trouble if you run `codex` twice on the same slot in parallel — both refresh independently, one of them ends up with a token the server has already burned.

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

`~/.codex/auth.json` is the live file Codex reads. cxswap only ever swaps that one file in and out.

## Caveats

- macOS only right now. The "real codex" resolver also strips Superset's bash wrapper from `PATH`.
- Requires `codex` v0.122 or newer (the rollout schema with `rate_limits.primary/secondary` was added around that time).
- `OPENAI_API_KEY` in your environment will override `auth.json`. cxswap unsets it when running `codex login` so the OAuth path wins; if you want `cx` to do the same for the launched session, wrap it: `alias cx='env -u OPENAI_API_KEY cxswap launch'`.

## Uninstall

```bash
uv tool uninstall cxswap        # or: pipx uninstall cxswap
cxswap purge --yes              # before uninstall, removes ~/.codex-swap
```

## Development

```bash
git clone https://github.com/alexneyman/cxswap
cd cxswap
bash scripts/install-dev.sh     # installs editable via uv tool
```

## License

MIT
