"""Tests for parsing the rsconnect-args input with shell quoting rules."""

from __future__ import annotations

import pytest

from connect_actions.rsconnect_args import RsconnectArgsError, parse_rsconnect_args


def test_empty_string_yields_no_args():
    assert parse_rsconnect_args("") == []


def test_simple_space_separated_args_unchanged():
    # Backward compatibility: plain flags with no quoting behave exactly as
    # the old unquoted Bash word-splitting did.
    assert parse_rsconnect_args("--verbose --new") == ["--verbose", "--new"]


def test_quoted_value_with_spaces_stays_together():
    assert parse_rsconnect_args('--title "My App"') == ["--title", "My App"]


def test_single_quoted_value_with_spaces_stays_together():
    assert parse_rsconnect_args("--title 'My App'") == ["--title", "My App"]


def test_mixed_quoted_and_unquoted_args():
    assert parse_rsconnect_args('--verbose --title "My App" --new') == [
        "--verbose",
        "--title",
        "My App",
        "--new",
    ]


def test_extra_whitespace_between_args_is_ignored():
    assert parse_rsconnect_args("  --verbose   --new  ") == ["--verbose", "--new"]


def test_unbalanced_quote_raises_rsconnect_args_error():
    with pytest.raises(RsconnectArgsError, match="Could not parse rsconnect-args"):
        parse_rsconnect_args('--title "My App')


def test_single_argument_value_with_equals_and_spaces():
    assert parse_rsconnect_args('--title="My App"') == ["--title=My App"]
