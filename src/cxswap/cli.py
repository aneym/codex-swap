"""argparse front-end for cxswap."""

from __future__ import annotations

import argparse
import sys
import time

from . import __version__
from .auth import auth_identity, current_auth
from .launcher import launch
from .onboard import onboard
from .paths import AUTH_PATH
from .slots import (
    add_current,
    current_slot,
    load_sequence,
    remove,
    rotate,
    reauth,
    stash_active,
    switch_to,
    verify_all,
)
from .usage import refresh_cache


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


def cmd_add(args) -> int:
    rc, msg = add_current()
    print(msg)
    return rc


def cmd_remove(args) -> int:
    rc, msg = remove(args.target)
    print(msg)
    return rc


def cmd_list(args) -> int:
    seq = load_sequence()
    if not seq["accounts"]:
        print("No accounts configured. Run `cxswap onboard 3` to set them up.")
        return 0
    usage = {}
    if not args.no_usage:
        usage = refresh_cache().get("data", {})
    active = current_slot(seq)
    print(f"{'':2} {'slot':<5} {'email':<35} {'plan':<8} {'5h':>6} {'7d':>6} {'resets':>10}")
    for slot in sorted(seq["accounts"], key=lambda s: int(s)):
        acc = seq["accounts"][slot]
        marker = "*" if slot == active else " "
        info = usage.get(slot, {}) if isinstance(usage, dict) else {}
        primary = info.get("primary") if isinstance(info.get("primary"), dict) else {}
        secondary = info.get("secondary") if isinstance(info.get("secondary"), dict) else {}
        print(
            f" {marker} {slot:<5} {(acc.get('email') or '')[:34]:<35} "
            f"{(acc.get('plan_type') or '')[:7]:<8} "
            f"{_fmt_pct(primary.get('used_percent') if primary else None):>6} "
            f"{_fmt_pct(secondary.get('used_percent') if secondary else None):>6} "
            f"{_fmt_resets(primary.get('resets_at') if primary else None):>10}"
        )
    return 0


def cmd_status(args) -> int:
    auth = current_auth()
    if not auth:
        print(f"No auth.json at {AUTH_PATH} (logged out).")
        return 0
    email, account_id, plan_type = auth_identity(auth)
    seq = load_sequence()
    slot = current_slot(seq)
    if slot:
        print(f"Active: slot {slot} — {email} ({plan_type})")
    else:
        print(f"Active: unmanaged — {email} ({plan_type}), account_id={account_id[:12]}…")
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
    for slot, status, detail in results:
        if status == "broken":
            broken.append(slot)
        elif status == "rate_limited":
            rate_limited.append(slot)
        email = (seq["accounts"].get(slot, {}).get("email") or "")[:31]
        print(f"{slot:<5} {email:<32} {status:<14}  {detail[:80]}")
    notes = []
    if broken:
        notes.append(
            f"{len(broken)} slot(s) need re-minting (auth dead). "
            f"Run: cxswap reauth {' / '.join(broken)}"
        )
    if rate_limited:
        notes.append(
            f"{len(rate_limited)} slot(s) hit their usage cap — auth is fine, "
            f"they'll auto-refresh when the window resets."
        )
    if notes:
        print()
        for n in notes:
            print(n)
    return 1 if broken else 0


def cmd_usage(args) -> int:
    payload = refresh_cache()
    if args.json:
        import json as _json
        print(_json.dumps(payload, indent=2))
    else:
        data = payload.get("data", {})
        if not data:
            print("(no usage data — slots haven't been used yet, or rollouts not found)")
        for slot, info in sorted(data.items(), key=lambda kv: int(kv[0])):
            primary = info.get("primary") or {}
            secondary = info.get("secondary") or {}
            print(
                f"slot {slot}: 5h={_fmt_pct(primary.get('used_percent'))} "
                f"7d={_fmt_pct(secondary.get('used_percent'))} "
                f"plan={info.get('plan_type') or '—'}"
            )
    return 0


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
        prog="cxswap",
        description="Multi-account switcher for the OpenAI Codex CLI.",
    )
    p.add_argument("--version", action="version", version=f"cxswap {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp_add = sub.add_parser("add", help="Save the currently logged-in account as a new slot")
    sp_add.set_defaults(func=cmd_add)

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

    sp_stash = sub.add_parser("stash", help="Snapshot live auth.json into its slot (preserve refreshed tokens)")
    sp_stash.set_defaults(func=cmd_stash)

    sp_onboard = sub.add_parser("onboard", help="Guided login flow for N accounts")
    sp_onboard.add_argument("count", type=int, nargs="?", default=3)
    sp_onboard.set_defaults(func=cmd_onboard)

    sp_verify = sub.add_parser("verify", help="Test every slot's token by running 'codex login status'")
    sp_verify.set_defaults(func=cmd_verify)

    sp_usage = sub.add_parser("usage", help="Refresh the usage cache and print")
    sp_usage.add_argument("--json", action="store_true")
    sp_usage.set_defaults(func=cmd_usage)

    sp_launch = sub.add_parser("launch", help="Pick lowest-usage slot and exec codex")
    sp_launch.add_argument("--slot", help="Pin a specific slot")
    sp_launch.add_argument("--skip-auto", action="store_true", help="Skip auto-pick")
    sp_launch.add_argument("codex_args", nargs=argparse.REMAINDER, help="Args forwarded to codex")
    sp_launch.set_defaults(func=cmd_launch)

    sp_purge = sub.add_parser("purge", help="Delete all cxswap state")
    sp_purge.add_argument("--yes", action="store_true", help="Confirm")
    sp_purge.set_defaults(func=cmd_purge)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    return ns.func(ns)


def cx_main(argv: list[str] | None = None) -> int:
    """Entry point for the `cx` shim — equivalent to `cxswap launch`."""
    args = list(sys.argv[1:] if argv is None else argv)
    skip_auto = False
    pinned = None
    forwarded: list[str] = []
    i = 0
    # Lightweight pre-parse so the user can type `cx --slot 2 ...` without
    # collisions with codex's own --slot / --skip-auto.
    while i < len(args):
        a = args[i]
        if a == "--cxswap-slot" and i + 1 < len(args):
            pinned = args[i + 1]
            i += 2
            continue
        if a == "--cxswap-skip-auto":
            skip_auto = True
            i += 1
            continue
        forwarded.append(a)
        i += 1
    # Env knobs override CLI flags.
    if "CXSWAP_SKIP_AUTO" in __import__("os").environ:
        skip_auto = True
    env_slot = __import__("os").environ.get("CXSWAP_SLOT")
    if env_slot:
        pinned = env_slot
    launch(forwarded, skip_auto=skip_auto, pinned_slot=pinned)
    return 0
