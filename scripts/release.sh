#!/usr/bin/env bash
# Cut a new release: bump version, update changelog, tag, push.
# The publish workflow takes over from there.
#
# Usage: scripts/release.sh 0.1.1

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $0 <version>" >&2
  echo "example: $0 0.1.1" >&2
  exit 1
fi

VERSION="$1"
TAG="v${VERSION}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is dirty. Commit or stash first." >&2
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists." >&2
  exit 1
fi

# Bump pyproject.toml
perl -i -pe "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml

# Promote the [Unreleased] block in CHANGELOG.md into a versioned section.
DATE="$(date +%Y-%m-%d)"
perl -i -pe "s/^## \\[Unreleased\\]/## [Unreleased]\n\n## ${VERSION} — ${DATE}/" CHANGELOG.md

git add pyproject.toml CHANGELOG.md
git commit -m "Release ${VERSION}"
git tag -a "$TAG" -m "Release ${VERSION}"

echo
echo "About to push:"
echo "  branch: $(git rev-parse --abbrev-ref HEAD)"
echo "  tag:    $TAG"
echo "Press Enter to push (Ctrl-C to abort)..."
read -r _

git push origin "$(git rev-parse --abbrev-ref HEAD)"
git push origin "$TAG"

echo
echo "Pushed. The publish workflow will build, push to PyPI, and create the GitHub release:"
echo "  https://github.com/aneym/codex-swap/actions"
