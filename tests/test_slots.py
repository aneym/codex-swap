"""Tests for slot resolution helpers in slots.py."""

from __future__ import annotations

from codex_swap.slots import _resolve, next_free_slot, slot_for_account_id


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


def test_next_free_slot_finds_lowest_gap():
    seq = _seq(("1", {}), ("3", {}))
    assert next_free_slot(seq) == "2"


def test_next_free_slot_appends_when_dense():
    seq = _seq(("1", {}), ("2", {}), ("3", {}))
    assert next_free_slot(seq) == "4"


def test_next_free_slot_starts_at_one():
    assert next_free_slot({"accounts": {}}) == "1"
