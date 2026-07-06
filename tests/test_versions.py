"""Tests for Connect version parsing and feature-support checks."""

from __future__ import annotations

import pytest

from connect_actions.versions import (
    FEATURE_MIN_VERSIONS,
    format_min_version,
    parse_version,
    supports,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025.12.0", (2025, 12, 0)),
        ("2025.06.0", (2025, 6, 0)),
        ("2026.07.0", (2026, 7, 0)),
        ("2025.12", (2025, 12, 0)),  # patch defaults to 0
        ("2025.12.3-dev", (2025, 12, 3)),  # build suffix ignored
        ("2025.12.0+abc123", (2025, 12, 0)),
        ("  2025.12.0  ", (2025, 12, 0)),  # leading whitespace
    ],
)
def test_parse_version_valid(raw, expected):
    assert parse_version(raw) == expected


@pytest.mark.parametrize("raw", ["", "unknown", "vNext", "abc.def"])
def test_parse_version_unparseable_returns_none(raw):
    assert parse_version(raw) is None


def test_parse_version_orders_correctly():
    assert parse_version("2025.06.0") < parse_version("2025.12.0")
    assert parse_version("2025.12.0") < parse_version("2026.07.0")
    # Calendar minors compare numerically, not lexically: 6 < 12.
    assert parse_version("2025.6.0") < parse_version("2025.10.0")


def test_feature_min_versions_are_gated_features():
    # Only features the actions actually gate on live here; Trusted Publishing is
    # left to `posit connect login` to validate.
    assert set(FEATURE_MIN_VERSIONS) == {"drafts", "metadata"}


@pytest.mark.parametrize("feature", list(FEATURE_MIN_VERSIONS))
def test_supports_unknown_version_returns_none(feature):
    assert supports("", feature) is None
    assert supports("not-a-version", feature) is None


def test_supports_at_and_above_minimum():
    assert supports("2025.07.0", "drafts") is True
    assert supports("2025.12.0", "drafts") is True
    assert supports("2025.12.0", "metadata") is True


def test_supports_below_minimum():
    # 2025.06.0 added draft previews but rsconnect can't verify a deploy against
    # them until 2025.07.0, so it's below the drafts floor.
    assert supports("2025.06.0", "drafts") is False
    assert supports("2025.05.0", "drafts") is False
    assert supports("2025.06.0", "metadata") is False


def test_format_min_version_zero_pads_month():
    assert format_min_version("drafts") == "2025.07.0"
    assert format_min_version("metadata") == "2025.12.0"
