"""Tests for deploy/scripts/generate-requirements.sh.

These drive the shell script directly in a temp directory and assert which
dependency source it picks. The script orders sources manifest.json ->
requirements.txt -> uv.lock -> pyproject.toml, so the tests pin down that
ordering (and the --frozen export behavior) rather than just "a deploy
succeeds," which can't tell the branches apart.

The uv.lock and pyproject.toml branches shell out to ``uv``, which resolves
from PyPI; these tests need network access (the same as ``uv run pytest``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "deploy"
    / "scripts"
    / "generate-requirements.sh"
)


def run(cwd: Path) -> subprocess.CompletedProcess:
    """Run generate-requirements.sh in ``cwd`` and return the completed process."""
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def write_pyproject(path: Path, dep: str) -> None:
    """Write a minimal project at ``path`` with a single pinned dependency."""
    (path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "myapp"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.11"\n'
        f'dependencies = ["{dep}"]\n'
    )


def test_uv_lock_wins_over_pyproject_and_is_frozen(tmp_path):
    # Lock iniconfig (a zero-dependency package) at 1.1.1, then bump pyproject to
    # 2.0.0 *without* re-locking. If the script uses the uv.lock branch with
    # --frozen, the export reflects the locked 1.1.1. If it instead re-resolved
    # (no --frozen) or fell through to the pyproject branch, we'd see 2.0.0.
    write_pyproject(tmp_path, "iniconfig==1.1.1")
    subprocess.run(["uv", "lock"], cwd=tmp_path, check=True, capture_output=True)
    write_pyproject(tmp_path, "iniconfig==2.0.0")

    result = run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "uv.lock found" in result.stdout
    requirements = (tmp_path / "requirements.txt").read_text()
    assert "iniconfig==1.1.1" in requirements
    assert "2.0.0" not in requirements


def test_existing_requirements_txt_takes_precedence(tmp_path):
    # An existing requirements.txt wins over uv.lock and is left untouched.
    write_pyproject(tmp_path, "iniconfig==1.1.1")
    subprocess.run(["uv", "lock"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n")

    result = run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "already exists" in result.stdout
    assert (tmp_path / "requirements.txt").read_text() == "flask==3.0.0\n"


def test_manifest_skips_generation(tmp_path):
    # manifest.json short-circuits: no requirements.txt is generated.
    (tmp_path / "manifest.json").write_text("{}")
    write_pyproject(tmp_path, "iniconfig==1.1.1")

    result = run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "manifest.json found" in result.stdout
    assert not (tmp_path / "requirements.txt").exists()


def test_pyproject_only_compiles(tmp_path):
    # With no requirements.txt or uv.lock, the pyproject.toml branch compiles.
    write_pyproject(tmp_path, "iniconfig==2.0.0")

    result = run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "pyproject.toml found" in result.stdout
    assert "iniconfig==2.0.0" in (tmp_path / "requirements.txt").read_text()


def test_no_sources_errors(tmp_path):
    # Nothing to deploy from -> non-zero exit and no requirements.txt.
    result = run(tmp_path)

    assert result.returncode != 0
    assert not (tmp_path / "requirements.txt").exists()
