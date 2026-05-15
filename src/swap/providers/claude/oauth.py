"""Claude Code login flow + probe stubs.

The agent-friendly bit is ``start_login()``: it (a) backs up the live state,
(b) wipes whatever's live so claude-code prompts a fresh OAuth, (c) spawns
``claude auth login``, (d) scrapes any URL we see in the child's stdout/stderr
and re-emits it on a single marker line that an agent can grep for, (e)
restores the backup on failure.

URL surfacing strategy (in priority order):
1. Set ``BROWSER=echo`` in the spawned env. Some CLIs honor this; some don't.
2. Prepend a temporary PATH dir containing a shim named ``open`` (and
   ``xdg-open`` on Linux) that prints its argv on stdout. This catches
   claude-code's standard "open the browser" call on macOS.
3. Tap the child's stdout/stderr via a pty so we still scrape any URL the
   child writes directly (some claude versions print the URL before opening
   the browser anyway).

Probes (``probe_active_slot``, ``probe_slot_isolated``) are intentional v0.1
stubs that return ``("ok", "probe not implemented")``. v0.2 should call the
Anthropic ``/api/oauth/usage`` endpoint and treat a 401 as ``broken``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from . import auth as _auth
from .binary import binary_env, find_binary

_URL_RE = re.compile(r"https?://[^\s<>\"']+")


# ---------------------------------------------------------------------------
# shim dir: prepended to PATH so claude-code's `open <url>` prints the URL
# instead of launching a browser.
# ---------------------------------------------------------------------------


_OPEN_SHIM = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    # claude-swap shim: print any URL argv instead of launching a browser.
    for arg in "$@"; do
      case "$arg" in
        http://*|https://*)
          # Single, agent-friendly marker line. Flush by exiting normally.
          printf 'claude-swap: open in browser \xE2\x86\x92 %s\\n' "$arg"
          ;;
      esac
    done
    exit 0
    """
)


def _materialize_open_shim(dirpath: Path) -> None:
    """Drop ``open`` + ``xdg-open`` shims into ``dirpath``."""
    for name in ("open", "xdg-open"):
        target = dirpath / name
        target.write_text(_OPEN_SHIM)
        target.chmod(0o755)


def _spawn_env_with_shim(shim_dir: Path) -> dict:
    env = binary_env()
    existing = env.get("PATH", "")
    env["PATH"] = f"{shim_dir}:{existing}" if existing else str(shim_dir)
    env["BROWSER"] = "echo"
    env.setdefault("CLAUDE_SWAP_LOGIN", "1")
    return env


# ---------------------------------------------------------------------------
# URL surfacing — sniffs the child output stream.
# ---------------------------------------------------------------------------


_MARKER_PREFIX = "claude-swap: open in browser → "


def _emit_url_marker(url: str, *, already_seen: set[str]) -> None:
    """Emit our single-line marker once per unique URL."""
    if url in already_seen:
        return
    already_seen.add(url)
    sys.stdout.write(f"{_MARKER_PREFIX}{url}\n")
    sys.stdout.flush()


def _watch_line(line: str, seen: set[str]) -> None:
    """Forward a line of child output verbatim, and also scan for URLs.

    The shim writes the marker itself; this catcher handles any direct URL
    the child writes to stdout/stderr.
    """
    sys.stdout.write(line)
    sys.stdout.flush()
    if _MARKER_PREFIX in line:
        # already a marker — don't re-emit.
        return
    for url in _URL_RE.findall(line):
        # Filter obvious docs/help URLs we don't care about. The OAuth flow
        # uses ``claude.ai`` / ``platform.claude.com`` / ``console.anthropic.com``.
        if any(
            host in url
            for host in (
                "claude.ai",
                "anthropic.com",
                "claude.com",
                "anthropic",
            )
        ):
            _emit_url_marker(url, already_seen=seen)


# ---------------------------------------------------------------------------
# the public entry point
# ---------------------------------------------------------------------------


def start_login() -> int:
    """Run an interactive ``claude auth login`` with backup + URL relay.

    Returns the child process return code. On any failure (non-zero rc) the
    pre-login keychain + ``oauthAccount`` snapshot is restored so the user
    isn't left logged out.
    """
    real = find_binary()
    backup_creds, backup_oauth = _auth.capture_live_state()

    # Wipe the live creds before login so claude prompts a fresh OAuth.
    # (Leaving them in place causes claude to silently reuse the active
    # account.)
    _auth.clear_live_credentials()

    with tempfile.TemporaryDirectory(prefix="claude-swap-login-") as shim_dir:
        shim_path = Path(shim_dir)
        _materialize_open_shim(shim_path)
        env = _spawn_env_with_shim(shim_path)

        seen: set[str] = set()
        rc = _run_login(real, env, seen)

    if rc != 0:
        # Roll back so the user isn't stranded.
        _auth.restore_live_state(backup_creds, backup_oauth)
        return rc

    # Success: verify creds actually appeared.
    new_creds = _auth.read_live_credentials()
    if not new_creds:
        # Login claimed success but didn't write creds; roll back.
        _auth.restore_live_state(backup_creds, backup_oauth)
        sys.stderr.write(
            "claude-swap: login finished but no credentials were written.\n"
        )
        return 1
    return 0


def _run_login(real: str, env: dict, seen: set[str]) -> int:
    """Spawn ``claude auth login`` and tee its output, scanning for URLs.

    Uses a Popen pipe rather than ``pty.fork`` to keep this dependency-free
    and cross-platform. The trade-off: claude-code will see a non-TTY child
    stdout, which usually still works for ``auth login`` (it just won't
    paint a colored UI). We forward the pipe contents verbatim so the user
    still sees prompts on their terminal.
    """
    cmd = [real, "auth", "login"]
    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdin=sys.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        sys.stderr.write(f"claude-swap: failed to spawn {cmd[0]}: {exc}\n")
        return 127

    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            _watch_line(line, seen)
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait(timeout=5)
        return proc.returncode or 130
    return proc.wait()


# ---------------------------------------------------------------------------
# probes — stubs for v0.1
# ---------------------------------------------------------------------------


def probe_active_slot(timeout: float = 10.0) -> tuple[str, str]:
    """Probe the live slot. v0.1: stub.

    A real probe would refresh the access token if expired and call
    ``GET https://api.anthropic.com/api/oauth/usage`` with the access token.
    A 401 with ``invalid_grant`` body means the refresh chain is dead and the
    slot is ``broken``; a 200 means ``ok``; anything else is ``error``.
    """
    _ = timeout
    return "ok", "probe not implemented in v0.1"


def probe_slot_isolated(
    slot: str,
    snapshot_dir: Path,
    real_claude: str,
    timeout: float = 30.0,
) -> tuple[str, str, str, dict | None]:
    """Isolated probe. v0.1: stub that always returns ``ok``.

    A real isolated probe would point ``CLAUDE_CONFIG_DIR`` at a temporary
    directory, restore the slot snapshot into it, and run the usage endpoint
    call with the slot's refresh token. Until then we just confirm the
    snapshot exists.
    """
    _ = real_claude
    _ = timeout
    creds = snapshot_dir / "credentials.json"
    if not creds.exists():
        return slot, "switch_failed", f"no snapshot at {creds}", None
    return slot, "ok", "probe not implemented in v0.1", None
