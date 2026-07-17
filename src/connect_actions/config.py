"""Resolve Connect deployment configuration (server, GUID, entrypoint).

The same 3-tier resolution backs both the deploy and cleanup-previews actions:

1. Explicit ``connect-server`` + ``content-guid`` inputs.
2. A ``deployment-file`` input pointing at a Posit deployment TOML.
3. Auto-detection of exactly one ``.toml`` under ``.posit/publish/deployments/``.

Everything here is pure: functions take typed inputs and either return a
:class:`Config` or raise :class:`ConfigError`. The thin CLI layer in
:mod:`connect_actions.cli` reads env vars, prints progress, and writes
``GITHUB_OUTPUT``.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DEPLOYMENTS_DIR = ".posit/publish/deployments"


@dataclass
class Config:
    """Resolved deployment configuration."""

    connect_server: str
    content_guid: str
    entrypoint: str = ""
    content_type: str = ""


class ConfigError(Exception):
    """Raised when deployment configuration cannot be resolved.

    The message matches what the action prints (without the ``Error: ``
    prefix, which the CLI layer adds).
    """


def find_deployment_file(base_dir: Path) -> Path:
    """Auto-detect the single deployment TOML under ``.posit/publish/deployments/``.

    Searches recursively (matching the original ``find``). Raises
    :class:`ConfigError` if the directory is missing, empty, or holds more than
    one TOML file.
    """
    deployments_dir = base_dir / DEPLOYMENTS_DIR
    if not deployments_dir.is_dir():
        raise ConfigError(
            "No .posit/publish/deployments/ directory and "
            "connect-server/content-guid not provided"
        )

    toml_files = sorted(deployments_dir.rglob("*.toml"))
    if not toml_files:
        raise ConfigError(
            "No deployment files found in .posit/publish/deployments/ and "
            "connect-server/content-guid not provided"
        )
    if len(toml_files) > 1:
        listing = "\n".join(f"  {path}" for path in toml_files)
        raise ConfigError(
            "Multiple deployment files found in .posit/publish/deployments/:\n"
            f"{listing}\n"
            "Please specify one with the deployment-file input"
        )
    return toml_files[0]


def parse_deployment_file(path: Path) -> Config:
    """Parse a Posit deployment TOML file into a :class:`Config`.

    Missing keys resolve to empty strings, matching the original parser.
    """
    with path.open("rb") as f:
        data = tomllib.load(f)

    configuration = data.get("configuration", {})
    return Config(
        connect_server=data.get("server_url", ""),
        content_guid=data.get("id", ""),
        entrypoint=configuration.get("entrypoint", ""),
        # Posit Publisher records the content type (e.g. "quarto-static",
        # "python-shiny") at the top level; the deploy action uses it to decide
        # whether the runner needs a Quarto install for `quarto inspect`.
        content_type=data.get("type", ""),
    )


def resolve_config(
    *,
    connect_server: str = "",
    content_guid: str = "",
    deployment_file: str = "",
    base_dir: Path | None = None,
    log: Callable[[str], None] = lambda _msg: None,
) -> Config:
    """Resolve deployment configuration via the 3-tier priority.

    ``log`` receives human-readable progress messages; it defaults to a no-op so
    the function stays side-effect free for tests. ``base_dir`` is the directory
    that relative paths resolve against (defaults to the current directory).
    """
    if base_dir is None:
        base_dir = Path(".")

    # Tier 1: explicit inputs win, and skip TOML parsing entirely.
    if connect_server and content_guid:
        log("Using provided connect-server and content-guid")
        return Config(connect_server=connect_server, content_guid=content_guid)

    # Tier 2: a specified deployment file.
    if deployment_file:
        path = base_dir / deployment_file
        if not path.is_file():
            raise ConfigError(f"Deployment file not found: {deployment_file}")
    # Tier 3: auto-detect the single TOML under .posit/publish/deployments/.
    else:
        path = find_deployment_file(base_dir)
        log(f"Auto-detected deployment file: {path}")

    log(f"Reading configuration from: {path}")
    return parse_deployment_file(path)
