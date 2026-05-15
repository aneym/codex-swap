"""Codex provider adapter — binds the Codex CLI surface to the core protocol."""

from __future__ import annotations

from ...core.paths import provider_root
from ...core.provider import Provider
from . import auth as _auth
from . import binary as _binary
from . import oauth as _oauth
from . import usage as _usage


def _swap_root():
    return provider_root("codex")


CODEX = Provider(
    name="codex",
    display_name="Codex",
    cli_prog="codex-swap",
    cli_description="Multi-account switcher for the OpenAI Codex CLI.",
    swap_root=_swap_root,
    # credentials
    read_live_credentials=_auth.current_auth,
    clear_live_credentials=_auth.clear_live_credentials,
    credentials_identity=_auth.auth_identity,
    credentials_fingerprint=_auth.auth_fingerprint,
    # slot snapshot
    snapshot_to_slot=_auth.snapshot_to_slot,
    restore_from_slot=_auth.restore_from_slot,
    # oauth / login
    start_login=_oauth.start_login,
    # probes
    probe_active_slot=_oauth.probe_active_slot,
    probe_slot_isolated=_oauth.probe_slot_isolated,
    # usage telemetry
    refresh_usage_from_rollouts=_usage.refresh_from_rollouts,
    load_persisted_usage=_usage.load_persisted,
    drop_slot_usage=_usage.drop_slot_record,
    merge_into_persisted_usage=_usage.merge_into_persisted,
    effective_used_percent=_usage.effective_used_percent,
    is_exhausted=_usage.is_exhausted,
    # binary
    find_binary=_binary.find_binary,
    binary_env=_binary.binary_env,
    # launcher tuning
    near_cap_percent=80.0,
    onboard_label="Codex accounts",
    quiet_env_var="CODEX_SWAP_QUIET",
)

__all__ = ["CODEX"]
