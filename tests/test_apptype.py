"""Tests for mapping a Connect app_mode to a deploy subcommand."""

from __future__ import annotations

import pytest

from connect_actions.apptype import AppType, AppTypeError, resolve_app_type


def test_manifest_short_circuits_lookup():
    # A manifest.json wins even when an app_mode is also available; it never
    # needs a local Quarto install.
    result = resolve_app_type(manifest_present=True, app_mode="quarto-static")

    assert result == AppType(deploy_type="manifest", needs_quarto=False)


@pytest.mark.parametrize(
    "app_mode, deploy_type",
    [
        ("python-shiny", "shiny"),
        ("python-fastapi", "fastapi"),
        ("python-flask", "flask"),
        ("python-dash", "dash"),
        ("python-streamlit", "streamlit"),
        ("python-bokeh", "bokeh"),
        ("quarto-static", "quarto"),
    ],
)
def test_known_app_modes_map_to_subcommand(app_mode, deploy_type):
    assert resolve_app_type(manifest_present=False, app_mode=app_mode).deploy_type == deploy_type


def test_quarto_static_needs_quarto():
    assert resolve_app_type(manifest_present=False, app_mode="quarto-static").needs_quarto is True


def test_quarto_shiny_falls_through_unchanged():
    # Connect doesn't support Python shiny-backed Quarto docs (only R), so there
    # is no mapping for quarto-shiny; it passes straight through. See
    # https://github.com/posit-dev/rsconnect-python/pull/755#issuecomment-4271245574
    result = resolve_app_type(manifest_present=False, app_mode="quarto-shiny")

    assert result == AppType(deploy_type="quarto-shiny", needs_quarto=False)


def test_unknown_app_mode_falls_through_unchanged():
    # An unrecognized mode passes straight to `posit connect deploy`, which will
    # reject it if genuinely unsupported.
    result = resolve_app_type(manifest_present=False, app_mode="python-gradio")

    assert result == AppType(deploy_type="python-gradio", needs_quarto=False)


def test_empty_app_mode_without_manifest_errors():
    with pytest.raises(AppTypeError, match="Could not determine app_mode"):
        resolve_app_type(manifest_present=False, app_mode="")


@pytest.mark.parametrize("app_mode", ["shiny", "rmd-shiny", "rmd-static", "api"])
def test_r_app_modes_without_manifest_error_with_r_guidance(app_mode):
    # R content can't be built from source here; the error must name R and point
    # to a manifest.json rather than mentioning uv.lock/pyproject.toml/Python.
    with pytest.raises(AppTypeError) as excinfo:
        resolve_app_type(manifest_present=False, app_mode=app_mode)

    message = str(excinfo.value)
    assert "R" in message
    assert "manifest.json" in message
    assert "writeManifest" in message
    assert "uv" not in message.lower()
    assert "pyproject" not in message.lower()


def test_r_app_mode_with_manifest_still_deploys():
    # A manifest.json is exactly the supported path for R content, so its presence
    # short-circuits the R check and deploys the manifest directly.
    result = resolve_app_type(manifest_present=True, app_mode="shiny")

    assert result == AppType(deploy_type="manifest", needs_quarto=False)
