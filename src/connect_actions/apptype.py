"""Resolve the ``posit connect deploy`` subcommand for a piece of content.

Connect records what kind of application a content item is as its ``app_mode``
(e.g. ``python-shiny``, ``quarto-static``). The deploy action reads that from the
content record on Connect -- the single source of truth, available whether or not
the repo has a Posit Publisher deployment TOML -- and maps it to the matching
``posit connect deploy`` subcommand.

A ``manifest.json`` short-circuits all of this: it already declares the app type,
entrypoint, and dependencies, so we deploy it directly and never inspect the
content record.

Everything here is pure: :func:`resolve_app_type` takes typed inputs and returns
an :class:`AppType` (or raises :class:`AppTypeError`). The thin CLI layer in
:mod:`connect_actions.cli` performs the I/O (the ``manifest.json`` check, the
``posit connect api`` query) and writes ``GITHUB_OUTPUT``.
"""

from __future__ import annotations

from dataclasses import dataclass

# Connect ``app_mode`` -> ``posit connect deploy`` subcommand. Modes not listed
# fall through unchanged, letting the CLI surface whatever it doesn't support.
#
# ``quarto-shiny`` is intentionally absent: Connect does not support Python
# shiny-backed Quarto documents (only R), so a Python deploy should never see
# that mode on a content record. See
# https://github.com/posit-dev/rsconnect-python/pull/755#issuecomment-4271245574
# (the supported path is to ``quarto render`` first, then deploy the rendered
# output as a plain ``python-shiny`` app).
APP_MODE_TO_TYPE: dict[str, str] = {
    "python-shiny": "shiny",
    "python-fastapi": "fastapi",
    "python-flask": "flask",
    "python-dash": "dash",
    "python-streamlit": "streamlit",
    "python-bokeh": "bokeh",
    "quarto-static": "quarto",
}

# Connect ``app_mode`` values for R content. The ``posit`` CLI (via
# rsconnect-python) can only build a bundle for Python and Quarto content from
# source; R content has no source-deploy path here and must be deployed from a
# pre-built ``manifest.json`` (generated in R with ``rsconnect::writeManifest()``).
# We single these out so a missing manifest produces an R-tailored error instead
# of falling through to the Python requirements-generation path. ``quarto-shiny``
# is R-backed too but is handled separately (it falls through unchanged); see the
# note on ``APP_MODE_TO_TYPE`` above.
R_APP_MODES: frozenset[str] = frozenset(
    {
        "shiny",  # R Shiny
        "rmd-shiny",  # interactive R Markdown
        "rmd-static",  # rendered R Markdown
        "api",  # R Plumber API
    }
)


class AppTypeError(Exception):
    """Raised when the deploy subcommand can't be determined.

    The message matches what the action prints (without the ``Error: `` prefix,
    which the CLI layer adds).
    """


@dataclass
class AppType:
    """The resolved deploy subcommand and whether it needs a local Quarto."""

    deploy_type: str
    needs_quarto: bool


def resolve_app_type(*, manifest_present: bool, app_mode: str) -> AppType:
    """Decide the deploy subcommand from a manifest or Connect ``app_mode``.

    With a ``manifest.json`` present the type is ``manifest`` and Quarto is never
    needed. Otherwise ``app_mode`` (from the Connect content record) is mapped to
    a subcommand; an empty ``app_mode`` raises :class:`AppTypeError`, as does an R
    ``app_mode`` (R content has no source-deploy path here and needs a
    ``manifest.json``). Only the ``quarto`` subcommand runs ``quarto inspect``
    locally, so ``needs_quarto`` is true exactly when the resolved type is
    ``quarto``.
    """
    if manifest_present:
        return AppType(deploy_type="manifest", needs_quarto=False)

    if not app_mode:
        raise AppTypeError(
            "Could not determine app_mode from the Connect content record. "
            "Provide a manifest.json or ensure the content GUID is correct."
        )

    if app_mode in R_APP_MODES:
        raise AppTypeError(
            f"R content (app_mode '{app_mode}') requires "
            "a manifest.json. Generate one in R with rsconnect::writeManifest() and "
            "commit it to your repository, then re-run the deploy."
        )

    deploy_type = APP_MODE_TO_TYPE.get(app_mode, app_mode)
    return AppType(deploy_type=deploy_type, needs_quarto=deploy_type == "quarto")
