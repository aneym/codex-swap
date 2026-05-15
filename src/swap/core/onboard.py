"""Generic guided onboarding: log in to N accounts in a row."""

from __future__ import annotations

import sys

from .provider import Provider
from .sequence import load_sequence
from .slots import add_current, seed_slots


def onboard(provider: Provider, paths: dict, count: int) -> int:
    real = provider.find_binary()
    print(f"Onboarding {count} {provider.display_name} accounts. We'll log in to each in turn.")
    print(f"Real {provider.name} binary: {real}")
    print()

    # Stash whatever's currently logged in, so the user doesn't lose it.
    if provider.read_live_credentials() is not None:
        rc, msg = add_current(provider, paths)
        if rc == 0:
            print(msg)
        else:
            print(f"(skip: {msg})")
        print()

    for i in range(1, count + 1):
        print(f"=== Account {i} of {count} ===")
        print(
            "Clearing local credentials so the provider prompts a fresh login.\n"
            f"(Not running '{provider.name} logout' — that revokes the refresh token "
            "server-side and breaks any prior snapshot.)"
        )
        provider.clear_live_credentials()

        print(
            f"\nA browser window will open. Sign in to the next {provider.display_name} account.\n"
        )
        rc = provider.start_login()
        if rc != 0:
            sys.stderr.write(f"{provider.name} login exited with code {rc}. Aborting.\n")
            return rc
        if provider.read_live_credentials() is None:
            sys.stderr.write(
                f"{provider.name} login finished but credentials were not created. Aborting.\n"
            )
            return 1

        rc, msg = add_current(provider, paths)
        print(msg)
        print()

    seq = load_sequence(paths["sequence"])
    slot_ids = sorted(seq["accounts"], key=lambda s: int(s))
    print(f"Done. {len(slot_ids)} slot(s) configured.")
    if len(slot_ids) >= 2:
        print()
        print("Seeding usage data for all slots in parallel (one-time, ~50 tokens each)...")
        results = seed_slots(provider, paths, slot_ids)
        ok = sum(1 for _, status, _ in results if status == "ok")
        print(
            f"Seeded {ok}/{len(results)} slot(s) successfully. "
            f"Run `{provider.cli_prog} list` to verify."
        )
    return 0
