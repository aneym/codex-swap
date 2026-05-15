"""Project metadata invariants."""

from __future__ import annotations

import re
from pathlib import Path

import codex_swap
import swap


def test_version_is_semver_like():
    assert re.match(r"^\d+\.\d+\.\d+", codex_swap.__version__)
    assert codex_swap.__version__ == swap.__version__


def test_pyproject_uses_package_version_as_single_source():
    pyproject = Path("pyproject.toml").read_text()
    assert 'dynamic = ["version"]' in pyproject
    assert 'path = "src/swap/__init__.py"' in pyproject
    assert '\nversion = "' not in pyproject
