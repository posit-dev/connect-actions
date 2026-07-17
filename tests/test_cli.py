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


def test_resolve_config_writes_extra_files_as_heredoc(tmp_path, monkeypatch):
    toml_path = tmp_path / DEPLOYMENTS / "app.toml"
    toml_path.parent.mkdir(parents=True)
    toml_path.write_text(
        'server_url = "https://connect.example.com"\n'
        'id = "abc-123"\n'
        "[configuration]\n"
        'entrypoint = "report.qmd"\n'
        'files = ["/report.qmd", "/helper.py", "/data/input.csv"]\n'
    )
    output_file = tmp_path / "github_output"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.delenv("INPUT_CONNECT_SERVER", raising=False)
    monkeypatch.delenv("INPUT_CONTENT_GUID", raising=False)
    monkeypatch.delenv("INPUT_DEPLOYMENT_FILE", raising=False)

    assert main(["resolve-config"]) == 0

    written = output_file.read_text()
    # Multi-line outputs use the heredoc form so each file lands on its own line.
    assert "extra_files<<__GHA_EOF__\nhelper.py\ndata/input.csv\n__GHA_EOF__" in written


def test_resolve_config_empty_extra_files_uses_plain_form(tmp_path, monkeypatch):
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("INPUT_CONNECT_SERVER", "https://connect.example.com")
    monkeypatch.setenv("INPUT_CONTENT_GUID", "guid-123")
    monkeypatch.setenv("INPUT_DEPLOYMENT_FILE", "")

    assert main(["resolve-config"]) == 0

    assert "extra_files=\n" in output_file.read_text()


def test_resolve_config_error_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))
    monkeypatch.delenv("INPUT_CONNECT_SERVER", raising=False)
    monkeypatch.delenv("INPUT_CONTENT_GUID", raising=False)
    monkeypatch.delenv("INPUT_DEPLOYMENT_FILE", raising=False)

    assert main(["resolve-config"]) == 1

    assert "Error: No .posit/publish/deployments/ directory" in capsys.readouterr().err


def test_resolve_app_type_maps_app_mode(tmp_path, monkeypatch):
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("MANIFEST_PRESENT", "false")
    monkeypatch.setenv("APP_MODE", "quarto-static")

    assert main(["resolve-app-type"]) == 0

    written = output_file.read_text()
    assert "app_type=quarto" in written
    assert "needs_quarto=true" in written


def test_resolve_app_type_manifest(tmp_path, monkeypatch):
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("MANIFEST_PRESENT", "true")
    monkeypatch.setenv("APP_MODE", "")

    assert main(["resolve-app-type"]) == 0

    written = output_file.read_text()
    assert "app_type=manifest" in written
    assert "needs_quarto=false" in written


def test_resolve_app_type_empty_mode_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))
    monkeypatch.setenv("MANIFEST_PRESENT", "false")
    monkeypatch.setenv("APP_MODE", "")

    assert main(["resolve-app-type"]) == 1
    assert "Could not determine app_mode" in capsys.readouterr().err


def test_check_deploy_features_recent_server_sends_metadata(tmp_path, monkeypatch):
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("CONNECT_VERSION", "2025.12.0")
    monkeypatch.setenv("DRAFT", "true")

    assert main(["check-deploy-features"]) == 0
    assert "send_metadata=true" in output_file.read_text()


def test_check_deploy_features_old_server_skips_metadata(tmp_path, monkeypatch, capsys):
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("CONNECT_VERSION", "2025.06.0")
    monkeypatch.setenv("DRAFT", "false")

    assert main(["check-deploy-features"]) == 0
    assert "send_metadata=false" in output_file.read_text()
    assert "does not support bundle metadata" in capsys.readouterr().out


def test_check_deploy_features_draft_on_old_server_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github_output"))
    monkeypatch.setenv("CONNECT_VERSION", "2025.06.0")
    monkeypatch.setenv("DRAFT", "true")

    assert main(["check-deploy-features"]) == 1
    assert "Draft (preview) deployments require Connect" in capsys.readouterr().out


def test_check_deploy_features_unknown_version_skips_metadata(tmp_path, monkeypatch, capsys):
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("CONNECT_VERSION", "")
    monkeypatch.setenv("DRAFT", "true")  # unknown version does not block drafts

    assert main(["check-deploy-features"]) == 0
    assert "send_metadata=false" in output_file.read_text()
    assert "Could not determine the Connect server version" in capsys.readouterr().out
