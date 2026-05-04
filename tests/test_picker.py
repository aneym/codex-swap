"""Tests for the slot scoring & picker logic — pure functions, no IO."""

from __future__ import annotations

from codex_swap.launcher import _choose, _slot_score


def test_slot_score_unknown_usage_sorts_last():
    score = _slot_score("3", {})
    # Unknown usage should sort *after* any known data — penalty bucket is 1.
    assert score[0] == 1


def test_slot_score_known_usage_uses_pcts():
    usage = {
        "1": {
            "primary": {"used_percent": 25.0},
            "secondary": {"used_percent": 12.0},
        }
    }
    bucket, pri, sec, slot = _slot_score("1", usage)
    assert bucket == 0
    assert pri == 25.0
    assert sec == 12.0
    assert slot == 1


def test_choose_picks_lowest_primary():
    seq = {"sequence": ["1", "2", "3"]}
    usage = {
        "1": {"primary": {"used_percent": 80.0}, "secondary": {"used_percent": 0}},
        "2": {"primary": {"used_percent": 5.0}, "secondary": {"used_percent": 50}},
        "3": {"primary": {"used_percent": 5.0}, "secondary": {"used_percent": 10}},
    }
    # Both 2 and 3 have 5% primary; secondary breaks the tie -> slot 3.
    assert _choose(seq, usage) == "3"


def test_choose_skips_unknown_when_known_is_lower():
    seq = {"sequence": ["1", "2"]}
    usage = {
        "1": {"primary": {"used_percent": 10.0}, "secondary": {"used_percent": 0}}
    }
    # Slot 2 has no usage data -> sorts last; slot 1 wins.
    assert _choose(seq, usage) == "1"


def test_choose_picks_unknown_only_when_no_known_data():
    seq = {"sequence": ["1", "2"]}
    assert _choose(seq, {}) in {"1", "2"}


def test_choose_empty_sequence_returns_none():
    assert _choose({"sequence": []}, {}) is None
