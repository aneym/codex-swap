"""Smart-launch: pick lowest-effective-usage slot, switch in, exec the provider binary.

Bucketing logic is provider-agnostic; the provider supplies usage refresh,
effective_used_percent decay, exhaustion detection, binary discovery.
"""

from __future__ import annotations

import os
import sys

from .policy import (
    DEFAULT_SPILLOVER_PRIMARY_PERCENT,
    DEFAULT_SPILLOVER_SECONDARY_PERCENT,
    load_policy,
    policy_enabled,
)
from .provider import Provider
from .sequence import load_sequence
from .slots import current_slot, switch_to


def _slot_score(
    provider: Provider,
    slot: str,
    usage: dict,
) -> tuple[int, float, float, int]:
    """Sort key for the picker — lower is better.

    Bucket 0 — known + healthy (both windows below near_cap_percent after decay).
    Bucket 1 — no record yet (bias toward learning).
    Bucket 2 — known and at/above near_cap_percent, OR flagged exhausted.
    """
    info = usage.get(slot)
    if not isinstance(info, dict):
        return (1, 0.0, 0.0, int(slot))
    if provider.is_exhausted(info):
        return (2, 100.0, 100.0, int(slot))
    pri_eff = provider.effective_used_percent(info.get("primary"))
    sec_eff = provider.effective_used_percent(info.get("secondary"))
    pri = float(pri_eff) if pri_eff is not None else 101.0
    sec = float(sec_eff) if sec_eff is not None else 101.0
    near = provider.near_cap_percent
    bucket = 2 if (pri >= near or sec >= near) else 0
    return (bucket, pri, sec, int(slot))


def _policy_score(
    provider: Provider,
    slot: str,
    usage: dict,
    reserve_slots: set[str],
) -> tuple[int, float, float, int]:
    bucket, pri, sec, slot_num = _slot_score(provider, slot, usage)
    exhausted = provider.is_exhausted(usage.get(slot))
    if slot not in reserve_slots:
        if exhausted:
            return (6, pri, sec, slot_num)
        return (bucket if bucket < 2 else 4, pri, sec, slot_num)
    if exhausted:
        return (7, pri, sec, slot_num)
    if bucket == 0:
        return (2, pri, sec, slot_num)
    if bucket == 1:
        return (3, pri, sec, slot_num)
    return (5, pri, sec, slot_num)


def _primary_is_usable(provider: Provider, slot: str, usage: dict, policy: dict) -> bool:
    info = usage.get(slot)
    if provider.is_exhausted(info):
        return False
    if not isinstance(info, dict):
        return True

    pri = provider.effective_used_percent(info.get("primary"))
    sec = provider.effective_used_percent(info.get("secondary"))
    pri = 0.0 if pri is None else float(pri)
    sec = 0.0 if sec is None else float(sec)
    pri_limit = float(policy.get("spillover_primary_percent") or DEFAULT_SPILLOVER_PRIMARY_PERCENT)
    sec_limit = float(policy.get("spillover_secondary_percent") or DEFAULT_SPILLOVER_SECONDARY_PERCENT)
    return pri < pri_limit and sec < sec_limit


def choose(provider: Provider, seq: dict, usage: dict, policy: dict | None = None) -> str | None:
    sequence = [str(s) for s in seq.get("sequence", [])]
    if not sequence:
        return None
    if not policy_enabled(policy):
        return min(sequence, key=lambda s: _slot_score(provider, s, usage))

    primary = str(policy.get("primary_slot") or "")
    if primary in sequence and _primary_is_usable(provider, primary, usage, policy):
        return primary

    reserves = {str(s) for s in policy.get("reserve_slots", [])}
    return min(sequence, key=lambda s: _policy_score(provider, s, usage, reserves))


def _label(provider: Provider, seq: dict, slot: str, usage: dict) -> str:
    acc = seq.get("accounts", {}).get(slot, {})
    parts = [acc.get("email") or f"slot {slot}"]
    info = usage.get(slot, {}) if isinstance(usage, dict) else None
    primary = (
        info.get("primary") if isinstance(info, dict) and isinstance(info.get("primary"), dict) else None
    )
    secondary = (
        info.get("secondary") if isinstance(info, dict) and isinstance(info.get("secondary"), dict) else None
    )
    pri_eff = provider.effective_used_percent(primary)
    sec_eff = provider.effective_used_percent(secondary)
    if pri_eff is not None:
        parts.append(f"5h {pri_eff:.0f}%")
    if sec_eff is not None:
        parts.append(f"7d {sec_eff:.0f}%")
    if provider.is_exhausted(info):
        parts.append("limit reached")
    elif pri_eff is None and sec_eff is None:
        parts.append("usage unknown")
    return ", ".join(parts)


def _unknown_slots(seq: dict, usage: dict) -> list[str]:
    return sorted(
        (s for s in seq.get("accounts", {}) if s not in usage),
        key=lambda s: int(s),
    )


def maybe_switch(
    provider: Provider,
    paths: dict,
    *,
    skip_auto: bool = False,
    pinned_slot: str | None = None,
) -> None:
    if skip_auto and not pinned_slot:
        return
    seq = load_sequence(paths["sequence"])
    if not seq or len(seq.get("accounts", {})) < 2:
        return

    # Cheap rollout-scan merges any new findings into the persisted store.
    usage = provider.refresh_usage_from_rollouts()
    policy = load_policy(paths["policy"])

    cur = current_slot(provider, paths, seq)
    target = str(pinned_slot) if pinned_slot else choose(provider, seq, usage, policy)
    if not target:
        return
    if target not in seq.get("accounts", {}):
        sys.stderr.write(f"{provider.cli_prog}: slot {target} not configured\n")
        return

    if target != cur:
        rc, msg = switch_to(provider, paths, target)
        if rc != 0:
            sys.stderr.write(f"cx: switch failed: {msg}\n")
            return
        sys.stderr.write(f"cx: using slot {target} ({_label(provider, seq, target, usage)})\n")

    unknown = _unknown_slots(seq, usage)
    if unknown and os.environ.get(provider.quiet_env_var) != "1":
        sys.stderr.write(
            f"cx: tip — slot(s) {','.join(unknown)} have no usage data yet. "
            f"Run `{provider.cli_prog} seed` once to measure them in parallel.\n"
        )


def launch(
    provider: Provider,
    paths: dict,
    args: list[str],
    *,
    skip_auto: bool = False,
    pinned_slot: str | None = None,
) -> None:
    """Switch into the right slot, then exec the provider's binary with `args`."""
    maybe_switch(provider, paths, skip_auto=skip_auto, pinned_slot=pinned_slot)
    target = provider.find_binary()
    os.execvp(target, [target] + args)
