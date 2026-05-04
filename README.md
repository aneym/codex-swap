# cxswap

Pick the ChatGPT Pro account with the lowest usage every time you launch [Codex CLI](https://github.com/openai/codex). One command, no thinking.

```
$ cx
cx: using slot 2 (alex@example.com, 5h 4%, 7d 12%)
╭─── OpenAI Codex (v0.128.0) ───╮
│ model: gpt-5.5  fast          │
╰────────────────────────────────╯
```

If you have three Codex Pro accounts and you keep hitting the 5-hour cap on whichever one you happened to be logged into, this is for you. It's the Codex equivalent of [`cswap`](https://pypi.org/project/claude-swap/) for Claude Code.

## What it does

- Saves a snapshot of each account's `~/.codex/auth.json` into its own slot.
- Before each `cx` launch, scans your local Codex rollouts to learn each account's primary (5-hour) and secondary (7-day) usage percent.
- Swaps `auth.json` to the slot with the lowest usage, then `exec`s `codex`.
- Snapshots back any refreshed tokens so the rotation chain never breaks.

## Install

```bash
pipx install cxswap
# or:
uv tool install cxswap
```

That installs two commands: `cxswap` (admin) and `cx` (the smart launcher).

## Quickstart

```bash
# 1. Save your already-logged-in account.
cxswap add

# 2. Onboard the rest. cxswap will prompt fresh logins one at a time.
cxswap onboard 2

# 3. Use codex via cx instead of codex.
cx
```

Add an alias to your shell rc if you want:

```bash
alias cx='cxswap launch'
```

## Commands

| Command | What it does |
|---------|--------------|
| `cxswap add` | Save the currently logged-in account as a new slot |
| `cxswap remove <slot>` | Remove a slot (slot number, email, or account_id) |
| `cxswap list` | Show all slots with usage % |
| `cxswap status` | Show which slot is active right now |
| `cxswap switch [<slot>]` | Switch to a slot (no arg → rotate to next) |
| `cxswap reauth <slot>` | Re-mint a slot via fresh `codex login` |
| `cxswap onboard [N]` | Guided login for N accounts in a row |
| `cxswap verify` | Test every slot's token by running `codex login status` |
| `cxswap usage` | Refresh & print the per-slot usage cache |
| `cxswap launch` | Pick lowest-usage slot, then `exec codex` (this is what `cx` does) |
| `cxswap stash` | Manually save the live `auth.json` back into its slot |
| `cxswap purge --yes` | Delete all cxswap state |

### Pinning and bypass

```bash
cx --cxswap-slot 2          # force a specific slot
cx --cxswap-skip-auto       # skip auto-pick (use whatever's in auth.json)
CXSWAP_SLOT=3 cx            # env equivalent
CXSWAP_SKIP_AUTO=1 cx       # env equivalent
```

Anything after those is forwarded to `codex` unchanged.

## How "lowest usage" is computed

After every Codex turn, the CLI persists a `token_count` event with `rate_limits.primary` (5-hour window) and `rate_limits.secondary` (7-day window) into `~/.codex/sessions/**/*.jsonl`. cxswap correlates conversation IDs to account IDs via `~/.codex/logs_2.sqlite` (`user.account_id="..."` + `conversation.id=...` in the otel log bodies), then for each managed slot pulls the latest snapshot from a rollout owned by that slot. The picker sorts by `(5h%, 7d%, slot#)`.

A slot with no usage data sorts as if it were 101% — it'll be picked only after the others fill up.

## Critical: never run `codex logout`

`codex logout` calls a server-side revoke that **invalidates the refresh token** at the OAuth provider. Every other slot whose snapshot pre-dates that revoke is then permanently dead. cxswap's onboarding and reauth flows use `rm ~/.codex/auth.json` instead — same effect locally, no server-side blast radius.

If a slot ever goes bad (you ran `codex logout` by hand, or the token aged out), recover with:

```bash
cxswap reauth <slot>     # opens a browser, re-mints just that one slot
```

## Refresh token rotation, briefly

ChatGPT issues single-use refresh tokens that rotate on every successful refresh. cxswap calls `stash_active` before every swap-out, so the slot's snapshot always carries the latest rotated token. You only get into trouble if you run `cx` while another `codex` process is also running on the same machine — both refresh independently, one of them ends up with a token the server has already burned.

**Safe:** sequential `cx` sessions.
**Unsafe:** two terminals each running `cx` against different slots simultaneously is fine, but two terminals on the *same* slot will eventually clobber each other.

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

- macOS only right now. The "real codex" resolver also strips Superset's bash wrapper from PATH.
- Requires `codex` v0.122 or newer (the rollout schema with `rate_limits.primary/secondary` was added around that time).
- `OPENAI_API_KEY` in your environment will override `auth.json`. cxswap unsets it when running `codex login` so the OAuth path wins; if you want `cx` to do the same for the launched session, wrap it: `alias cx='env -u OPENAI_API_KEY cxswap launch'`.

## License

MIT
