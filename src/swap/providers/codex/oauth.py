"""Codex login + probe (active + isolated) — verbatim from the original module.

Login spawns `codex login` after the caller has stash/cleared local creds.
The two probe variants share helpers but differ in CODEX_HOME setup.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .binary import binary_env, find_binary

# Phrases that ONLY fire when codex's basic auth refresh is dead.
_BAD_TOKEN_PHRASES = (
    "Failed to refresh token",
    "refresh_token_reused",
    "refresh_token_revoked",
    "Your refresh token has already been used",
    "Your refresh token was revoked",
    "your refresh token was already used",
    "your refresh token was revoked",
    "token_invalidated",
)

_RATE_LIMIT_PHRASES = (
    "You've hit your usage limit",
    "rate_limit_reached",
    "usage limit. Visit",
    "limit_reached_type",
)


def start_login() -> int:
    """Spawn `codex login` interactively. Returns the rc."""
    real = find_binary()
    return subprocess.run([real, "login"], env=binary_env()).returncode


def _looks_broken(text: str) -> str | None:
    for phrase in _BAD_TOKEN_PHRASES:
        if phrase in text:
            return phrase
    return None


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _first_match(text: str, phrases) -> str:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return ""


def _line_with(text: str, phrase: str) -> str:
    for line in text.splitlines():
        if phrase in line:
            return line.strip()[:140]
    return phrase


def probe_active_slot(timeout: float = 10.0) -> tuple[str, str]:
    """Probe the live slot. Returns (status, detail)."""
    real = find_binary()
    verify_model = os.environ.get("CODEX_SWAP_VERIFY_MODEL", "gpt-5.4-mini")
    cmd = [
        real,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
    ]
    if verify_model:
        cmd.extend(["-m", verify_model])
    cmd.append("Reply exactly ok and do not use tools.")
    try:
        proc = subprocess.run(
            cmd,
            env=binary_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        combined = _as_text(proc.stdout) + "\n" + _as_text(proc.stderr)
        rc = proc.returncode
    except subprocess.TimeoutExpired as exc:
        combined = _as_text(exc.stdout) + "\n" + _as_text(exc.stderr)
        rc = None

    bad = _looks_broken(combined)
    if bad:
        return "broken", _line_with(combined, bad)
    if any(p in combined for p in _RATE_LIMIT_PHRASES):
        return "rate_limited", _line_with(combined, _first_match(combined, _RATE_LIMIT_PHRASES))
    if rc is None:
        return "ok", "auth ok (response was streaming when timeout fired)"
    if rc == 0:
        return "ok", "auth ok"
    last_err = ""
    for line in reversed(combined.splitlines()):
        if line.strip():
            last_err = line.strip()
            break
    return "error", f"probe exited {rc}: {last_err[:120]}"


def probe_slot_isolated(
    slot: str,
    snapshot_dir: Path,
    real_codex: str,
    timeout: float = 30.0,
) -> tuple[str, str, str, dict | None]:
    """Probe one slot using its own temporary CODEX_HOME (parallel-safe).

    `snapshot_dir` is the per-slot directory (e.g. `<root>/accounts/<N>/`); the
    slot's auth.json is at `<snapshot_dir>/auth.json`.
    """
    snapshot_path = snapshot_dir / "auth.json"
    if not snapshot_path.exists():
        return slot, "switch_failed", f"no snapshot at {snapshot_path}", None

    from .usage import latest_rate_limits

    tmp_root = Path(tempfile.mkdtemp(prefix=f"codex-swap-probe-{slot}-"))
    try:
        try:
            os.chmod(tmp_root, 0o700)
        except OSError:
            pass
        tmp_auth = tmp_root / "auth.json"
        shutil.copy2(snapshot_path, tmp_auth)
        os.chmod(tmp_auth, 0o600)

        env = binary_env()
        env["CODEX_HOME"] = str(tmp_root)

        verify_model = os.environ.get("CODEX_SWAP_VERIFY_MODEL", "gpt-5.4-mini")
        cmd = [
            real_codex,
            "exec",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--sandbox",
            "read-only",
        ]
        if verify_model:
            cmd.extend(["-m", verify_model])
        cmd.append("Reply exactly ok and do not use tools.")

        try:
            proc = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            combined = _as_text(proc.stdout) + "\n" + _as_text(proc.stderr)
            rc = proc.returncode
        except subprocess.TimeoutExpired as exc:
            combined = _as_text(exc.stdout) + "\n" + _as_text(exc.stderr)
            rc = None

        bad = _looks_broken(combined)
        if bad:
            return slot, "broken", _line_with(combined, bad), None
        if any(p in combined for p in _RATE_LIMIT_PHRASES):
            return (
                slot,
                "rate_limited",
                _line_with(combined, _first_match(combined, _RATE_LIMIT_PHRASES)),
                None,
            )

        # Capture rotated refresh_token before we tear down the temp dir.
        if tmp_auth.exists():
            shutil.copy2(tmp_auth, snapshot_path)
            os.chmod(snapshot_path, 0o600)

        record: dict | None = None
        sessions_root = tmp_root / "sessions"
        rollout_path: Path | None = None
        if sessions_root.exists():
            rollouts = list(sessions_root.rglob("rollout-*.jsonl"))
            if rollouts:
                rollouts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                rollout_path = rollouts[0]
                rl = latest_rate_limits(rollout_path)
                if isinstance(rl, dict):
                    record = {
                        "primary": rl.get("primary"),
                        "secondary": rl.get("secondary"),
                        "plan_type": rl.get("plan_type"),
                        "scanned_at": time.time(),
                        "source": "probe",
                        "source_path": str(rollout_path),
                    }

        if rc == 0:
            detail = "auth ok" if record else "auth ok (no rate_limits in rollout)"
            return slot, "ok", detail, record
        if rc is None:
            detail = (
                "auth ok (response was streaming when timeout fired)"
                if record
                else "timed out without capturing rate_limits"
            )
            return slot, "ok", detail, record
        last_err = ""
        for line in reversed(combined.splitlines()):
            if line.strip():
                last_err = line.strip()
                break
        return slot, "error", f"probe exited {rc}: {last_err[:120]}", record
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
