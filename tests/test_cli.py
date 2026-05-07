"""CLI glue tests."""

from __future__ import annotations

import argparse

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
    """A persisted exhausted record shows 100%/100% with a `limit reached` hint."""
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
    assert "5h=100%" in out
    assert "7d=100%" in out
    assert "limit reached" in out


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
    assert "5h=12%" in out
    assert "7d=4%" in out
    assert "limit reached" not in out
