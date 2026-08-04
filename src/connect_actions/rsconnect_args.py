"""Parse the ``rsconnect-args`` action input with shell quoting rules.

``rsconnect-args`` lets a caller pass arbitrary extra flags through to
``posit connect deploy`` (e.g. ``--title "My App"``). Passing the raw string
straight to Bash for unquoted (IFS) word-splitting can't express a value
containing whitespace: ``--title "My App"`` would split into three tokens --
``--title``, ``"My`` (literal quote included), and ``App"`` -- and the
click-based CLI rejects the extra argument.

:func:`parse_rsconnect_args` instead splits the string with POSIX shell
quoting rules (:func:`shlex.split`), so quoted substrings stay together as a
single argument while plain space-separated args (e.g. ``--verbose --new``)
behave exactly as before. The thin CLI layer in :mod:`connect_actions.cli`
writes the resulting list as a newline-delimited ``GITHUB_OUTPUT`` value (the
same pattern ``extra_files`` uses), and ``deploy.sh`` reads it back into a
Bash array to expand with proper quoting.
"""

from __future__ import annotations

import shlex


class RsconnectArgsError(Exception):
    """Raised when ``rsconnect-args`` can't be parsed as a shell-quoted string.

    The message matches what the action prints (without the ``Error: ``
    prefix, which the CLI layer adds).
    """


def parse_rsconnect_args(raw: str) -> list[str]:
    """Split the raw ``rsconnect-args`` string into individual arguments.

    Uses POSIX shell quoting rules, so ``--title "My App"`` yields
    ``["--title", "My App"]`` while unquoted args split on whitespace exactly
    as unquoted Bash expansion would. Raises :class:`RsconnectArgsError` on
    malformed input (e.g. an unbalanced quote).
    """
    try:
        return shlex.split(raw)
    except ValueError as err:
        raise RsconnectArgsError(f"Could not parse rsconnect-args: {err}") from err
