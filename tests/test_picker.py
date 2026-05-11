"""Tests for the slot scoring & picker logic — pure functions, no IO."""

from __future__ import annotations

import time

from codex_swap.launcher import (
    NEAR_CAP_PERCENT,
    _choose,
    _policy_score,
    _slot_score,
    _unknown_slots,
)


def test_slot_score_unknown_usage_treated_as_fresh():
    """Unknown usage scores as bucket 1 with 0/0 percents (assume fresh)."""
    bucket, pri, sec, slot = _slot_score("3", {})
    assert bucket == 1
    assert pri == 0.0
    assert sec == 0.0
    assert slot == 3


def test_slot_score_known_low_usage_uses_pcts():
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


def test_slot_score_near_cap_falls_below_unknown():
    """Known + near cap on either window ranks WORSE than an unknown slot."""
    usage_high = {
        "1": {
            "primary": {"used_percent": 95.0},
            "secondary": {"used_percent": 50.0},
        }
    }
    near_cap_bucket, *_ = _slot_score("1", usage_high)
    unknown_bucket, *_ = _slot_score("2", {})
    assert near_cap_bucket > unknown_bucket
    assert near_cap_bucket == 2


def test_slot_score_near_cap_secondary_alone_is_enough():
    """High secondary (7d) usage alone qualifies as near-cap."""
    usage = {
        "1": {
            "primary": {"used_percent": 5.0},
            "secondary": {"used_percent": NEAR_CAP_PERCENT + 1.0},
        }
    }
    bucket, *_ = _slot_score("1", usage)
    assert bucket == 2


def test_slot_score_decays_after_resets_at():
    """A 95% slot whose primary window has reset should score as 0% via decay."""
    past = time.time() - 60
    usage = {
        "1": {
            "primary": {"used_percent": 95.0, "resets_at": past},
            "secondary": {"used_percent": 30.0, "resets_at": past + 10_000},
        }
    }
    bucket, pri, sec, _ = _slot_score("1", usage)
    assert bucket == 0  # primary decayed to 0; secondary still healthy
    assert pri == 0.0
    assert sec == 30.0


def test_choose_picks_lowest_primary():
    seq = {"sequence": ["1", "2", "3"]}
    usage = {
        "1": {"primary": {"used_percent": 70.0}, "secondary": {"used_percent": 0}},
        "2": {"primary": {"used_percent": 5.0}, "secondary": {"used_percent": 50}},
        "3": {"primary": {"used_percent": 5.0}, "secondary": {"used_percent": 10}},
    }
    # Both 2 and 3 have 5% primary; secondary breaks the tie -> slot 3.
    assert _choose(seq, usage) == "3"


def test_choose_prefers_known_low_over_unknown():
    """Known + low usage still beats unknown — don't waste a rotation."""
    seq = {"sequence": ["1", "2"]}
    usage = {"1": {"primary": {"used_percent": 10.0}, "secondary": {"used_percent": 0}}}
    assert _choose(seq, usage) == "1"


def test_choose_picks_unknown_over_near_cap():
    """The bug fix: a 90% slot must NOT block rotation to an unknown slot."""
    seq = {"sequence": ["1", "2", "3"]}
    usage = {
        "1": {"primary": {"used_percent": 90.0}, "secondary": {"used_percent": 27.0}},
    }
    assert _choose(seq, usage) in {"2", "3"}


def test_choose_picks_known_low_over_unknown_and_near_cap():
    seq = {"sequence": ["1", "2", "3"]}
    usage = {
        "1": {"primary": {"used_percent": 90.0}, "secondary": {"used_percent": 27.0}},
        "2": {"primary": {"used_percent": 8.0}, "secondary": {"used_percent": 5.0}},
    }
    assert _choose(seq, usage) == "2"


def test_choose_picks_least_bad_when_all_at_cap():
    seq = {"sequence": ["1", "2"]}
    usage = {
        "1": {"primary": {"used_percent": 95.0}, "secondary": {"used_percent": 30.0}},
        "2": {"primary": {"used_percent": 88.0}, "secondary": {"used_percent": 30.0}},
    }
    assert _choose(seq, usage) == "2"


def test_choose_picks_unknown_only_when_no_known_data():
    seq = {"sequence": ["1", "2"]}
    assert _choose(seq, {}) in {"1", "2"}


def test_choose_empty_sequence_returns_none():
    assert _choose({"sequence": []}, {}) is None


def test_choose_routes_to_decayed_slot_after_reset():
    """A previously-near-cap slot whose window reset wins over an at-cap one."""
    past = time.time() - 30
    seq = {"sequence": ["1", "2"]}
    usage = {
        "1": {
            "primary": {"used_percent": 92.0, "resets_at": time.time() + 10_000},
            "secondary": {"used_percent": 30.0},
        },
        "2": {
            "primary": {"used_percent": 91.0, "resets_at": past},
            "secondary": {"used_percent": 30.0},
        },
    }
    # Slot 2's primary decayed to 0; slot 1 is still at 92.
    assert _choose(seq, usage) == "2"


def test_unknown_slots_returns_only_unmeasured():
    seq = {"accounts": {"1": {}, "2": {}, "3": {}}}
    usage = {"1": {"primary": {"used_percent": 10.0}}}
    assert _unknown_slots(seq, usage) == ["2", "3"]


def test_unknown_slots_empty_when_all_known():
    seq = {"accounts": {"1": {}, "2": {}}}
    usage = {"1": {}, "2": {}}
    assert _unknown_slots(seq, usage) == []


