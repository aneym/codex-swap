"""Tests for the legacy `~/.codex-swap/` -> `~/.swap/codex/` migrator."""

from __future__ import annotations

from pathlib import Path

from swap.core.migrate import migrate_codex_legacy


def _redirect_layout(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    """Point the migrator at a tmp legacy + new layout under tmp_path."""
    legacy = tmp_path / "old" / ".codex-swap"
    new_root = tmp_path / "new" / ".swap"
    monkeypatch.setenv("CODEX_SWAP_LEGACY_ROOT", str(legacy))
    monkeypatch.setenv("SWAP_ROOT", str(new_root))
    monkeypatch.delenv("CODEX_SWAP_ROOT", raising=False)
    return legacy, new_root


def test_migrate_codex_legacy_moves_data(monkeypatch, tmp_path):
    legacy, new_root = _redirect_layout(monkeypatch, tmp_path)
    target = new_root / "codex"

    legacy.mkdir(parents=True)
    (legacy / "sequence.json").write_text('{"sequence": ["1"], "accounts": {"1": {}}}')
    (legacy / "accounts").mkdir()
    (legacy / "accounts" / "1").mkdir()
    (legacy / "accounts" / "1" / "auth.json").write_text("{}")

    assert not target.exists()
    assert migrate_codex_legacy(quiet=True) is True
    assert not legacy.exists()
    assert target.exists()
    assert (target / "sequence.json").exists()
    assert (target / "accounts" / "1" / "auth.json").exists()


def test_migrate_codex_legacy_is_idempotent(monkeypatch, tmp_path):
    legacy, new_root = _redirect_layout(monkeypatch, tmp_path)
    target = new_root / "codex"
    legacy.mkdir(parents=True)
    (legacy / "sequence.json").write_text("{}")

    assert migrate_codex_legacy(quiet=True) is True
    assert migrate_codex_legacy(quiet=True) is False  # nothing to do second time
    assert target.exists()


def test_migrate_codex_legacy_skips_when_legacy_absent(monkeypatch, tmp_path):
    _redirect_layout(monkeypatch, tmp_path)
    assert migrate_codex_legacy(quiet=True) is False


def test_migrate_codex_legacy_skips_when_target_already_exists(monkeypatch, tmp_path):
    legacy, new_root = _redirect_layout(monkeypatch, tmp_path)
    target = new_root / "codex"
    legacy.mkdir(parents=True)
    (legacy / "sequence.json").write_text("{}")
    target.mkdir(parents=True)
    (target / "sentinel").write_text("kept")

    assert migrate_codex_legacy(quiet=True) is False
    assert legacy.exists()  # not touched
    assert (target / "sentinel").read_text() == "kept"


def test_migrate_codex_legacy_honors_codex_swap_root(monkeypatch, tmp_path):
    """`CODEX_SWAP_ROOT` overrides the per-provider target root."""
    legacy = tmp_path / "old" / ".codex-swap"
    target = tmp_path / "custom-codex-root"
    monkeypatch.setenv("CODEX_SWAP_LEGACY_ROOT", str(legacy))
    monkeypatch.setenv("CODEX_SWAP_ROOT", str(target))
    monkeypatch.delenv("SWAP_ROOT", raising=False)

    legacy.mkdir(parents=True)
    (legacy / "sequence.json").write_text("{}")

    assert migrate_codex_legacy(quiet=True) is True
    assert target.exists()
    assert (target / "sequence.json").exists()
