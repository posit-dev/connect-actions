"""Tests for scripts/install-posit-cli.sh.

The script's whole job is choosing which specs to hand ``uv tool install``, so
these stub ``uv`` with a shim on PATH that records its arguments. That pins the
exact specs without a network install on every run.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "install-posit-cli.sh"

DEV_ARGV = [
    "tool",
    "install",
    "--with",
    "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python@main",
    "git+https://github.com/posit-dev/posit-cli@main",
]
RELEASED_ARGV = ["tool", "install", "posit-cli"]


@pytest.fixture
def fake_uv(tmp_path):
    """A PATH directory whose ``uv`` records its argv, one argument per line."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_log = tmp_path / "uv-argv"

    uv = bin_dir / "uv"
    uv.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{argv_log}"\n')
    uv.chmod(0o755)

    return bin_dir, argv_log


def run(fake_uv, use_dev_cli=None):
    """Run the script with a stubbed PATH; return (process, recorded uv argv)."""
    bin_dir, argv_log = fake_uv
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin"}
    if use_dev_cli is not None:
        env["USE_DEV_CLI"] = use_dev_cli

    proc = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, env=env
    )
    argv = argv_log.read_text().splitlines() if argv_log.exists() else []
    return proc, argv


def test_dev_installs_both_packages_from_main(fake_uv):
    proc, argv = run(fake_uv, "true")

    assert proc.returncode == 0, proc.stderr
    assert argv == DEV_ARGV


# Anything that isn't exactly "true" installs the released CLI, including a
# typo. Worth pinning so the fallback stays a deliberate choice.
@pytest.mark.parametrize("value", [None, "", "false", "True", "ture"])
def test_everything_else_installs_the_released_cli(fake_uv, value):
    proc, argv = run(fake_uv, value)

    assert proc.returncode == 0, proc.stderr
    assert argv == RELEASED_ARGV
    assert "git+" not in " ".join(argv)
