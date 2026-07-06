"""Connect server version parsing and feature-support checks.

Several features these actions rely on are only available on recent Connect
releases. Rather than let a deploy fail with a cryptic API error (or silently
require a version the user didn't know about), we read the server's version
(``posit connect api server_settings -q .version``) and decide up front which
features to use.

Everything here is pure: functions take a raw version string and return typed
results. The thin CLI layer in :mod:`connect_actions.cli` reads env vars, prints
GitHub Actions annotations, and writes ``GITHUB_OUTPUT``.

A version compares as a ``(major, minor, patch)`` tuple. When the version can't
be determined (empty string, unparseable, or the admin has hidden it via
``Server.HideVersion``) the support checks return ``None`` -- "unknown" -- and
callers degrade gracefully rather than guessing.
"""

from __future__ import annotations

import re

# Minimum Connect version for each feature, as a comparable version tuple.
FEATURE_MIN_VERSIONS: dict[str, tuple[int, int, int]] = {
    # Draft (preview) deployments: `posit connect deploy --draft`.
    "drafts": (2025, 6, 0),
    # Bundle metadata upload (`--metadata`), via rsconnect's multipart API.
    # https://github.com/posit-dev/rsconnect-python/pull/736
    "metadata": (2025, 12, 0),
    # Trusted Publishing (OIDC token exchange). Also requires an Enhanced or
    # Advanced license, which we can't detect here.
    "trusted-publishing": (2026, 7, 0),
}


def format_min_version(feature: str) -> str:
    """Render a feature's minimum version the way Connect does (e.g. ``2025.06.0``)."""
    major, minor, patch = FEATURE_MIN_VERSIONS[feature]
    return f"{major}.{minor:02d}.{patch}"


def parse_version(raw: str) -> tuple[int, int, int] | None:
    """Parse a Connect version string into a ``(major, minor, patch)`` tuple.

    Connect versions are calendar-based, e.g. ``2025.12.0``, sometimes with a
    build suffix (``2025.12.0-dev``, ``2025.12.0+abc``). We read the leading
    ``major.minor[.patch]`` numeric components and ignore any suffix. Returns
    ``None`` when the string is empty or has no recognizable version prefix.
    """
    if not raw:
        return None
    match = re.match(r"\s*(\d+)\.(\d+)(?:\.(\d+))?", raw)
    if not match:
        return None
    major, minor, patch = match.group(1), match.group(2), match.group(3)
    return (int(major), int(minor), int(patch or 0))


def supports(raw: str, feature: str) -> bool | None:
    """Whether a server running version ``raw`` supports ``feature``.

    Returns ``True``/``False`` when the version is known, or ``None`` when it
    can't be determined so the caller can decide how to degrade.
    """
    version = parse_version(raw)
    if version is None:
        return None
    return version >= FEATURE_MIN_VERSIONS[feature]
