"""Smoke tests for shell entrypoint scripts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_install_script_help():
    proc = _run("bash", "scripts/install.sh", "--help")
    assert "Install codex-swap" in proc.stdout
    assert "--source auto|pypi|release|git" in proc.stdout


def test_install_script_dry_run_release():
    env = os.environ.copy()
    env["CODEX_SWAP_INSTALL_RELEASE_TAG"] = "v9.8.7"
    proc = subprocess.run(
        ["bash", "scripts/install.sh", "--dry-run", "--source", "release", "--no-path-check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    combined = proc.stdout + proc.stderr
    assert "https://github.com/aneym/codex-swap/releases/download/v9.8.7/" in combined
    assert "codex_swap-9.8.7-py3-none-any.whl" in combined
    assert "tool install" in combined or "pipx install" in combined


def test_install_script_dry_run_auto_uses_release_before_main():
    env = os.environ.copy()
    env["CODEX_SWAP_INSTALL_RELEASE_TAG"] = "v9.8.7"
    proc = subprocess.run(
        ["bash", "scripts/install.sh", "--dry-run", "--source", "auto", "--no-path-check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    combined = proc.stdout + proc.stderr
    assert "codex-swap" in combined
    assert "https://github.com/aneym/codex-swap/releases/download/v9.8.7/" in combined
    assert "codex_swap-9.8.7-py3-none-any.whl" in combined
    assert "git+https://github.com/aneym/codex-swap" in combined


def test_release_script_help():
    proc = _run("bash", "scripts/release.sh", "--help")
    assert "Release codex-swap" in proc.stdout
    assert "--no-push" in proc.stdout


def test_shell_scripts_have_no_syntax_errors():
    scripts = ["scripts/install.sh", "scripts/release.sh", "scripts/check-release.sh"]
    env = os.environ.copy()
    for script in scripts:
        subprocess.run(["bash", "-n", script], cwd=ROOT, env=env, check=True)
