"""GitHub Actions release automation invariants."""

from __future__ import annotations

from pathlib import Path


def _workflow(name: str) -> str:
    return Path(".github/workflows", name).read_text()


def test_main_push_ci_auto_tags_and_publishes_release():
    ci = _workflow("ci.yml")
    tag_release = _workflow("tag-release.yml")
    publish = _workflow("publish.yml")

    assert "push:" in ci
    assert "branches: [main]" in ci

    assert 'workflows: ["CI"]' in tag_release
    assert "branches: [main]" in tag_release
    assert "github.event.workflow_run.conclusion == 'success'" in tag_release
    assert "github.event.workflow_run.event == 'push'" in tag_release
    assert 'echo "tag=v$version" >> "$GITHUB_OUTPUT"' in tag_release
    assert 'git push origin "$tag"' in tag_release

    assert 'tags: ["v*"]' in publish
    assert "id-token: write" in publish
    assert "pypa/gh-action-pypi-publish" in publish
    assert "softprops/action-gh-release" in publish
