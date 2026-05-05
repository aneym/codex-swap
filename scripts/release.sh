#!/usr/bin/env bash
# Cut a production release: verify package gates, bump version, tag, and push.
#
# Main-branch automation also exists: after CI passes on a push to main,
# .github/workflows/tag-release.yml creates the missing vX.Y.Z tag for the
# version in src/codex_swap/__init__.py. This script remains the maintainer
# fast path for preparing and pushing the release locally.
#
# Usage:
#   scripts/release.sh 0.1.1
#   scripts/release.sh 0.1.1 --yes
#   scripts/release.sh 0.1.1 --no-push

set -euo pipefail

YES=0
PUSH=1
RUN_CHECKS=1

usage() {
  cat <<'USAGE'
Release codex-swap.

Usage:
  scripts/release.sh <version> [options]

Options:
  --yes          Push branch and tag without prompting.
  --no-push      Commit and tag locally, but do not push.
  --skip-checks  Skip scripts/check-release.sh. Use only after running it manually.
  -h, --help     Show this help.
USAGE
}

if [ $# -lt 1 ]; then
  usage >&2
  exit 1
fi

case "$1" in
  -h|--help)
    usage
    exit 0
    ;;
esac

VERSION="$1"
shift

while [ $# -gt 0 ]; do
  case "$1" in
    --yes)
      YES=1
      shift
      ;;
    --no-push)
      PUSH=0
      shift
      ;;
    --skip-checks)
      RUN_CHECKS=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([a-zA-Z0-9.+-]+)?$ ]]; then
  echo "Version must look like 1.2.3 or 1.2.3rc1; got: $VERSION" >&2
  exit 2
fi

TAG="v${VERSION}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is dirty. Commit or stash first." >&2
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists locally." >&2
  exit 1
fi

if git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists on origin." >&2
  exit 1
fi

unreleased="$(
  awk '
    /^## \[Unreleased\]/ { found=1; next }
    found && /^## / { exit }
    found && NF { print }
  ' CHANGELOG.md
)"
if [ -z "$unreleased" ]; then
  echo "CHANGELOG.md has no [Unreleased] notes to release." >&2
  exit 1
fi

perl -i -pe "s/^__version__ = \".*\"/__version__ = \"${VERSION}\"/" src/codex_swap/__init__.py

DATE="$(date +%Y-%m-%d)"
perl -i -pe "s/^## \\[Unreleased\\]/## [Unreleased]\n\n## ${VERSION} — ${DATE}/" CHANGELOG.md

if [ "$RUN_CHECKS" -eq 1 ]; then
  bash scripts/check-release.sh
fi

git add src/codex_swap/__init__.py CHANGELOG.md
git commit -m "chore: release ${VERSION}"
git tag -a "$TAG" -m "Release ${VERSION}"

echo
echo "Created release commit and tag:"
echo "  commit: $(git rev-parse --short HEAD)"
echo "  tag:    $TAG"

if [ "$PUSH" -eq 0 ]; then
  echo "Not pushing because --no-push was provided."
  exit 0
fi

if [ "$YES" -ne 1 ]; then
  echo "About to push branch $(git rev-parse --abbrev-ref HEAD) and tag $TAG."
  echo "Press Enter to push (Ctrl-C to abort)..."
  read -r _
fi

git push origin "$(git rev-parse --abbrev-ref HEAD)"
git push origin "$TAG"

echo
echo "Pushed. The publish workflow will build, publish to PyPI, and create the GitHub release:"
echo "  https://github.com/aneym/codex-swap/actions/workflows/publish.yml"
