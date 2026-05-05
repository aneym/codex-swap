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
    assert "actions/checkout@v6" in ci
    assert "actions/checkout@v4" not in ci
    assert "install smoke" in ci
    assert "bash scripts/smoke-install.sh --source release" in ci

    assert 'workflows: ["CI"]' in tag_release
    assert "branches: [main]" in tag_release
    assert "actions/checkout@v6" in tag_release
    assert "actions/checkout@v4" not in tag_release
    assert "github.event.workflow_run.conclusion == 'success'" in tag_release
    assert "github.event.workflow_run.event == 'push'" in tag_release
    assert 'echo "tag=v$version" >> "$GITHUB_OUTPUT"' in tag_release
    assert 'git push origin "$tag"' in tag_release

    assert 'tags: ["v*"]' in publish
    assert "actions/checkout@v6" in publish
    assert "actions/checkout@v4" not in publish
    assert "id-token: write" in publish
    assert "pypa/gh-action-pypi-publish" in publish
    assert "softprops/action-gh-release" in publish
    assert "sha256sum dist/* install.sh > SHA256SUMS" in publish
    assert "install.sh" in publish
    assert "SHA256SUMS" in publish
