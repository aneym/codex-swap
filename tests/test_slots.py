"""Tests for slot resolution helpers in slots.py."""

from __future__ import annotations

import subprocess

from codex_swap import slots
from codex_swap.slots import (
    _resolve,
    add_auth_file,
    next_free_slot,
    slot_for_account_id,
    slot_for_auth,
)


def _seq(*entries: tuple[str, dict]) -> dict:
    return {
        "sequence": [s for s, _ in entries],
        "accounts": {s: a for s, a in entries},
    }


def test_resolve_by_slot_number():
    seq = _seq(("1", {"email": "a@x.com", "account_id": "id-a"}))
    assert _resolve(seq, "1") == "1"


def test_resolve_by_email():
    seq = _seq(("2", {"email": "b@x.com", "account_id": "id-b"}))
    assert _resolve(seq, "b@x.com") == "2"


def test_resolve_by_account_id():
    seq = _seq(("3", {"email": "c@x.com", "account_id": "id-c"}))
    assert _resolve(seq, "id-c") == "3"


def test_resolve_unknown_returns_none():
    seq = _seq(("1", {"email": "a@x.com", "account_id": "id-a"}))
    assert _resolve(seq, "nope") is None


def test_slot_for_account_id_handles_empty():
    assert slot_for_account_id({"accounts": {}}, "anything") is None
    assert slot_for_account_id({"accounts": {"1": {"account_id": "x"}}}, "") is None


def test_slot_for_auth_matches_api_key_fingerprint():
    auth = {"auth_mode": "apikey", "OPENAI_API_KEY": "sk-test"}
    seq = _seq(("2", {"auth_fingerprint": "apikey:f3abf2a6cc4f00987743db5f"}))
    assert slot_for_auth(seq, auth) == "2"


def test_resolve_by_fingerprint_and_label():
    seq = _seq(("2", {"auth_fingerprint": "apikey:fingerprint", "label": "work"}))
    assert _resolve(seq, "apikey:fingerprint") == "2"
    assert _resolve(seq, "work") == "2"


def test_add_auth_file_imports_api_key_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(slots, "ACCOUNTS_DIR", tmp_path / "accounts")
    monkeypatch.setattr(slots, "SEQUENCE_PATH", tmp_path / "sequence.json")
    monkeypatch.setattr(slots, "STATE_PATH", tmp_path / "state.json")

    auth_path = tmp_path / "profile" / "auth.json"
    auth_path.parent.mkdir()
    auth_path.write_text('{"auth_mode": "apikey", "OPENAI_API_KEY": "sk-test"}')

    rc, msg = add_auth_file(auth_path, source_label="work")

    assert rc == 0
    assert "work" in msg
    seq = slots.load_sequence()
    assert seq["sequence"] == ["1"]
    assert seq["accounts"]["1"]["label"] == "work"
    assert seq["accounts"]["1"]["auth_mode"] == "apikey"
    assert seq["accounts"]["1"]["auth_fingerprint"] == "apikey:f3abf2a6cc4f00987743db5f"
    assert (tmp_path / "accounts" / "1" / "auth.json").exists()
    assert not (tmp_path / "state.json").exists()


def test_probe_slot_timeout_handles_bytes_output(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["codex", "exec", "ok"],
            timeout=10,
            output=b"streaming",
            stderr=b"",
        )

    monkeypatch.setattr(slots.subprocess, "run", fake_run)

    assert slots._probe_slot("/usr/local/bin/codex") == (
        "ok",
        "auth ok (response was streaming when timeout fired)",
    )


def test_probe_slot_non_auth_failure_is_error(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr='ERROR: {"detail":"model requires a newer version"}',
        )

    monkeypatch.setattr(slots.subprocess, "run", fake_run)

    status, detail = slots._probe_slot("/usr/local/bin/codex")
    assert status == "error"
    assert "model requires a newer version" in detail


def test_next_free_slot_finds_lowest_gap():
    seq = _seq(("1", {}), ("3", {}))
    assert next_free_slot(seq) == "2"


def test_next_free_slot_appends_when_dense():
    seq = _seq(("1", {}), ("2", {}), ("3", {}))
    assert next_free_slot(seq) == "4"


def test_next_free_slot_starts_at_one():
    assert next_free_slot({"accounts": {}}) == "1"
