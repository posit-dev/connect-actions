"""Tests for scripts/install-posit-cli.sh.

The script's whole job is choosing which specs to hand ``uv tool install``, so
these tests stub ``uv`` (and the ``posit`` it verifies afterwards) with shims on
PATH that record their arguments. That pins the exact specs -- including the
explicit ``@main``, which a bare git URL would silently turn into "whatever
upstream's default branch is" -- without a network install on every run.

USE_DEV_CLI arrives from an action input, so it is an arbitrary string rather
than a boolean. Only ``true``, ``false`` and empty are accepted -- GitHub renders
YAML booleans as lowercase, and anything else is more likely a typo than an
intent, so it fails the step rather than defaulting to the released CLI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "install-posit-cli.sh"

PYPI_SPEC = "posit-cli>=0.1.1"
DEV_CLI_SPEC = "git+https://github.com/posit-dev/posit-cli@main"
DEV_RSCONNECT_SPEC = (
    "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python@main"
)


@pytest.fixture
def fake_bin(tmp_path):
    """A PATH directory whose ``uv`` records its argv, one argument per line."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_log = tmp_path / "uv-argv"

    uv = bin_dir / "uv"
    uv.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{argv_log}"\n')
    uv.chmod(0o755)

    # The script ends with `posit --version` as a smoke check.
    posit = bin_dir / "posit"
    posit.write_text('#!/usr/bin/env bash\necho "posit, version 0.0.0-stub"\n')
    posit.chmod(0o755)

    return bin_dir, argv_log


def run(fake_bin, use_dev_cli=None):
    """Run the script with a stubbed PATH; return (process, recorded uv argv)."""
    bin_dir, argv_log = fake_bin
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(bin_dir.parent)}
    if use_dev_cli is not None:
        env["USE_DEV_CLI"] = use_dev_cli

    proc = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, env=env
    )
    argv = argv_log.read_text().splitlines() if argv_log.exists() else []
    return proc, argv


def test_default_installs_released_cli_from_pypi(fake_bin):
    # No input at all: the actions' default. Nothing may come from git, and no
    # --with override should be passed, so posit-cli resolves rsconnect itself.
    proc, argv = run(fake_bin)

    assert proc.returncode == 0, proc.stderr
    assert argv == ["tool", "install", PYPI_SPEC]
    assert "git+" not in " ".join(argv)


@pytest.mark.parametrize("value", ["false", ""])
def test_off_values_install_from_pypi(fake_bin, value):
    proc, argv = run(fake_bin, value)

    assert proc.returncode == 0, proc.stderr
    assert argv == ["tool", "install", PYPI_SPEC]


@pytest.mark.parametrize("value", ["true"])
def test_on_values_install_both_packages_from_main(fake_bin, value):
    proc, argv = run(fake_bin, value)

    assert proc.returncode == 0, proc.stderr
    assert argv == ["tool", "install", "--with", DEV_RSCONNECT_SPEC, DEV_CLI_SPEC]
    # Surfaces in the run's annotations, so an accidental `use-dev-cli: true`
    # left on in a workflow is visible without reading the log.
    assert "::warning::" in proc.stdout


@pytest.mark.parametrize(
    "value", ["ture", "maybe", "yes", "1", "0", "no", "TRUE", "True", "true false"]
)
def test_unrecognized_value_fails_without_installing(fake_bin, value):
    # The dangerous failure is installing the *released* CLI when the caller
    # asked for dev, so an unparseable value must stop the step, not fall back.
    proc, argv = run(fake_bin, value)

    assert proc.returncode == 1
    assert "::error::" in proc.stdout
    assert argv == []
