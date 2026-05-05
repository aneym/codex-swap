"""CLI glue tests."""

from __future__ import annotations

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
