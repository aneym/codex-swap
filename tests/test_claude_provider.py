"""Smoke tests for the Claude provider adapter.

Confirms the provider registers cleanly and implements the full protocol
surface. Does NOT exercise the actual OAuth flow or usage API — those
require live state.
"""

from __future__ import annotations

import json


def test_claude_provider_loads_with_expected_identity():
    from swap.providers.claude import CLAUDE

    assert CLAUDE.name == "claude"
    assert CLAUDE.display_name == "Claude"
    assert CLAUDE.cli_prog == "claude-swap"
    assert CLAUDE.quiet_env_var == "CLAUDE_SWAP_QUIET"


def test_claude_provider_implements_protocol_surface():
    """Every callable on the Provider must be wired by the claude adapter."""
    from swap.providers.claude import CLAUDE

    required = [
        "swap_root",
        "read_live_credentials",
        "clear_live_credentials",
        "credentials_identity",
        "credentials_fingerprint",
        "snapshot_to_slot",
        "restore_from_slot",
        "start_login",
        "probe_active_slot",
        "probe_slot_isolated",
        "refresh_usage_from_rollouts",
        "load_persisted_usage",
        "drop_slot_usage",
        "merge_into_persisted_usage",
        "effective_used_percent",
        "is_exhausted",
        "find_binary",
        "binary_env",
    ]
    for name in required:
        attr = getattr(CLAUDE, name)
        assert callable(attr), f"{name} must be callable on CLAUDE"


def test_claude_swap_root_uses_per_provider_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SWAP_ROOT", str(tmp_path))
    from swap.providers.claude import CLAUDE

    assert CLAUDE.swap_root() == tmp_path


def test_credentials_identity_from_oauth_account_block():
    """Identity is pulled from ``oauthAccount``, embedded into the creds dict."""
    from swap.providers.claude import auth

    creds = {
        "claudeAiOauth": {
            "accessToken": "sk-ant-oat01-xxx",
            "refreshToken": "sk-ant-ort01-yyy",
            "subscriptionType": "max",
        },
        "_oauth_account": {
            "emailAddress": "alex@example.com",
            "organizationUuid": "abc-123",
            "accountUuid": "user-7",
        },
    }
    email, account_id, plan = auth.credentials_identity(creds)
    assert email == "alex@example.com"
    assert account_id == "abc-123"
    assert plan == "max"


def test_credentials_fingerprint_prefers_account_uuid():
    from swap.providers.claude import auth

    creds = {"_oauth_account": {"accountUuid": "user-7"}}
    assert auth.credentials_fingerprint(creds) == "claude:user-7"


def test_credentials_fingerprint_falls_back_to_token_hash():
    from swap.providers.claude import auth

    creds = {
        "claudeAiOauth": {"refreshToken": "sk-ant-ort01-aaaaaaaaaaaaaaaaaa"},
        "_oauth_account": {},
    }
    fp = auth.credentials_fingerprint(creds)
    assert fp.startswith("claude:tok:")
    assert len(fp) > len("claude:tok:")


def test_snapshot_and_restore_roundtrip(tmp_path, monkeypatch):
    """A full snapshot writes credentials + oauthAccount; restore puts both back."""
    from swap.providers.claude import auth

    # Steer the live keychain at the file backend so the test runs anywhere.
    monkeypatch.setattr(auth, "_is_macos", lambda: False)
    fake_home = tmp_path / "home"
    monkeypatch.setattr(auth, "HOME", fake_home)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    fake_home.mkdir()

    # Live creds blob + matching .claude.json oauthAccount.
    live_creds = json.dumps({"claudeAiOauth": {"accessToken": "tok"}})
    (fake_home / ".claude").mkdir()
    (fake_home / ".claude" / ".credentials.json").write_text(live_creds)
    (fake_home / ".claude.json").write_text(
        json.dumps(
            {
                "projects": {"/tmp": {"trusted": True}},
                "oauthAccount": {
                    "emailAddress": "alex@example.com",
                    "organizationUuid": "abc-123",
                    "accountUuid": "user-7",
                },
            }
        )
    )

    slot_dir = tmp_path / "slot1"
    auth.snapshot_to_slot(slot_dir)
    assert (slot_dir / "credentials.json").read_text() == live_creds
    snapped_oauth = json.loads((slot_dir / "oauth_account.json").read_text())
    assert snapped_oauth["emailAddress"] == "alex@example.com"

    # Mutate live state to prove restore writes both pieces back.
    (fake_home / ".claude" / ".credentials.json").write_text("{}")
    (fake_home / ".claude.json").write_text(
        json.dumps(
            {
                "projects": {"/tmp": {"trusted": True}},
                "oauthAccount": {"emailAddress": "other@example.com"},
            }
        )
    )

    auth.restore_from_slot(slot_dir)
    assert (fake_home / ".claude" / ".credentials.json").read_text() == live_creds
    after = json.loads((fake_home / ".claude.json").read_text())
    assert after["oauthAccount"]["emailAddress"] == "alex@example.com"
    # Restore must preserve other keys.
    assert after["projects"] == {"/tmp": {"trusted": True}}


def test_binary_env_drops_anthropic_api_key(monkeypatch):
    from swap.providers.claude import binary

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api-xxx")
    env = binary.binary_env()
    assert "ANTHROPIC_API_KEY" not in env


def test_cs_launcher_is_not_implemented_in_v01(capsys):
    from swap.providers.claude.cli import cs_main

    rc = cs_main([])
    captured = capsys.readouterr()
    assert rc == 1
    assert "not implemented" in captured.err


def test_claude_swap_cli_help_lists_generic_commands(capsys):
    from swap.core.cli_base import build_parser
    from swap.providers.claude import CLAUDE

    parser = build_parser(CLAUDE)
    help_text = parser.format_help()
    for cmd in (
        "add",
        "remove",
        "list",
        "status",
        "switch",
        "reauth",
        "reconnect",
        "stash",
        "onboard",
        "verify",
        "usage",
        "seed",
        "anchor",
        "policy",
        "launch",
        "purge",
    ):
        assert cmd in help_text, f"Missing subcommand {cmd!r} in --help"


def test_usage_is_exhausted_treats_100_percent_as_exhausted():
    from swap.providers.claude import usage

    rec = {"primary": {"used_percent": 100.0}, "secondary": {"used_percent": 0.0}}
    assert usage.is_exhausted(rec)
    assert not usage.is_exhausted({"primary": {"used_percent": 50.0}})
