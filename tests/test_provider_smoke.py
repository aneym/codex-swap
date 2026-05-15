"""Smoke tests that pin the new `swap.*` surface and the compat shim."""

from __future__ import annotations


def test_codex_provider_loads_with_expected_identity():
    from swap.providers.codex import CODEX

    assert CODEX.name == "codex"
    assert CODEX.display_name == "Codex"
    assert CODEX.cli_prog == "codex-swap"


def test_codex_provider_implements_protocol_surface():
    """Every callable on the Provider must be wired by the codex adapter."""
    from swap.providers.codex import CODEX

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
        attr = getattr(CODEX, name)
        assert callable(attr), f"{name} must be callable on CODEX"


def test_codex_swap_compat_shim_still_imports():
    """Callers importing `codex_swap.*` keep working."""
    import codex_swap
    from codex_swap import auth, cli, codex, launcher, paths, policy, slots, usage

    assert codex_swap.__version__
    # Sentinel module-level names that tests/callers expect to exist.
    assert hasattr(cli, "main")
    assert hasattr(cli, "cx_main")
    assert hasattr(cli, "launch")
    assert hasattr(cli, "refresh_from_rollouts")
    assert hasattr(launcher, "_choose")
    assert hasattr(launcher, "NEAR_CAP_PERCENT")
    assert hasattr(auth, "auth_identity")
    assert hasattr(codex, "find_real_codex")
    assert hasattr(codex, "codex_env")
    assert hasattr(slots, "add_auth_file")
    assert hasattr(slots, "_resolve")
    assert hasattr(usage, "effective_used_percent")
    assert hasattr(usage, "USAGE_CACHE")
    assert hasattr(policy, "load_policy")
    assert hasattr(paths, "SWAP_ROOT")


def test_codex_swap_cli_module_runs_help(capsys):
    """The legacy CLI entrypoint still parses; help mentions every command."""
    from codex_swap.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()
    for cmd in (
        "add", "import-profile", "remove", "list", "status", "switch",
        "reauth", "reconnect", "stash", "onboard", "verify", "usage",
        "seed", "anchor", "policy", "launch", "purge",
    ):
        assert cmd in help_text, f"Missing subcommand {cmd!r} in --help"
