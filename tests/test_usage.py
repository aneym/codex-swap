"""Tests for codex usage — rollout parsing, persistence, decay, and merge."""

from __future__ import annotations

import json
import time
from pathlib import Path

from swap.providers.codex import usage as usage_mod
from swap.providers.codex.usage import (
    effective_record,
    effective_used_percent,
    is_exhausted,
    is_exhaustion_signal,
    latest_rate_limits,
    load_persisted,
    merge_into_persisted,
    save_persisted,
    session_id_from_path,
)

# A faithful capture of the rate_limits payload Codex writes to a rollout
# once an account has hit its weekly cap. `primary`/`secondary` go null and
# the depletion is announced via `credits.has_credits=false`.
EXHAUSTION_PAYLOAD = {
    "limit_id": "premium",
    "limit_name": None,
    "primary": None,
    "secondary": None,
    "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
    "plan_type": None,
    "rate_limit_reached_type": None,
}


def _redirect_usage_cache(monkeypatch, target: Path) -> None:
    """Point the provider's usage cache resolver at a tmp file."""
    monkeypatch.setattr(usage_mod, "_usage_cache", lambda: target)


def test_session_id_from_path_extracts_uuid():
    p = Path("rollout-2026-05-04T16-58-12-019df4c8-c9bb-7f32-bdea-c1edf0185198.jsonl")
    assert session_id_from_path(p) == "019df4c8-c9bb-7f32-bdea-c1edf0185198"


def test_session_id_from_path_returns_none_for_garbage():
    assert session_id_from_path(Path("not-a-rollout.jsonl")) is None


def test_latest_rate_limits_finds_most_recent_non_null(tmp_path: Path):
    p = tmp_path / "rollout-2026-05-04T00-00-00-aaa-bbb-ccc-ddd-eee.jsonl"
    events = [
        {
            "timestamp": "2026-05-04T20:00:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {"primary": None, "secondary": None},
            },
        },
        {
            "timestamp": "2026-05-04T20:01:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {
                    "primary": {"used_percent": 12.5, "window_minutes": 300, "resets_at": 1},
                    "secondary": {"used_percent": 4.0, "window_minutes": 10080, "resets_at": 2},
                    "plan_type": "pro",
                },
            },
        },
        {"timestamp": "2026-05-04T20:02:00Z", "type": "session_meta", "payload": {}},
    ]
    p.write_text("\n".join(json.dumps(e) for e in events))
    rl = latest_rate_limits(p)
    assert rl is not None
    assert rl["primary"]["used_percent"] == 12.5
    assert rl["plan_type"] == "pro"


def test_latest_rate_limits_returns_none_for_missing_file(tmp_path: Path):
    assert latest_rate_limits(tmp_path / "does-not-exist.jsonl") is None


def test_latest_rate_limits_skips_invalid_json(tmp_path: Path):
    p = tmp_path / "rollout-x-y-z-w-v-q.jsonl"
    p.write_text("not json\n{\"type\":\"event_msg\",\"payload\":{\"type\":\"token_count\",\"rate_limits\":{\"primary\":{\"used_percent\":1.0}}}}\n")
    rl = latest_rate_limits(p)
    assert rl is not None
    assert rl["primary"]["used_percent"] == 1.0


# --- decay --------------------------------------------------------------------


def test_effective_used_percent_returns_pct_before_reset():
    future = time.time() + 3_600
    window = {"used_percent": 75.0, "resets_at": future}
    assert effective_used_percent(window) == 75.0


def test_effective_used_percent_returns_zero_after_reset():
    past = time.time() - 30
    window = {"used_percent": 99.0, "resets_at": past}
    assert effective_used_percent(window) == 0.0


def test_effective_used_percent_handles_missing_resets_at():
    """If we have a percent but no resets_at, return the raw percent."""
    window = {"used_percent": 50.0}
    assert effective_used_percent(window) == 50.0


def test_effective_used_percent_returns_none_for_no_data():
    assert effective_used_percent(None) is None
    assert effective_used_percent({}) is None
    assert effective_used_percent({"used_percent": None}) is None


