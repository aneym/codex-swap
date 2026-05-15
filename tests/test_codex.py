"""Tests for Codex binary discovery."""

from __future__ import annotations

import subprocess
from pathlib import Path

from swap.providers.codex import binary as codex_binary


def test_codex_version_parses_cli_output(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="codex-cli 0.128.0\n", stderr="")

    monkeypatch.setattr(codex_binary.subprocess, "run", fake_run)

    assert codex_binary._codex_version(Path("/tmp/codex")) == (0, 128, 0)


def test_find_real_codex_picks_newest_candidate(monkeypatch, tmp_path):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old = old_dir / "codex"
    new = new_dir / "codex"
    old.write_text("#!/bin/sh\n")
    new.write_text("#!/bin/sh\n")
    old.chmod(0o755)
    new.chmod(0o755)

    monkeypatch.setenv("PATH", f"{old_dir}:{new_dir}")

    def fake_version(path):
        if path == old:
            return (0, 101, 0)
        if path == new:
            return (0, 128, 0)
        return None

    monkeypatch.setattr(codex_binary, "_codex_version", fake_version)

    assert codex_binary.find_binary() == str(new)
