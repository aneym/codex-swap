"""Provider protocol.

A Provider is a frozen dataclass of callables that the provider-agnostic core
uses to do everything specific to a CLI/account ecosystem (Codex, Claude Code,
future entrants). The core never imports from a provider module; it composes
behavior by calling these callables.

Naming convention: every callable here is provider-shaped, never global state.
A Provider is the thing you'd register a new vendor by writing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ExtraCommand:
    """A provider-specific subcommand mounted onto its CLI builder.

    The core CLI exposes generic commands (add/list/switch/...). A provider may
    bolt extra commands on (e.g. `codex-swap seed`). They are *not* mounted on
    other providers' CLIs.
    """

    name: str
    help: str
    configure: Callable[[Any], None]
    """`(subparser) -> None` — configures argparse args; must call set_defaults(func=...)."""


@dataclass(frozen=True)
class Provider:
    """A pluggable account-switch backend.

    Most callables are total — they always return something (possibly a sentinel
    like `None`) rather than raising. Login / refresh / probe may print to the
    user.
    """

    name: str
    """short id, e.g. 'codex'. Used in paths (`~/.swap/<name>/`) and the CLI prog."""

    display_name: str
    """human-readable name, e.g. 'Codex'."""

    cli_prog: str
    """argparse prog name, e.g. 'codex-swap'."""

    cli_description: str
    """one-line CLI description used in `--help`."""

    swap_root: Callable[[], Path]
    """Per-provider data root, e.g. `~/.swap/codex/`."""

    # --- credentials / live state ---
    read_live_credentials: Callable[[], dict | None]
    """Read what's currently live for this provider (e.g. `~/.codex/auth.json`)."""

    clear_live_credentials: Callable[[], None]
    """Remove the live creds file. NEVER call provider-side logout from here."""

    credentials_identity: Callable[[dict], tuple]
    """Return (email, account_id, plan_type) from a parsed credentials blob."""

    credentials_fingerprint: Callable[[dict], str]
    """Stable, non-secret identifier for accounts without an account_id."""

    # --- slot snapshot I/O ---
    snapshot_to_slot: Callable[[Path], None]
    """Copy the live creds into `<slot_dir>/`. May write multiple files."""

    restore_from_slot: Callable[[Path], None]
    """Copy `<slot_dir>/` to the live location. Inverse of snapshot_to_slot."""

    # --- OAuth / login ---
    start_login: Callable[[], int]
    """Spawn the provider's interactive login flow. Returns the rc of that process."""

    # --- health probe ---
    probe_active_slot: Callable[..., tuple[str, str]]
    """Probe the current live slot. Returns (status, detail).

    Status is 'ok' / 'rate_limited' / 'broken' / 'error'. Takes an optional
    `timeout` keyword; signature is left loose so providers can extend.
    """

    probe_slot_isolated: Callable[..., tuple]
    """Probe a slot in an isolated home dir (parallel-safe).

    Signature: `(slot, snapshot_path, real_binary, timeout) -> (slot, status, detail, record_or_none)`.
    The returned `record` is the usage shape ({primary, secondary, plan_type, scanned_at, source, source_path}).
    """

    # --- usage telemetry (launcher policy + `usage` command) ---
    refresh_usage_from_rollouts: Callable[[], dict]
    """Cheap rollout scan; merges new findings into persisted store; returns full store."""

    load_persisted_usage: Callable[[], dict]
    """Read the persisted usage store as-is (no rescan)."""

    drop_slot_usage: Callable[[str], None]
    """Remove a single slot's usage record (called after `remove`)."""

    merge_into_persisted_usage: Callable[[dict], dict]
    """Merge per-slot updates into the persisted store; higher scanned_at wins."""

    effective_used_percent: Callable[..., float | None]
    """`(window: dict | None) -> float | None`. Apply resets_at decay to a window."""

    is_exhausted: Callable[[dict | None], bool]
    """True if a slot's persisted record is flagged exhausted."""

    # --- binary exec ---
    find_binary: Callable[[], str]
    """Locate the provider's CLI binary on PATH."""

    binary_env: Callable[[], dict]
    """Env dict to pass when spawning the provider binary (e.g. drop conflicting keys)."""

    # --- launcher labels ---
    near_cap_percent: float = 80.0
    """Threshold above which a slot is considered near-cap (last-resort bucket)."""

    # --- optional provider-specific CLI extensions ---
    extra_commands: tuple = field(default_factory=tuple)
    """`tuple[ExtraCommand, ...]` of provider-specific subcommands."""

    # --- onboarding / launcher text ---
    onboard_label: str = "accounts"
    """Plural label used by the onboarding prompt (e.g. 'Codex accounts')."""

    quiet_env_var: str = "SWAP_QUIET"
    """Env var that, when set to '1', suppresses launcher tips."""
