"""Guided onboarding: log in to N ChatGPT Pro accounts in a row."""

from __future__ import annotations

import subprocess
import sys

from .auth import current_auth
from .codex import codex_env, find_real_codex
from .paths import AUTH_PATH
from .slots import add_current, load_sequence


def onboard(count: int) -> int:
    real = find_real_codex()
    print(f"Onboarding {count} Codex accounts. We'll log in to each in turn.")
    print(f"Real codex binary: {real}")
    print()

    # Stash whatever's currently logged in, so the user doesn't lose it.
    if current_auth() is not None:
        rc, msg = add_current()
        if rc == 0:
            print(msg)
        else:
            print(f"(skip: {msg})")
        print()

    for i in range(1, count + 1):
        print(f"=== Account {i} of {count} ===")
        print(
            "Clearing local auth.json so codex prompts a fresh login.\n"
            "(Not running 'codex logout' — that revokes the refresh token "
            "server-side and breaks any prior snapshot.)"
        )
        if AUTH_PATH.exists():
            AUTH_PATH.unlink()

        print("\nA browser window will open. Sign in to the next ChatGPT Pro account.\n")
        rc = subprocess.run([real, "login"], env=codex_env()).returncode
        if rc != 0:
            sys.stderr.write(f"codex login exited with code {rc}. Aborting.\n")
            return rc
        if not AUTH_PATH.exists():
            sys.stderr.write("codex login finished but auth.json was not created. Aborting.\n")
            return 1

        rc, msg = add_current()
        print(msg)
        print()

    seq = load_sequence()
    print(f"Done. {len(seq['accounts'])} slot(s) configured.")
    return 0
