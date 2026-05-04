# AGENTS.md — for AI agents helping a human set this up

You're an AI assistant in a chat session with a human who has multiple ChatGPT Pro accounts and wants to use `codex-swap` to switch between them automatically. Walk them through the entire setup in chat, running shell commands on their behalf where you can. The only steps the human must do themselves are the OAuth browser logins.

## What this tool is

`codex-swap` keeps per-account snapshots of `~/.codex/auth.json`, scans local Codex rollouts for each account's rate-limit %, and swaps to the lowest-usage account before launching `codex`. The user-facing command is `cx`. Full admin CLI is `codex-swap`.

## Critical safety rules — never violate these

1. **Never run `codex logout`.** It revokes the refresh token at OpenAI's OAuth server, which kills every other slot whose snapshot pre-dates the revoke. The tool's onboarding/reauth flows use `rm ~/.codex/auth.json` instead. If the human has a stale instinct to "log out and back in," explain why and run `codex-swap reconnect` instead.
2. **Never run `codex` and `cx` in parallel against the same slot.** Refresh tokens are single-use; concurrent refreshes guarantee one process loses. Sequential is fine; parallel against *different* slots is also fine.
3. **Never edit files under `~/.codex-swap/` directly.** Use the CLI subcommands. Snapshots are chmod 600 and contain OAuth refresh tokens.
4. **Treat `~/.codex/auth.json` as live state.** The user's currently-active slot can rotate it at any moment via routine token refreshes. Always go through `codex-swap` so the tool can stash rotated tokens before swapping.

## End-to-end setup script you should run

Run these in order. Each step has a verification gate; don't proceed if a gate fails.

### Step 1 — Confirm prerequisites

```bash
which codex && codex --version       # Codex CLI must be installed, v0.122+
which uv || which pipx               # Either uv or pipx must be available
```

If `codex` is missing: tell the user to install it first (`brew install codex` or `npm i -g @openai/codex`). Stop here.

If neither `uv` nor `pipx` is available: ask the user which to install. `uv` is faster (`curl -LsSf https://astral.sh/uv/install.sh | sh`). `pipx` is more familiar (`brew install pipx`).

### Step 2 — Install codex-swap

```bash
uv tool install git+https://github.com/aneym/codex-swap
# or:
pipx install git+https://github.com/aneym/codex-swap
```

Verify:

```bash
codex-swap --version          # expect: codex-swap 0.1.0 (or newer)
which cx                       # expect: ~/.local/bin/cx
```

If `cx` is not found, tell the user `~/.local/bin` is missing from `PATH` and run:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
exec zsh
```

### Step 3 — Save the currently-logged-in account

The human must already be logged into Codex with one of their ChatGPT Pro accounts. Verify:

```bash
codex login status            # expect: "Logged in using ChatGPT"
```

If "Not logged in" comes back: ask the human to run `codex login` and complete the browser flow, then retry.

If "Logged in":

```bash
codex-swap add                # snapshots auth.json as slot 1
codex-swap status             # confirm: "Active: slot 1 — <email> (pro)"
```

### Step 4 — Onboard the remaining accounts

Ask the human how many more ChatGPT Pro accounts they have (typically 1 or 2 more). Then:

```bash
codex-swap onboard <N>        # N = the count of remaining accounts
```

This runs an interactive loop. For each account:

1. The tool deletes the local `auth.json` (no server-side logout — that's the safety rule above).
2. A browser tab opens for the human to sign in.
3. The new auth.json is snapshotted as the next slot.

**Your job during this loop:** wait silently. Tell the human "log into account 2 in the browser tab that just opened." Don't interrupt. The tool will print a status line per slot saved.

### Step 5 — Verify all slots are healthy

```bash
codex-swap verify             # runs a real `codex exec ok` per slot
```

Each row shows `ok`, `rate_limited`, or `broken`:

- **ok** — slot is usable now.
- **rate_limited** — auth is fine, the account just hit its 5h or 7d cap. Will recover when the window resets.
- **broken** — the refresh token is dead. Need to re-mint:

```bash
codex-swap reconnect          # walks through fresh logins for every broken slot
```

Re-run `codex-swap verify` after `reconnect` and don't stop until no row says `broken`.

### Step 6 — Daily-use confirmation

Once verify shows no broken slots, the human is done. Tell them:

> "Use `cx` instead of `codex` from now on. It auto-picks the slot with the most quota left and `exec`s codex. Run `codex-swap list` any time you want to see usage; run `codex-swap reconnect` if you ever see a 'refresh token' error."

## Subcommand reference for agents

Cheap (safe to run any time, no token cost):
- `codex-swap status` — current active slot
- `codex-swap list` — slots + last-known usage
- `codex-swap usage` — refresh usage cache from rollouts
- `codex-swap stash` — re-snapshot live auth.json into its slot

Mutating (changes auth state on disk):
- `codex-swap add` — current login → new slot
- `codex-swap remove <slot>` — delete a slot
- `codex-swap switch [<slot>]` — copy slot's snapshot → live auth.json
- `codex-swap stash` — copy live auth.json → slot snapshot

Interactive (opens a browser, requires human):
- `codex-swap onboard <N>` — fresh login for N accounts
- `codex-swap reauth <slot>` — fresh login for one specific slot
- `codex-swap reconnect` — verify all + reauth every broken slot

Token-spending (costs ~50 tokens per slot):
- `codex-swap verify` — `codex exec ok` per slot to test auth health

Destructive:
- `codex-swap purge --yes` — wipes `~/.codex-swap/`. Snapshots gone.

## Common failures and fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Your refresh token has already been used` | Slot snapshot is out of sync with server (usually from running `codex logout` somewhere) | `codex-swap reconnect` |
| `cx: switch failed: Snapshot missing` | Slot directory was deleted manually | `codex-swap remove <slot>` then `codex-swap onboard 1` |
| `(No usage data)` for a slot | Slot has never been used since onboarding | Normal — usage % fills in after first use |
| `cx` keeps picking a slot you don't want | That slot has the lowest usage % | `CODEX_SWAP_SLOT=<other> cx` to pin |
| `codex: command not found` after install | `~/.local/bin` not on PATH | `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && exec zsh` |

## Optional: install the convenience aliases

These are short shell wrappers — pure cosmetic. Only add them if the human asks for shorter command names:

```bash
cat <<'EOF' >> ~/.zshrc
cxraw()       { CODEX_SWAP_SKIP_AUTO=1 cx "$@"; }
cxslot()      { CODEX_SWAP_SLOT="$1" cx "${@:2}"; }
cxaccounts()  { codex-swap list "$@"; }
cxstatus()    { codex-swap status "$@"; }
cxverify()    { codex-swap verify "$@"; }
cxreconnect() { codex-swap reconnect "$@"; }
EOF
exec zsh
```

## When you're confused

If the user reports a behavior you don't recognize, run:

```bash
codex-swap status              # what's active
codex-swap list                # what slots exist
codex-swap verify              # which slots are healthy
ls -la ~/.codex-swap/          # data layout
ls -la ~/.codex/auth.json      # live auth file mtime
```

Then read `README.md` "How 'lowest usage' is computed" and "Refresh token rotation" sections — those cover 90% of edge cases.
