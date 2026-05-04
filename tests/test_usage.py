"""Tests for usage.py — rollout parsing and session id extraction."""

from __future__ import annotations

import json
from pathlib import Path

from codex_swap.usage import latest_rate_limits, session_id_from_path


def test_session_id_from_path_extracts_uuid():
    p = Path("rollout-2026-05-04T16-58-12-019df4c8-c9bb-7f32-bdea-c1edf0185198.jsonl")
    assert session_id_from_path(p) == "019df4c8-c9bb-7f32-bdea-c1edf0185198"


def test_session_id_from_path_returns_none_for_garbage():
    assert session_id_from_path(Path("not-a-rollout.jsonl")) is None


def test_latest_rate_limits_finds_most_recent_non_null(tmp_path: Path):
    p = tmp_path / "rollout-2026-05-04T00-00-00-aaa-bbb-ccc-ddd-eee.jsonl"
    events = [
        # Earlier event with null rate limits
        {
            "timestamp": "2026-05-04T20:00:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "rate_limits": {"primary": None, "secondary": None},
            },
        },
        # Later event with real data — this is what we want
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
        # An event of a different type — should be ignored
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
