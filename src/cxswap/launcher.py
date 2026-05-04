"""Smart-launch: pick lowest-usage slot, switch in, exec codex."""

from __future__ import annotations

import os
import sys

from .codex import find_real_codex
from .paths import USAGE_CACHE_TTL_SECONDS
from .slots import current_slot, load_sequence, switch_to
from .usage import cached, refresh_cache


def _slot_score(slot: str, usage: dict) -> tuple[int, float, float, int]:
    info = usage.get(slot)
    if not isinstance(info, dict):
        return (1, 101.0, 101.0, int(slot))
    primary = info.get("primary") if isinstance(info.get("primary"), dict) else {}
    secondary = info.get("secondary") if isinstance(info.get("secondary"), dict) else {}
    pri = float(primary.get("used_percent", 101.0)) if primary else 101.0
    sec = float(secondary.get("used_percent", 101.0)) if secondary else 101.0
    return (0, pri, sec, int(slot))


def _choose(seq: dict, usage: dict) -> str | None:
    sequence = [str(s) for s in seq.get("sequence", [])]
    if not sequence:
        return None
    return min(sequence, key=lambda s: _slot_score(s, usage))


def _label(seq: dict, slot: str, usage: dict) -> str:
    acc = seq.get("accounts", {}).get(slot, {})
    parts = [acc.get("email") or f"slot {slot}"]
    info = usage.get(slot, {}) if isinstance(usage, dict) else {}
    primary = info.get("primary") if isinstance(info.get("primary"), dict) else None
    secondary = info.get("secondary") if isinstance(info.get("secondary"), dict) else None
    if primary and "used_percent" in primary:
        parts.append(f"5h {float(primary['used_percent']):.0f}%")
    if secondary and "used_percent" in secondary:
        parts.append(f"7d {float(secondary['used_percent']):.0f}%")
    return ", ".join(parts)


def maybe_switch(skip_auto: bool = False, pinned_slot: str | None = None) -> None:
    if skip_auto and not pinned_slot:
        return
    seq = load_sequence()
    if not seq or len(seq.get("accounts", {})) < 2:
        return

    usage = cached(USAGE_CACHE_TTL_SECONDS)
    if not usage:
        usage = refresh_cache().get("data", {})

    cur = current_slot(seq)
    target = str(pinned_slot) if pinned_slot else _choose(seq, usage)
    if not target or target == cur:
        return
    if target not in seq.get("accounts", {}):
        sys.stderr.write(f"cxswap: slot {target} not configured\n")
        return

    rc, msg = switch_to(target)
    if rc == 0:
        sys.stderr.write(f"cx: using slot {target} ({_label(seq, target, usage)})\n")
    else:
        sys.stderr.write(f"cx: switch failed: {msg}\n")


def launch(args: list[str], skip_auto: bool = False, pinned_slot: str | None = None) -> None:
    """Switch into the right slot, then exec codex with `args`."""
    maybe_switch(skip_auto=skip_auto, pinned_slot=pinned_slot)
    target = find_real_codex()
    os.execvp(target, [target] + args)
