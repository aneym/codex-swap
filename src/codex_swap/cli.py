"""argparse front-end for codex-swap."""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
import time
from pathlib import Path

from . import __version__
from .auth import auth_fingerprint, auth_identity, current_auth
from .launcher import launch
from .onboard import onboard
from .paths import AUTH_PATH
from .slots import (
    add_auth_file,
    add_current,
    current_slot,
    load_sequence,
    reauth,
    reconnect_broken,
    remove,
    resolve_slot,
    rotate,
    seed_slots,
    stash_active,
    switch_to,
    verify_all,
)
from .usage import effective_used_percent, is_exhausted, load_persisted, refresh_from_rollouts


def _fmt_pct(v) -> str:
    try:
        return f"{float(v):.0f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_resets(ts) -> str:
    try:
        delta = int(ts) - int(time.time())
    except (TypeError, ValueError):
        return ""
    if delta <= 0:
        return "(reset)"
    if delta < 3600:
        return f"in {delta // 60}m"
    if delta < 86400:
        return f"in {delta // 3600}h"
    return f"in {delta // 86400}d"


def _fmt_resets_at(ts) -> str:
    """Long-form reset string: 'resets Thu 6:35pm, in 4h' or 'already reset'."""
    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        return ""
    delta = ts_int - int(time.time())
    if delta <= 0:
        return "already reset"
    when = (
        _dt.datetime.fromtimestamp(ts_int)
        .strftime("%a %-I:%M%p")
        .replace("AM", "am")
        .replace("PM", "pm")
    )
    if delta < 3600:
        rel = f"in {delta // 60}m"
    elif delta < 86400:
        rel = f"in {delta // 3600}h"
    else:
        rel = f"in {delta // 86400}d"
    return f"resets {when}, {rel}"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CODEX_SWAP_FORCE_COLOR"):
        return True
    return bool(sys.stdout.isatty())


