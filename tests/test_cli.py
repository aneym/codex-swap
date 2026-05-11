"""CLI glue tests."""

from __future__ import annotations

import argparse
import time

from codex_swap import cli


def test_cx_main_honors_short_slot_env(monkeypatch):
    calls = []

    def fake_launch(args, *, skip_auto=False, pinned_slot=None):
        calls.append((args, skip_auto, pinned_slot))

    monkeypatch.setattr(cli, "launch", fake_launch)
    monkeypatch.setenv("CXSWAP_SLOT", "2")

    assert cli.cx_main(["exec", "ok"]) == 0
    assert calls == [(["exec", "ok"], False, "2")]


def test_cx_main_honors_short_skip_env(monkeypatch):
    calls = []

    def fake_launch(args, *, skip_auto=False, pinned_slot=None):
        calls.append((args, skip_auto, pinned_slot))

    monkeypatch.setattr(cli, "launch", fake_launch)
    monkeypatch.setenv("CXSWAP_SKIP_AUTO", "1")

    assert cli.cx_main(["--model", "gpt-5.5"]) == 0
    assert calls == [(["--model", "gpt-5.5"], True, None)]


def test_cmd_usage_marks_exhausted_slot(monkeypatch, capsys):
    """A persisted exhausted record shows 100%/100% with a `LIMIT REACHED` hint."""
    monkeypatch.setattr(
        cli,
        "refresh_from_rollouts",
        lambda: {
            "2": {
                "primary": {"used_percent": 30.0},
                "secondary": {"used_percent": 47.0},
                "exhausted": True,
                "plan_type": "pro",
                "source": "rollout-exhausted",
            }
        },
    )
    args = argparse.Namespace(json=False)
    assert cli.cmd_usage(args) == 0
    out = capsys.readouterr().out
    assert "slot 2" in out
    assert "5h" in out and "100%" in out
    assert "7d" in out
    assert "LIMIT REACHED" in out


def test_cmd_usage_renders_healthy_slot_normally(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "refresh_from_rollouts",
        lambda: {
            "1": {
                "primary": {"used_percent": 12.0},
                "secondary": {"used_percent": 4.0},
                "plan_type": "pro",
                "source": "rollout",
            }
        },
    )
    args = argparse.Namespace(json=False)
    assert cli.cmd_usage(args) == 0
    out = capsys.readouterr().out
    assert "slot 1" in out
    assert "12%" in out
    assert "4%" in out
    assert "LIMIT REACHED" not in out


def test_cmd_usage_shows_window_reset_times(monkeypatch, capsys):
    """Healthy slots show absolute + relative reset time inline per window."""
    future_5h = int(time.time()) + 4 * 3600
    future_7d = int(time.time()) + 3 * 86400
    monkeypatch.setattr(
        cli,
        "refresh_from_rollouts",
        lambda: {
            "1": {
                "primary": {"used_percent": 38.0, "resets_at": future_5h},
                "secondary": {"used_percent": 99.0, "resets_at": future_7d},
                "plan_type": "pro",
                "source": "rollout",
            }
        },
    )
    args = argparse.Namespace(json=False)
    assert cli.cmd_usage(args) == 0
    out = capsys.readouterr().out
    assert "38%" in out
    assert "99%" in out
    assert "resets " in out
    assert "in 4h" in out
    assert "in 3d" in out


def test_cmd_usage_marks_window_already_reset(monkeypatch, capsys):
    """A past resets_at on an exhausted slot prints 'already reset' so the
    user knows the window has cleared and they can seed."""
    past_5h = int(time.time()) - 60
    future_7d = int(time.time()) + 3 * 86400
    monkeypatch.setattr(
        cli,
        "refresh_from_rollouts",
        lambda: {
            "2": {
                "primary": {"used_percent": 94.0, "resets_at": past_5h},
                "secondary": {"used_percent": 47.0, "resets_at": future_7d},
                "exhausted": True,
                "plan_type": "pro",
                "source": "rollout-exhausted",
            }
        },
    )
    args = argparse.Namespace(json=False)
    assert cli.cmd_usage(args) == 0
    out = capsys.readouterr().out
    assert "100%" in out
    assert "already reset" in out
    assert "LIMIT REACHED" in out


def test_cmd_usage_omits_color_codes_when_not_a_tty(monkeypatch, capsys):
    """Output piped to a non-tty must be ANSI-free for clean grep/redirect."""
    monkeypatch.setattr(
        cli,
        "refresh_from_rollouts",
        lambda: {
            "1": {
                "primary": {"used_percent": 10.0, "resets_at": int(time.time()) + 7200},
                "secondary": {"used_percent": 5.0, "resets_at": int(time.time()) + 600_000},
                "plan_type": "pro",
                "source": "rollout",
            }
        },
    )
    monkeypatch.delenv("CODEX_SWAP_FORCE_COLOR", raising=False)
    args = argparse.Namespace(json=False)
    assert cli.cmd_usage(args) == 0
    out = capsys.readouterr().out
    assert "\033[" not in out


def test_cmd_policy_sets_primary_and_reserve(monkeypatch, capsys):
    saved = []
    monkeypatch.setattr(
        cli,
        "load_sequence",
        lambda: {
            "sequence": ["1", "2", "3"],
            "accounts": {
                "1": {"email": "one@example.com"},
                "2": {"email": "two@example.com"},
                "3": {"email": "three@example.com"},
            },
        },
    )
    monkeypatch.setattr(cli, "load_policy", lambda: {})

    def fake_save(policy):
        saved.append(policy)
        return {
            "primary_slot": policy["primary_slot"],
            "reserve_slots": policy["reserve_slots"],
            "spillover_primary_percent": policy["spillover_primary_percent"],
            "spillover_secondary_percent": policy["spillover_secondary_percent"],
        }

    monkeypatch.setattr(cli, "save_policy", fake_save)
    args = argparse.Namespace(
        primary="one@example.com",
        reserve=["3"],
        spillover_5h=75.0,
        spillover_7d=90.0,
        clear=False,
    )
    assert cli.cmd_policy(args) == 0
    assert saved == [
        {
            "primary_slot": "1",
            "reserve_slots": ["3"],
            "spillover_primary_percent": 75.0,
            "spillover_secondary_percent": 90.0,
        }
    ]
    out = capsys.readouterr().out
    assert "Routing policy: sticky" in out
    assert "primary: 1" in out
    assert "reserves: 3" in out


def test_cmd_anchor_uses_isolated_seed_for_one_slot(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        cli,
        "load_sequence",
        lambda: {"accounts": {"2": {"email": "two@example.com"}}, "sequence": ["2"]},
    )

    def fake_seed(slots, *, max_concurrency, probe_timeout):
        calls.append((slots, max_concurrency, probe_timeout))
        return [("2", "ok", "auth ok")]

    monkeypatch.setattr(cli, "seed_slots", fake_seed)
    args = argparse.Namespace(target="two@example.com", timeout=12.0)
    assert cli.cmd_anchor(args) == 0
    assert calls == [(["2"], 1, 12.0)]
    out = capsys.readouterr().out
    assert "Anchoring sends one tiny isolated Codex probe" in out
