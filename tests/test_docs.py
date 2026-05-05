"""Documentation invariants for production install routes."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text()


def test_docs_prefer_stable_release_installer():
    docs = _read("README.md") + "\n" + _read("docs/INSTALL.md")

    assert "https://github.com/aneym/codex-swap/releases/latest/download/install.sh" in docs
    assert "raw.githubusercontent.com/aneym/codex-swap/main/scripts/install.sh" not in docs


def test_readme_advertises_live_pypi_badge():
    readme = _read("README.md")

    assert "img.shields.io/pypi/v/codex-swap" in readme
    assert "img.shields.io/github/v/release/aneym/codex-swap" in readme


def test_readme_prefers_pypi_package_installs():
    readme = _read("README.md")

    assert "Until codex-swap is on PyPI" not in readme
    assert "After PyPI Trusted Publishing is configured" not in readme
    assert readme.index("uv tool install codex-swap") < readme.index(
        "https://github.com/aneym/codex-swap/releases/download/"
    )


def test_release_docs_spell_out_pypi_pending_publisher():
    docs = _read("README.md") + "\n" + _read("docs/RELEASE.md")

    assert "pending publisher flow" in docs
    assert "PyPI project name: `codex-swap`" in docs
    assert "Owner: `aneym`" in docs
    assert "Repository: `codex-swap`" in docs
    assert "Workflow: `publish.yml`" in docs
    assert "Environment: `pypi`" in docs


def test_readme_purges_state_before_uninstalling_tool():
    readme = _read("README.md")

    assert readme.index("codex-swap purge --yes") < readme.index("uv tool uninstall codex-swap")