class _Style:
    """Minimal ANSI styling with TTY detection — no third-party deps."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled or not text:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, t: str) -> str:
        return self._wrap("1", t)

    def dim(self, t: str) -> str:
        return self._wrap("2", t)

    def green(self, t: str) -> str:
        return self._wrap("32", t)

    def yellow(self, t: str) -> str:
        return self._wrap("33", t)

    def red(self, t: str) -> str:
        return self._wrap("31", t)

    def cyan(self, t: str) -> str:
        return self._wrap("36", t)

    def bold_red(self, t: str) -> str:
        return self._wrap("1;31", t)


def _color_pct(style: _Style, pct: float | None, text: str) -> str:
    """Severity-color a percent string. None and 0 render dim."""
    if pct is None:
        return style.dim(text)
    if pct <= 0:
        return style.dim(text)
    if pct < 50:
        return style.green(text)
    if pct < 80:
        return style.yellow(text)
    return style.red(text)


def _account_label(acc: dict) -> str:
    return acc.get("email") or acc.get("label") or acc.get("account_id") or acc.get("auth_mode") or ""


def cmd_add(args) -> int:
    rc, msg = add_current()
    print(msg)
    return rc


def cmd_import_profile(args) -> int:
    src = Path(args.profile).expanduser()
    label = args.label or src.name
    if not src.is_absolute() and "/" not in args.profile:
        src = Path.home() / ".codex-profiles" / args.profile
    if src.is_dir():
        src = src / "auth.json"
    rc, msg = add_auth_file(src, source_label=label)
    print(msg)
    return rc


def cmd_remove(args) -> int:
    rc, msg = remove(args.target)
    print(msg)
    return rc


def cmd_list(args) -> int:
    seq = load_sequence()
    if not seq["accounts"]:
        print("No accounts configured. Run `codex-swap onboard 3` to set them up.")
        return 0
    usage = {} if args.no_usage else refresh_from_rollouts()
    active = current_slot(seq)
    print(f"{'':2} {'slot':<5} {'email':<35} {'plan':<8} {'5h':>6} {'7d':>6} {'resets':>10}  notes")
    for slot in sorted(seq["accounts"], key=lambda s: int(s)):
        acc = seq["accounts"][slot]
        marker = "*" if slot == active else " "
        info = usage.get(slot, {}) if isinstance(usage, dict) else {}
        primary = info.get("primary") if isinstance(info.get("primary"), dict) else None
        secondary = info.get("secondary") if isinstance(info.get("secondary"), dict) else None
        if is_exhausted(info):
            pri_pct = "100%"
            sec_pct = "100%"
            note = "limit reached"
        else:
            pri_pct = _fmt_pct(effective_used_percent(primary))
            sec_pct = _fmt_pct(effective_used_percent(secondary))
            note = ""
        print(
            f" {marker} {slot:<5} {_account_label(acc)[:34]:<35} "
            f"{(acc.get('plan_type') or '')[:7]:<8} "
            f"{pri_pct:>6} "
            f"{sec_pct:>6} "
            f"{_fmt_resets(primary.get('resets_at') if primary else None):>10}  {note}"
        )
    return 0


def cmd_status(args) -> int:
    auth = current_auth()
    if not auth:
        print(f"No auth.json at {AUTH_PATH} (logged out).")
        return 0
    email, account_id, plan_type = auth_identity(auth)
    fingerprint = auth_fingerprint(auth)
    seq = load_sequence()
    slot = current_slot(seq)
    if slot:
        acc = seq["accounts"].get(slot, {})
        print(f"Active: slot {slot} — {_account_label(acc)} ({plan_type or acc.get('auth_mode') or 'unknown'})")
    else:
        label = email or auth.get("auth_mode", "") or fingerprint
        suffix = f", account_id={account_id[:12]}…" if account_id else ""
        print(f"Active: unmanaged — {label} ({plan_type or auth.get('auth_mode', 'unknown')}){suffix}")
    return 0


def cmd_switch(args) -> int:
    if args.target:
        rc, msg = switch_to(args.target)
    else:
        rc, msg = rotate()
    print(msg)
    return rc


def cmd_reauth(args) -> int:
    rc, msg = reauth(args.target)
    print(msg)
    return rc


def cmd_reconnect(args) -> int:
    rc, fixed, still_broken = reconnect_broken()
    if not fixed and not still_broken:
        print("All slots are healthy. Nothing to reconnect.")
        return 0
    print()
    if fixed:
        print(f"Re-minted: {', '.join(fixed)}")
    if still_broken:
        print(f"Still broken: {', '.join(still_broken)} (run `codex-swap reauth <slot>` to retry)")
    return rc


def cmd_stash(args) -> int:
    stash_active(load_sequence())
    return 0


def cmd_onboard(args) -> int:
    return onboard(args.count)


def cmd_verify(args) -> int:
    results = verify_all()
    if not results:
        print("No slots to verify.")
        return 0
    seq = load_sequence()
    print(f"{'slot':<5} {'email':<32} {'status':<14}  detail")
    broken = []
    rate_limited = []
    errors = []
    for slot, status, detail in results:
        if status == "broken":
            broken.append(slot)
        elif status == "rate_limited":
            rate_limited.append(slot)
        elif status == "error":
            errors.append(slot)
        email = (seq["accounts"].get(slot, {}).get("email") or "")[:31]
        print(f"{slot:<5} {email:<32} {status:<14}  {detail[:80]}")
    notes = []
    if broken:
        notes.append(
            f"{len(broken)} slot(s) need re-minting (auth dead). "
            f"Run: codex-swap reauth {' / '.join(broken)}"
        )
    if rate_limited:
        notes.append(
            f"{len(rate_limited)} slot(s) hit their usage cap — auth is fine, "
            f"they'll auto-refresh when the window resets."
        )
    if errors:
        notes.append(
            f"{len(errors)} slot probe(s) failed for a non-auth reason. "
            "Auth was not marked broken; inspect the detail above."
        )
    if notes:
        print()
        for n in notes:
            print(n)
    return 1 if broken or errors else 0


def cmd_usage(args) -> int:
    data = refresh_from_rollouts()
    if args.json:
        import json as _json
        print(_json.dumps({"timestamp": time.time(), "data": data}, indent=2))
        return 0
    if not data:
        print("(no usage data yet — run `codex-swap seed` to populate)")
        return 0
    style = _Style(_supports_color())
    rows = sorted(data.items(), key=lambda kv: int(kv[0]))
    for idx, (slot, info) in enumerate(rows):
        if idx > 0:
            print()
        _print_usage_block(style, slot, info)
    return 0


def _print_usage_block(style: _Style, slot: str, info: dict) -> None:
    primary = info.get("primary") if isinstance(info.get("primary"), dict) else None
    secondary = info.get("secondary") if isinstance(info.get("secondary"), dict) else None
    source = info.get("source") or "?"
    plan = info.get("plan_type") or "—"
    exhausted = is_exhausted(info)

    sep = style.dim("·")
    header_parts = [style.bold(f"slot {slot}"), sep, plan, sep, style.dim(source)]
    if exhausted:
        header_parts.append("  ")
        header_parts.append(style.bold_red("⚠ LIMIT REACHED"))
        header_parts.append(style.dim("—"))
        header_parts.append(f"run {style.bold('`codex-swap seed`')} to re-check")
    print(" ".join(header_parts))

    for label, win in (("5h", primary), ("7d", secondary)):
        if exhausted:
            pct_val: float | None = 100.0
        else:
            pct_val = effective_used_percent(win)
        pct_text = f"{_fmt_pct(pct_val):>4}"
        pct_colored = _color_pct(style, pct_val, pct_text)

        resets_at = win.get("resets_at") if isinstance(win, dict) else None
        reset_raw = _fmt_resets_at(resets_at)
        if reset_raw == "already reset":
            reset_part = style.cyan(reset_raw)
        elif reset_raw:
            reset_part = style.dim(reset_raw)
        else:
            reset_part = ""

        line = f"  {style.dim(label)}  {pct_colored}"
        if reset_part:
            line += f"   {reset_part}"
        print(line)


def cmd_seed(args) -> int:
    seq = load_sequence()
    if not seq["accounts"]:
        print("No slots configured. Run `codex-swap onboard 3` first.")
        return 1
    if args.targets:
        slots = []
        for t in args.targets:
            slot = resolve_slot(seq, t)
            if not slot:
                sys.stderr.write(f"codex-swap: unknown slot '{t}'\n")
                return 1
            slots.append(slot)
    elif args.all:
        slots = sorted(seq["accounts"], key=int)
    else:
        persisted = load_persisted()
        slots = sorted([s for s in seq["accounts"] if s not in persisted], key=int)
        if not slots:
            print("All slots already have usage data. Pass slot numbers or --all to re-seed.")
            return 0

    results = seed_slots(slots, max_concurrency=args.concurrency, probe_timeout=args.timeout)
    if not results:
        print("(nothing to seed)")
        return 0
    print()
    print(f"{'slot':<5} {'email':<32} {'status':<14} detail")
    for slot, status, detail in results:
        email = (seq["accounts"].get(slot, {}).get("email") or "")[:31]
        print(f"{slot:<5} {email:<32} {status:<14} {detail[:80]}")
    failures = [r for r in results if r[1] not in ("ok",)]
    return 1 if failures else 0


def cmd_launch(args) -> int:
    launch(args.codex_args, skip_auto=args.skip_auto, pinned_slot=args.slot)
    return 0  # unreachable; launch execs


def cmd_purge(args) -> int:
    import shutil

    from .paths import SWAP_ROOT
    if not args.yes:
        sys.stderr.write(f"Refusing to delete {SWAP_ROOT} without --yes.\n")
        return 1
    if SWAP_ROOT.exists():
        shutil.rmtree(SWAP_ROOT)
        print(f"Removed {SWAP_ROOT}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codex-swap",
        description="Multi-account switcher for the OpenAI Codex CLI.",
    )
    p.add_argument("--version", action="version", version=f"codex-swap {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp_add = sub.add_parser("add", help="Save the currently logged-in account as a new slot")
    sp_add.set_defaults(func=cmd_add)

    sp_import = sub.add_parser("import-profile", help="Save an existing Codex profile/auth.json as a slot")
    sp_import.add_argument("profile", help="profile name under ~/.codex-profiles, profile dir, or auth.json path")
    sp_import.add_argument("--label", help="display label for API-key or no-email auth")
    sp_import.set_defaults(func=cmd_import_profile)

    sp_rm = sub.add_parser("remove", help="Remove a slot")
    sp_rm.add_argument("target", help="slot number, email, or account_id")
    sp_rm.set_defaults(func=cmd_remove)

    sp_list = sub.add_parser("list", help="List all slots with usage")
    sp_list.add_argument("--no-usage", action="store_true", help="Skip refreshing the usage cache")
    sp_list.set_defaults(func=cmd_list)

    sp_status = sub.add_parser("status", help="Show currently active slot")
    sp_status.set_defaults(func=cmd_status)

    sp_switch = sub.add_parser("switch", help="Switch to a slot (default: rotate to next)")
    sp_switch.add_argument("target", nargs="?", help="slot number, email, or account_id")
    sp_switch.set_defaults(func=cmd_switch)

    sp_reauth = sub.add_parser("reauth", help="Re-mint a slot via fresh codex login")
    sp_reauth.add_argument("target", help="slot number, email, or account_id")
    sp_reauth.set_defaults(func=cmd_reauth)

    sp_reconnect = sub.add_parser(
        "reconnect",
        help="Verify all slots, then walk you through reauth for each broken one",
    )
    sp_reconnect.set_defaults(func=cmd_reconnect)

    sp_stash = sub.add_parser("stash", help="Snapshot live auth.json into its slot (preserve refreshed tokens)")
    sp_stash.set_defaults(func=cmd_stash)

    sp_onboard = sub.add_parser("onboard", help="Guided login flow for N accounts")
    sp_onboard.add_argument("count", type=int, nargs="?", default=3)
    sp_onboard.set_defaults(func=cmd_onboard)

    sp_verify = sub.add_parser("verify", help="Test every slot's token by running a small codex exec probe")
    sp_verify.set_defaults(func=cmd_verify)

    sp_usage = sub.add_parser("usage", help="Refresh the usage cache and print")
    sp_usage.add_argument("--json", action="store_true")
    sp_usage.set_defaults(func=cmd_usage)

    sp_seed = sub.add_parser(
        "seed",
        help="Probe slots in parallel to populate usage data (defaults to slots with no record)",
    )
    sp_seed.add_argument("targets", nargs="*", help="slot numbers / emails (default: only slots without data)")
    sp_seed.add_argument("--all", action="store_true", help="Re-seed every slot, even those with data")
    sp_seed.add_argument("--concurrency", type=int, default=4, help="Max parallel probes (default: 4)")
    sp_seed.add_argument("--timeout", type=float, default=30.0, help="Per-probe timeout in seconds (default: 30)")
    sp_seed.set_defaults(func=cmd_seed)

    sp_launch = sub.add_parser("launch", help="Pick lowest-usage slot and exec codex")
    sp_launch.add_argument("--slot", help="Pin a specific slot")
    sp_launch.add_argument("--skip-auto", action="store_true", help="Skip auto-pick")
    sp_launch.add_argument("codex_args", nargs=argparse.REMAINDER, help="Args forwarded to codex")
    sp_launch.set_defaults(func=cmd_launch)

    sp_purge = sub.add_parser("purge", help="Delete all codex-swap state")
    sp_purge.add_argument("--yes", action="store_true", help="Confirm")
    sp_purge.set_defaults(func=cmd_purge)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    return ns.func(ns)


def cx_main(argv: list[str] | None = None) -> int:
    """Entry point for the `cx` shim — equivalent to `codex-swap launch`."""
    args = list(sys.argv[1:] if argv is None else argv)
    skip_auto = False
    pinned = None
    forwarded: list[str] = []
    i = 0
    # Lightweight pre-parse so the user can type `cx --slot 2 ...` without
    # collisions with codex's own --slot / --skip-auto.
    while i < len(args):
        a = args[i]
        if a == "--codex-swap-slot" and i + 1 < len(args):
            pinned = args[i + 1]
            i += 2
            continue
        if a == "--codex-swap-skip-auto":
            skip_auto = True
            i += 1
            continue
        forwarded.append(a)
        i += 1
    # Env knobs override CLI flags. CXSWAP_* is kept for the README's
    # original short-name examples; CODEX_SWAP_* is the explicit form.
    env = __import__("os").environ
    if "CODEX_SWAP_SKIP_AUTO" in env or "CXSWAP_SKIP_AUTO" in env:
        skip_auto = True
    env_slot = env.get("CODEX_SWAP_SLOT") or env.get("CXSWAP_SLOT")
    if env_slot:
        pinned = env_slot
    launch(forwarded, skip_auto=skip_auto, pinned_slot=pinned)
    return 0