def test_effective_record_marks_reset_window():
    past = time.time() - 30
    rec = {
        "primary": {"used_percent": 90.0, "resets_at": past},
        "secondary": {"used_percent": 20.0, "resets_at": time.time() + 10_000},
    }
    out = effective_record(rec)
    assert out["primary"]["used_percent_effective"] == 0.0
    assert out["primary"]["window_reset"] is True
    assert out["secondary"]["used_percent_effective"] == 20.0
    assert "window_reset" not in out["secondary"]


# --- persistence + merge ------------------------------------------------------


def test_persisted_roundtrip(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    save_persisted({"1": {"primary": {"used_percent": 10.0}, "scanned_at": 100.0}})
    loaded = load_persisted()
    assert loaded["1"]["primary"]["used_percent"] == 10.0


def test_load_persisted_handles_missing_file(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "missing.json")
    assert load_persisted() == {}


def test_merge_into_persisted_keeps_unrelated_slots(tmp_path: Path, monkeypatch):
    """A scan that only finds slot 2 must not erase slot 1."""
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    save_persisted({
        "1": {"primary": {"used_percent": 10.0}, "scanned_at": 100.0},
        "2": {"primary": {"used_percent": 20.0}, "scanned_at": 100.0},
    })
    merged = merge_into_persisted({
        "2": {"primary": {"used_percent": 30.0}, "scanned_at": 200.0},
    })
    assert merged["1"]["primary"]["used_percent"] == 10.0  # untouched
    assert merged["2"]["primary"]["used_percent"] == 30.0  # updated


def test_merge_into_persisted_only_replaces_when_newer(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    save_persisted({"1": {"primary": {"used_percent": 50.0}, "scanned_at": 200.0}})
    merged = merge_into_persisted({
        "1": {"primary": {"used_percent": 99.0}, "scanned_at": 100.0},
    })
    assert merged["1"]["primary"]["used_percent"] == 50.0


def test_merge_into_persisted_adds_brand_new_slots(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    save_persisted({"1": {"primary": {"used_percent": 10.0}, "scanned_at": 100.0}})
    merged = merge_into_persisted({
        "3": {"primary": {"used_percent": 5.0}, "scanned_at": 150.0},
    })
    assert set(merged.keys()) == {"1", "3"}


def test_merge_ignores_non_dict_payload(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    save_persisted({"1": {"primary": {"used_percent": 10.0}, "scanned_at": 100.0}})
    merge_into_persisted({"2": "not a dict", "3": None})
    assert load_persisted() == {"1": {"primary": {"used_percent": 10.0}, "scanned_at": 100.0}}


# --- exhaustion detection -----------------------------------------------------


def test_is_exhaustion_signal_detects_no_credits():
    assert is_exhaustion_signal(EXHAUSTION_PAYLOAD)


def test_is_exhaustion_signal_detects_reached_type():
    rl = {
        "primary": None,
        "secondary": None,
        "credits": {"has_credits": True},
        "rate_limit_reached_type": "secondary",
    }
    assert is_exhaustion_signal(rl)


def test_is_exhaustion_signal_rejects_healthy_snapshot():
    rl = {"primary": {"used_percent": 50.0}, "secondary": {"used_percent": 30.0}}
    assert not is_exhaustion_signal(rl)


def test_is_exhaustion_signal_rejects_pure_no_data():
    """All-null with no credits hint and no reached_type carries no info."""
    rl = {"primary": None, "secondary": None, "credits": {"has_credits": True}}
    assert not is_exhaustion_signal(rl)


def test_is_exhaustion_signal_rejects_non_dict():
    assert not is_exhaustion_signal(None)
    assert not is_exhaustion_signal("nope")


def test_latest_rate_limits_keeps_exhaustion_after_healthy(tmp_path: Path):
    """A successful early call followed by a rate-limit-reached event must
    leave the exhaustion signal as the latest snapshot — not the healthy one."""
    p = tmp_path / "rollout-2026-05-07T00-00-00-aaa-bbb-ccc-ddd-eee.jsonl"
    events = [
        {
            "timestamp": "2026-05-07T09:00:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {
                    "primary": {"used_percent": 30.0},
                    "secondary": {"used_percent": 47.0},
                },
            },
        },
        {
            "timestamp": "2026-05-07T09:51:00Z",
            "type": "event_msg",
            "payload": {"type": "token_count", "rate_limits": EXHAUSTION_PAYLOAD},
        },
    ]
    p.write_text("\n".join(json.dumps(e) for e in events))
    rl = latest_rate_limits(p)
    assert rl is not None
    assert is_exhaustion_signal(rl)


def test_latest_rate_limits_skips_pure_no_data(tmp_path: Path):
    """A snapshot with both windows null and no exhaustion hint is still skipped."""
    p = tmp_path / "rollout-2026-05-07T00-00-00-aaa-bbb-ccc-ddd-eee.jsonl"
    events = [
        {
            "timestamp": "2026-05-07T09:00:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {
                    "primary": {"used_percent": 30.0},
                    "secondary": {"used_percent": 12.0},
                },
            },
        },
        {
            "timestamp": "2026-05-07T09:01:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {"primary": None, "secondary": None},
            },
        },
    ]
    p.write_text("\n".join(json.dumps(e) for e in events))
    rl = latest_rate_limits(p)
    assert rl is not None
    assert rl["primary"]["used_percent"] == 30.0


