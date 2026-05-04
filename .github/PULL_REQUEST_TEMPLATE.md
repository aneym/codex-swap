## What

Brief description of the change.

## Why

What problem does this solve, or what does it enable?

## How tested

- [ ] Existing tests pass (`pytest -q`)
- [ ] New tests added for new behavior, where practical
- [ ] Manually tested against a real Codex install with at least 2 ChatGPT Pro accounts (for changes that touch slot-switching logic)

## Notes for reviewers

- [ ] Did NOT add any code path that could call `codex logout` (see `AGENTS.md`)
- [ ] Did NOT introduce concurrent writes to `~/.codex/auth.json`
