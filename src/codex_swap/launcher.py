"""Smart-launch: pick lowest-effective-usage slot, switch in, exec codex.

The picker reads the persisted usage store (durable, never wiped on rescan),
applies `resets_at`-based decay so window resets are reflected without
re-measurement, and rotates to the slot with the lowest effective usage.

Seeding is NOT done here. It's an explicit step (`codex-swap seed`, or the
auto-seed at the end of `codex-swap onboard` / `codex-swap add`). Once a
slot has a record, decay keeps it accurate across window resets.
"""

from __future__ import annotations

import os
import sys

from .codex import find_real_codex
from .slots import current_slot, load_sequence, switch_to
from .usage import effective_used_percent, is_exhausted, refresh_from_rollouts

# Either rate-limit window at or above this percent makes the slot a
# "near cap" candidate — ranked below an unknown slot so cx is willing
# to rotate to a slot that hasn't been measured yet.
NEAR_CAP_PERCENT = 80.0


def _slot_score(slot: str, usage: dict) -> tuple[int, float, float, int]:
    """Sort key for the picker — lower is better.

    Bucket 0 — known and healthy (both windows below NEAR_CAP_PERCENT after
               decay). Preferred.
    Bucket 1 — no usage record yet (assume fresh; bias toward learning).
    Bucket 2 — known and at/above NEAR_CAP_PERCENT after decay, OR explicitly
               flagged exhausted by the most recent rollout. Last resort.
    """
    info = usage.get(slot)
    if not isinstance(info, dict):
        return (1, 0.0, 0.0, int(slot))
    if is_exhausted(info):
        return (2, 100.0, 100.0, int(slot))
    pri_eff = effective_used_percent(info.get("primary"))
    sec_eff = effective_used_percent(info.get("secondary"))
    pri = float(pri_eff) if pri_eff is not None else 101.0
    sec = float(sec_eff) if sec_eff is not None else 101.0
    bucket = 2 if (pri >= NEAR_CAP_PERCENT or sec >= NEAR_CAP_PERCENT) else 0
    return (bucket, pri, sec, int(slot))


def _choose(seq: dict, usage: dict) -> str | None:
    sequence = [str(s) for s in seq.get("sequence", [])]
    if not sequence:
        return None
    return min(sequence, key=lambda s: _slot_score(s, usage))


def _label(seq: dict, slot: str, usage: dict) -> str:
    acc = seq.get("accounts", {}).get(slot, {})
    parts = [acc.get("email") or f"slot {slot}"]
    info = usage.get(slot, {}) if isinstance(usage, dict) else None
    primary = info.get("primary") if isinstance(info, dict) and isinstance(info.get("primary"), dict) else None
    secondary = info.get("secondary") if isinstance(info, dict) and isinstance(info.get("secondary"), dict) else None
    pri_eff = effective_used_percent(primary)
    sec_eff = effective_used_percent(secondary)
    if pri_eff is not None:
        parts.append(f"5h {pri_eff:.0f}%")
    if sec_eff is not None:
        parts.append(f"7d {sec_eff:.0f}%")
    if is_exhausted(info):
        parts.append("limit reached")
    elif pri_eff is None and sec_eff is None:
        parts.append("usage unknown")
    return ", ".join(parts)


def _unknown_slots(seq: dict, usage: dict) -> list[str]:
    return sorted(
        (s for s in seq.get("accounts", {}) if s not in usage),
        key=lambda s: int(s),
    )


def maybe_switch(skip_auto: bool = False, pinned_slot: str | None = None) -> None:
    if skip_auto and not pinned_slot:
        return
    seq = load_sequence()
    if not seq or len(seq.get("accounts", {})) < 2:
        return

    # Cheap rollout-scan merges any new findings into the persisted store.
    # Slots without a fresh rollout keep their existing record (with decay).
    usage = refresh_from_rollouts()

    cur = current_slot(seq)
    target = str(pinned_slot) if pinned_slot else _choose(seq, usage)
    if not target:
        return
    if target not in seq.get("accounts", {}):
        sys.stderr.write(f"codex-swap: slot {target} not configured\n")
        return

    if target != cur:
        rc, msg = switch_to(target)
        if rc != 0:
            sys.stderr.write(f"cx: switch failed: {msg}\n")
            return
        sys.stderr.write(f"cx: using slot {target} ({_label(seq, target, usage)})\n")

    # If any slot is still unmeasured, point the user at the explicit seed
    # command. We do not auto-probe here — seeding is a one-time setup step.
    unknown = _unknown_slots(seq, usage)
    if unknown and os.environ.get("CODEX_SWAP_QUIET") != "1":
        sys.stderr.write(
            f"cx: tip — slot(s) {','.join(unknown)} have no usage data yet. "
            f"Run `codex-swap seed` once to measure them in parallel.\n"
        )


def launch(args: list[str], skip_auto: bool = False, pinned_slot: str | None = None) -> None:
    """Switch into the right slot, then exec codex with `args`."""
    maybe_switch(skip_auto=skip_auto, pinned_slot=pinned_slot)
    target = find_real_codex()
    os.execvp(target, [target] + args)