# --- exhaustion handling ------------------------------------------------------


def test_slot_score_exhausted_drops_to_worst_bucket():
    """A slot flagged exhausted ranks below an unmeasured slot, even when its
    last persisted percents look low."""
    usage = {
        "1": {
            "primary": {"used_percent": 30.0},
            "secondary": {"used_percent": 47.0},
            "exhausted": True,
        }
    }
    bucket, pri, sec, _ = _slot_score("1", usage)
    assert bucket == 2
    assert pri == 100.0
    assert sec == 100.0


def test_choose_avoids_exhausted_even_with_lowest_pct():
    """The bug: slot 2's cache showed 47% and got picked despite hitting cap.
    Once flagged exhausted, the picker must rotate away."""
    seq = {"sequence": ["1", "2", "3"]}
    usage = {
        "1": {"primary": {"used_percent": 75.0}, "secondary": {"used_percent": 60.0}},
        "2": {
            "primary": {"used_percent": 30.0},
            "secondary": {"used_percent": 47.0},
            "exhausted": True,
        },
    }
    # Slot 1 is healthy-ish (bucket 0); slot 3 has no record (bucket 1);
    # slot 2 is exhausted (bucket 2). Slot 1 wins.
    assert _choose(seq, usage) == "1"


def test_choose_prefers_unknown_over_exhausted():
    """An unmeasured slot beats an exhausted one — same logic as near-cap."""
    seq = {"sequence": ["1", "2"]}
    usage = {
        "1": {
            "primary": {"used_percent": 30.0},
            "secondary": {"used_percent": 47.0},
            "exhausted": True,
        },
    }
    assert _choose(seq, usage) == "2"


# --- sticky policy ------------------------------------------------------------


def test_choose_sticky_policy_prefers_primary_over_lower_usage_slot():
    seq = {"sequence": ["1", "2", "3"]}
    usage = {
        "1": {"primary": {"used_percent": 50.0}, "secondary": {"used_percent": 80.0}},
        "2": {"primary": {"used_percent": 1.0}, "secondary": {"used_percent": 1.0}},
    }
    policy = {
        "primary_slot": "1",
        "reserve_slots": [],
        "spillover_primary_percent": 80.0,
        "spillover_secondary_percent": 95.0,
    }
    assert _choose(seq, usage, policy) == "1"


def test_choose_sticky_policy_spills_over_when_primary_5h_is_high():
    seq = {"sequence": ["1", "2"]}
    usage = {
        "1": {"primary": {"used_percent": 80.0}, "secondary": {"used_percent": 20.0}},
        "2": {"primary": {"used_percent": 40.0}, "secondary": {"used_percent": 20.0}},
    }
    policy = {
        "primary_slot": "1",
        "reserve_slots": [],
        "spillover_primary_percent": 80.0,
        "spillover_secondary_percent": 95.0,
    }
    assert _choose(seq, usage, policy) == "2"


def test_choose_sticky_policy_spills_over_when_primary_7d_is_near_done():
    seq = {"sequence": ["1", "2"]}
    usage = {
        "1": {"primary": {"used_percent": 10.0}, "secondary": {"used_percent": 95.0}},
        "2": {"primary": {"used_percent": 40.0}, "secondary": {"used_percent": 20.0}},
    }
    policy = {
        "primary_slot": "1",
        "reserve_slots": [],
        "spillover_primary_percent": 80.0,
        "spillover_secondary_percent": 95.0,
    }
    assert _choose(seq, usage, policy) == "2"


def test_choose_sticky_policy_uses_primary_when_usage_unknown():
    seq = {"sequence": ["1", "2"]}
    policy = {
        "primary_slot": "1",
        "reserve_slots": [],
        "spillover_primary_percent": 80.0,
        "spillover_secondary_percent": 95.0,
    }
    assert _choose(seq, {}, policy) == "1"


def test_policy_score_keeps_healthy_reserve_ahead_of_capped_regular_slot():
    usage = {
        "1": {"primary": {"used_percent": 95.0}, "secondary": {"used_percent": 30.0}},
        "2": {"primary": {"used_percent": 2.0}, "secondary": {"used_percent": 2.0}},
    }
    regular_score = _policy_score("1", usage, {"2"})
    reserve_score = _policy_score("2", usage, {"2"})
    assert reserve_score < regular_score


def test_policy_score_keeps_near_cap_reserve_ahead_of_exhausted_regular_slot():
    usage = {
        "1": {
            "primary": {"used_percent": 20.0},
            "secondary": {"used_percent": 20.0},
            "exhausted": True,
        },
        "2": {"primary": {"used_percent": 90.0}, "secondary": {"used_percent": 20.0}},
    }
    regular_score = _policy_score("1", usage, {"2"})
    reserve_score = _policy_score("2", usage, {"2"})
    assert reserve_score < regular_score


def test_choose_policy_avoids_reserve_when_regular_slot_is_healthy():
    seq = {"sequence": ["1", "2", "3"]}
    usage = {
        "1": {"primary": {"used_percent": 90.0}, "secondary": {"used_percent": 20.0}},
        "2": {"primary": {"used_percent": 30.0}, "secondary": {"used_percent": 30.0}},
        "3": {"primary": {"used_percent": 1.0}, "secondary": {"used_percent": 1.0}},
    }
    policy = {
        "primary_slot": "1",
        "reserve_slots": ["3"],
        "spillover_primary_percent": 80.0,
        "spillover_secondary_percent": 95.0,
    }
    assert _choose(seq, usage, policy) == "2"
