"""Smoke tests for shell entrypoint scripts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_install_script_help():
    proc = _run("bash", "scripts/install.sh", "--help")
    assert "Install codex-swap" in proc.stdout
    assert "--source auto|pypi|release|git" in proc.stdout


def test_install_script_dry_run_release():
    env = os.environ.copy()
    env["CODEX_SWAP_INSTALL_RELEASE_TAG"] = "v9.8.7"
    proc = subprocess.run(
        ["bash", "scripts/install.sh", "--dry-run", "--source", "release", "--no-path-check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    combined = proc.stdout + proc.stderr
    assert "https://github.com/aneym/codex-swap/releases/download/v9.8.7/" in combined
    assert "codex_swap-9.8.7-py3-none-any.whl" in combined
    assert "tool install" in combined or "pipx install" in combined


def test_install_script_dry_run_auto_uses_release_before_main():
    env = os.environ.copy()
    env["CODEX_SWAP_INSTALL_RELEASE_TAG"] = "v9.8.7"
    proc = subprocess.run(
        ["bash", "scripts/install.sh", "--dry-run", "--source", "auto", "--no-path-check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    combined = proc.stdout + proc.stderr
    assert "codex-swap" in combined
    assert "https://github.com/aneym/codex-swap/releases/download/v9.8.7/" in combined
    assert "codex_swap-9.8.7-py3-none-any.whl" in combined
    assert "git+https://github.com/aneym/codex-swap" in combined


def test_install_script_checks_custom_tool_bin_dir(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    app_dir = tmp_path / "apps"
    bin_dir.mkdir()
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {str(app_dir)!r}
cat > {str(app_dir / "codex-swap")!r} <<'EOF'
#!/usr/bin/env bash
echo "codex-swap fake"
EOF
chmod +x {str(app_dir / "codex-swap")!r}
touch {str(app_dir / "cx")!r}
chmod +x {str(app_dir / "cx")!r}
"""
    )
    fake_uv.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["UV_TOOL_BIN_DIR"] = str(app_dir)
    proc = subprocess.run(
        ["bash", "scripts/install.sh", "--source", "pypi", "--no-path-check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )

    combined = proc.stdout + proc.stderr
    assert "codex-swap fake" in proc.stdout
    assert "command not found" not in combined


def test_release_script_help():
    proc = _run("bash", "scripts/release.sh", "--help")
    assert "Release codex-swap" in proc.stdout
    assert "--no-push" in proc.stdout


def test_shell_scripts_have_no_syntax_errors():
    scripts = ["scripts/install.sh", "scripts/release.sh", "scripts/check-release.sh"]
    env = os.environ.copy()
    for script in scripts:
        subprocess.run(["bash", "-n", script], cwd=ROOT, env=env, check=True)
