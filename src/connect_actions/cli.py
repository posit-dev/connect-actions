"""Command-line entry point for the connect-actions helper logic.

This is the thin I/O shell: it reads action inputs from environment variables,
delegates to the pure functions in the sibling modules, prints progress, and
writes ``key=value`` pairs to ``GITHUB_OUTPUT``. Keep logic out of here.
"""

from __future__ import annotations

import argparse
import os
import sys

from .apptype import AppTypeError, resolve_app_type
from .config import ConfigError, resolve_config
from .versions import format_min_version, supports


def _write_output(**values: str) -> None:
    """Append ``key=value`` lines to ``GITHUB_OUTPUT`` (or stdout when unset)."""
    lines = [f"{key}={value}" for key, value in values.items()]
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write("\n".join(lines) + "\n")
    else:
        for line in lines:
            print(line)


def cmd_resolve_config(_args: argparse.Namespace) -> int:
    try:
        config = resolve_config(
            connect_server=os.environ.get("INPUT_CONNECT_SERVER", ""),
            content_guid=os.environ.get("INPUT_CONTENT_GUID", ""),
            deployment_file=os.environ.get("INPUT_DEPLOYMENT_FILE", ""),
            log=print,
        )
    except ConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    _write_output(
        connect_server=config.connect_server,
        content_guid=config.content_guid,
        entrypoint=config.entrypoint,
    )
    return 0


def _truthy(value: str) -> bool:
    return value.strip().lower() == "true"


def cmd_resolve_app_type(_args: argparse.Namespace) -> int:
    """Map the content's app_mode to a deploy subcommand and Quarto need.

    Reads ``MANIFEST_PRESENT`` (whether a ``manifest.json`` was found) and
    ``APP_MODE`` (from ``posit connect api``), then writes ``app_type`` and
    ``needs_quarto`` so the action can conditionally set up Quarto and hand the
    subcommand to the deploy step.
    """
    try:
        app_type = resolve_app_type(
            manifest_present=_truthy(os.environ.get("MANIFEST_PRESENT", "")),
            app_mode=os.environ.get("APP_MODE", ""),
        )
    except AppTypeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(f"Resolved app type: {app_type.deploy_type} (needs_quarto={app_type.needs_quarto})")
    _write_output(
        app_type=app_type.deploy_type,
        needs_quarto="true" if app_type.needs_quarto else "false",
    )
    return 0


def cmd_check_deploy_features(_args: argparse.Namespace) -> int:
    """Decide which version-gated deploy features to use for this server.

    Reads ``CONNECT_VERSION`` (from ``posit connect api server_settings``) and
    ``DRAFT``. Fails when a draft is requested but the server is too old, and
    writes ``send_metadata`` so the deploy step knows whether to pass
    ``--metadata`` (unsupported metadata would fail the upload, so we skip it).
    """
    version = os.environ.get("CONNECT_VERSION", "")
    draft = _truthy(os.environ.get("DRAFT", ""))

    if not version:
        print(
            "::warning::Could not determine the Connect server version. Skipping "
            "bundle metadata to avoid failing on older servers; draft support is "
            "not verified."
        )

    if draft and supports(version, "drafts") is False:
        min_version = format_min_version("drafts")
        print(
            f"::error::Draft (preview) deployments require Connect {min_version} "
            f"or newer, but this server is running {version}. Set the deploy "
            "action's `draft: false` input to deploy directly instead of staging "
            "a preview."
        )
        return 1

    send_metadata = supports(version, "metadata") is True
    if version and not send_metadata:
        min_version = format_min_version("metadata")
        print(
            f"::notice::Connect {version} does not support bundle metadata "
            f"(requires {min_version} or newer); deploying without git provenance "
            "metadata."
        )

    _write_output(send_metadata="true" if send_metadata else "false")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="connect_actions")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser(
        "resolve-config",
        help="Resolve Connect server, content GUID, and entrypoint.",
    )
    resolve.set_defaults(func=cmd_resolve_config)

    app_type = subparsers.add_parser(
        "resolve-app-type",
        help="Map the content's app_mode to a deploy subcommand and Quarto need.",
    )
    app_type.set_defaults(func=cmd_resolve_app_type)

    deploy_features = subparsers.add_parser(
        "check-deploy-features",
        help="Gate draft/metadata deploy features on the Connect version.",
    )
    deploy_features.set_defaults(func=cmd_check_deploy_features)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
