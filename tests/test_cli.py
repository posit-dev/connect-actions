"""Tests for the thin CLI layer: env in, GITHUB_OUTPUT out."""

from __future__ import annotations

from connect_actions.cli import main

DEPLOYMENTS = ".posit/publish/deployments"


def test_resolve_config_writes_github_output(tmp_path, monkeypatch):
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("INPUT_CONNECT_SERVER", "https://connect.example.com")
    monkeypatch.setenv("INPUT_CONTENT_GUID", "guid-123")
    monkeypatch.setenv("INPUT_DEPLOYMENT_FILE", "")

    assert main(["resolve-config"]) == 0

    written = output_file.read_text()
    assert "connect_server=https://connect.example.com" in written
    assert "content_guid=guid-123" in written
    assert "entrypoint=" in written


def test_resolve_config_reads_deployment_file(tmp_path, monkeypatch):
    toml_path = tmp_path / DEPLOYMENTS / "app.toml"
    toml_path.parent.mkdir(parents=True)
    toml_path.write_text(
        'server_url = "https://connect.example.com"\n'
        'id = "abc-123"\n'
        "[configuration]\n"
        'entrypoint = "app:app"\n'
    )
    output_file = tmp_path / "github_output"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.delenv("INPUT_CONNECT_SERVER", raising=False)
    monkeypatch.delenv("INPUT_CONTENT_GUID", raising=False)
    monkeypatch.delenv("INPUT_DEPLOYMENT_FILE", raising=False)

    assert main(["resolve-config"]) == 0

    written = output_file.read_text()
    assert "connect_server=https://connect.example.com" in written
    assert "content_guid=abc-123" in written
    assert "entrypoint=app:app" in written


def test_resolve_config_error_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))
    monkeypatch.delenv("INPUT_CONNECT_SERVER", raising=False)
    monkeypatch.delenv("INPUT_CONTENT_GUID", raising=False)
    monkeypatch.delenv("INPUT_DEPLOYMENT_FILE", raising=False)

    assert main(["resolve-config"]) == 1

    assert "Error: No .posit/publish/deployments/ directory" in capsys.readouterr().err
