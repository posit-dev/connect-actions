"""Tests for the 3-tier deployment configuration resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from connect_actions.config import (
    Config,
    ConfigError,
    find_deployment_file,
    parse_deployment_file,
    resolve_config,
)

DEPLOYMENTS = ".posit/publish/deployments"


def write_toml(path: Path, *, server="", guid="", entrypoint=None, files=None) -> Path:
    """Write a minimal Posit deployment TOML at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if server:
        lines.append(f'server_url = "{server}"')
    if guid:
        lines.append(f'id = "{guid}"')
    if entrypoint is not None or files is not None:
        lines.append("[configuration]")
    if entrypoint is not None:
        lines.append(f'entrypoint = "{entrypoint}"')
    if files is not None:
        rendered = ", ".join(f'"{f}"' for f in files)
        lines.append(f"files = [{rendered}]")
    path.write_text("\n".join(lines) + "\n")
    return path


def test_explicit_inputs_win(tmp_path):
    # Even with a deployment file present, explicit inputs short-circuit and the
    # file is never read (entrypoint stays empty).
    write_toml(
        tmp_path / DEPLOYMENTS / "app.toml",
        server="https://from-file.example.com",
        guid="from-file-guid",
        entrypoint="app.py",
    )

    config = resolve_config(
        connect_server="https://explicit.example.com",
        content_guid="explicit-guid",
        base_dir=tmp_path,
    )

    assert config == Config(
        connect_server="https://explicit.example.com",
        content_guid="explicit-guid",
        entrypoint="",
    )


def test_single_toml_auto_detect_includes_entrypoint(tmp_path):
    write_toml(
        tmp_path / DEPLOYMENTS / "app.toml",
        server="https://connect.example.com",
        guid="abc-123",
        entrypoint="app:app",
    )

    config = resolve_config(base_dir=tmp_path)

    assert config == Config(
        connect_server="https://connect.example.com",
        content_guid="abc-123",
        entrypoint="app:app",
    )


def test_auto_detect_searches_recursively(tmp_path):
    # The original used a recursive `find`; nested TOMLs must still be found.
    write_toml(
        tmp_path / DEPLOYMENTS / "nested" / "app.toml",
        server="https://connect.example.com",
        guid="nested-guid",
    )

    config = resolve_config(base_dir=tmp_path)

    assert config.content_guid == "nested-guid"


def test_deployment_file_input(tmp_path):
    write_toml(
        tmp_path / "custom" / "deploy.toml",
        server="https://connect.example.com",
        guid="custom-guid",
        entrypoint="main.py",
    )

    config = resolve_config(deployment_file="custom/deploy.toml", base_dir=tmp_path)

    assert config == Config(
        connect_server="https://connect.example.com",
        content_guid="custom-guid",
        entrypoint="main.py",
    )


def test_missing_specified_file_errors(tmp_path):
    with pytest.raises(ConfigError, match="Deployment file not found: nope.toml"):
        resolve_config(deployment_file="nope.toml", base_dir=tmp_path)


def test_multiple_toml_errors(tmp_path):
    write_toml(tmp_path / DEPLOYMENTS / "a.toml", server="s", guid="a")
    write_toml(tmp_path / DEPLOYMENTS / "b.toml", server="s", guid="b")

    with pytest.raises(ConfigError, match="Multiple deployment files found") as exc:
        resolve_config(base_dir=tmp_path)

    # The error lists each offending file and points at the input to disambiguate.
    message = str(exc.value)
    assert "a.toml" in message
    assert "b.toml" in message
    assert "Please specify one with the deployment-file input" in message


def test_no_toml_files_errors(tmp_path):
    (tmp_path / DEPLOYMENTS).mkdir(parents=True)

    with pytest.raises(ConfigError, match="No deployment files found"):
        resolve_config(base_dir=tmp_path)


def test_missing_directory_errors(tmp_path):
    with pytest.raises(
        ConfigError, match="No .posit/publish/deployments/ directory"
    ):
        resolve_config(base_dir=tmp_path)


def test_missing_keys_resolve_to_empty(tmp_path):
    # A TOML without server_url/id/configuration still parses to empty strings.
    toml_path = tmp_path / "sparse.toml"
    toml_path.write_text("unrelated = true\n")

    assert parse_deployment_file(toml_path) == Config(
        connect_server="", content_guid="", entrypoint="", extra_files=[]
    )


def test_extra_files_excludes_entrypoint_requirements_and_posit(tmp_path):
    # The declared files array carries the entrypoint, requirements.txt, .posit
    # metadata, and supplementary sources. Only the supplementary sources should
    # come back as extra files (entrypoint is the positional; requirements.txt
    # and .posit/ are handled elsewhere or not needed at runtime).
    config = parse_deployment_file(
        write_toml(
            tmp_path / "app.toml",
            server="s",
            guid="g",
            entrypoint="report.qmd",
            files=[
                "/report.qmd",
                "/requirements.txt",
                "/.posit/publish/Config-ABCD.toml",
                "/.posit/publish/deployments/deployment-WXYZ.toml",
                "/helper.py",
                "/data/input.csv",
            ],
        )
    )

    assert config.entrypoint == "report.qmd"
    assert config.extra_files == ["helper.py", "data/input.csv"]


def test_extra_files_empty_without_files_array(tmp_path):
    config = parse_deployment_file(
        write_toml(tmp_path / "app.toml", server="s", guid="g", entrypoint="report.qmd")
    )

    assert config.extra_files == []


def test_log_callback_reports_progress(tmp_path):
    write_toml(tmp_path / DEPLOYMENTS / "app.toml", server="s", guid="g")
    messages: list[str] = []

    resolve_config(base_dir=tmp_path, log=messages.append)

    assert any("Auto-detected deployment file" in m for m in messages)
    assert any("Reading configuration from" in m for m in messages)


def test_find_deployment_file_returns_path(tmp_path):
    expected = write_toml(tmp_path / DEPLOYMENTS / "app.toml", server="s", guid="g")

    assert find_deployment_file(tmp_path) == expected
