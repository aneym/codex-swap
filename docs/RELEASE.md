# Release Process

Production release automation has three gates:

1. `CI` runs on every push to `main` and pull request.
2. After `CI` succeeds on a `main` push, `Tag release from main` creates `vX.Y.Z` if the package version is new and `CHANGELOG.md` has a matching section.
3. Pushing a `v*` tag runs `Publish to PyPI`, which builds, checks, uploads artifacts, publishes to PyPI, and creates a GitHub release.

## Prepare a Release

```bash
scripts/release.sh 0.1.1 --yes
```

The script:

- requires a clean working tree
- requires `[Unreleased]` changelog notes
- runs `scripts/check-release.sh`
- bumps `src/codex_swap/__init__.py`
- promotes the changelog notes
- creates an annotated tag
- pushes the branch and tag

## Main-Only Automation

If a release commit is pushed to `main` without a tag, the successful `CI` run creates the missing tag automatically. This keeps the production route automated even when maintainers only push the release commit.

## One-Time PyPI Setup

PyPI Trusted Publishing must be configured once:

- Owner: `aneym`
- Repository: `codex-swap`
- Workflow: `publish.yml`
- Environment: `pypi`

GitHub release artifacts are created from the built wheel/sdist. PyPI publishing requires the PyPI-side Trusted Publisher entry.
