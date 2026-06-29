"""Command-line entry point for the connect-actions helper logic.

This is the thin I/O shell: it reads action inputs from environment variables,
delegates to the pure functions in the sibling modules, prints progress, and
writes ``key=value`` pairs to ``GITHUB_OUTPUT``. Keep logic out of here.
"""

from __future__ import annotations

import argparse
import os
import sys

from .config import ConfigError, resolve_config


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="connect_actions")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser(
        "resolve-config",
        help="Resolve Connect server, content GUID, and entrypoint.",
    )
    resolve.set_defaults(func=cmd_resolve_config)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