# --- exhaustion record persistence -------------------------------------------


def test_merge_exhaustion_inherits_prior_window_timing(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    save_persisted({
        "2": {
            "primary": {"used_percent": 30.0, "resets_at": 1_111},
            "secondary": {"used_percent": 47.0, "resets_at": 9_999},
            "plan_type": "pro",
            "scanned_at": 100.0,
        }
    })
    merged = merge_into_persisted({
        "2": {
            "primary": None,
            "secondary": None,
            "plan_type": None,
            "exhausted": True,
            "exhausted_at": 200.0,
            "rate_limit_reached_type": None,
            "scanned_at": 200.0,
            "source": "rollout-exhausted",
            "source_path": "/tmp/rollout-x.jsonl",
        }
    })
    rec = merged["2"]
    assert rec["exhausted"] is True
    assert rec["exhausted_at"] == 200.0
    assert rec["primary"]["resets_at"] == 1_111
    assert rec["secondary"]["resets_at"] == 9_999
    assert rec["plan_type"] == "pro"
    assert rec["source"] == "rollout-exhausted"


def test_merge_exhaustion_with_no_prior_record(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    merged = merge_into_persisted({
        "1": {
            "primary": None,
            "secondary": None,
            "plan_type": None,
            "exhausted": True,
            "exhausted_at": 200.0,
            "scanned_at": 200.0,
            "source": "rollout-exhausted",
        }
    })
    rec = merged["1"]
    assert rec["exhausted"] is True
    assert rec["primary"] is None
    assert rec["secondary"] is None


def test_merge_healthy_replaces_prior_exhaustion(tmp_path: Path, monkeypatch):
    _redirect_usage_cache(monkeypatch, tmp_path / "usage.json")
    save_persisted({
        "1": {
            "primary": None,
            "secondary": None,
            "exhausted": True,
            "exhausted_at": 100.0,
            "scanned_at": 100.0,
        }
    })
    merged = merge_into_persisted({
        "1": {
            "primary": {"used_percent": 5.0},
            "secondary": {"used_percent": 2.0},
            "plan_type": "pro",
            "scanned_at": 200.0,
            "source": "rollout",
        }
    })
    rec = merged["1"]
    assert "exhausted" not in rec or rec.get("exhausted") in (False, None)
    assert rec["primary"]["used_percent"] == 5.0


def test_is_exhausted_helper():
    assert is_exhausted({"exhausted": True})
    assert not is_exhausted({"exhausted": False})
    assert not is_exhausted({})
    assert not is_exhausted(None)


def test_effective_record_preserves_exhausted_flag():
    rec = {
        "primary": None,
        "secondary": {"used_percent": 47.0, "resets_at": time.time() + 10_000},
        "exhausted": True,
    }
    out = effective_record(rec)
    assert out["exhausted"] is True
    assert out["secondary"]["used_percent_effective"] == 47.0
