"""Documentation invariants for production install routes."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text()


def test_docs_prefer_stable_release_installer():
    docs = _read("README.md") + "\n" + _read("docs/INSTALL.md")

    assert "https://github.com/aneym/codex-swap/releases/latest/download/install.sh" in docs
    assert "raw.githubusercontent.com/aneym/codex-swap/main/scripts/install.sh" not in docs


def test_readme_purges_state_before_uninstalling_tool():
    readme = _read("README.md")

    assert readme.index("codex-swap purge --yes") < readme.index("uv tool uninstall codex-swap")
