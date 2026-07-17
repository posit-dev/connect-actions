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
# Note ``quarto-shiny`` deploys as a Shiny app, so it does *not* need Quarto.
APP_MODE_TO_TYPE: dict[str, str] = {
    "python-shiny": "shiny",
    "python-fastapi": "fastapi",
    "python-flask": "flask",
    "python-dash": "dash",
    "python-streamlit": "streamlit",
    "python-bokeh": "bokeh",
    "quarto-static": "quarto",
    "quarto-shiny": "shiny",
}


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
    a subcommand; an empty ``app_mode`` raises :class:`AppTypeError`. Only the
    ``quarto`` subcommand runs ``quarto inspect`` locally, so ``needs_quarto`` is
    true exactly when the resolved type is ``quarto``.
    """
    if manifest_present:
        return AppType(deploy_type="manifest", needs_quarto=False)

    if not app_mode:
        raise AppTypeError(
            "Could not determine app_mode from the Connect content record. "
            "Provide a manifest.json or ensure the content GUID is correct."
        )

    deploy_type = APP_MODE_TO_TYPE.get(app_mode, app_mode)
    return AppType(deploy_type=deploy_type, needs_quarto=deploy_type == "quarto")
