#!/usr/bin/env bash
# Install the `posit` CLI. Both actions call this instead of running
# `uv tool install` inline, so there is one place that decides where the CLI
# and its rsconnect-python dependency come from.
#
# By default the CLI comes from PyPI. To test unreleased code, set either of
# these to any uv-installable requirement (a PEP 508 spec or a git+URL):
#
#   POSIT_CLI_SPEC         what to install, e.g.
#                          git+https://github.com/posit-dev/posit-cli@my-branch
#   RSCONNECT_PYTHON_SPEC  a full requirement pulled into the same tool
#                          environment, overriding the version posit-cli would
#                          otherwise resolve from PyPI, e.g.
#                          "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python@my-branch"
#
# Both are read from the environment, so a caller can set them under `env:` at
# the job or step level without the actions exposing an input for them. See
# "Using unreleased posit-cli or rsconnect-python" in the README.

set -euo pipefail

# The floor is the oldest release carrying everything the actions call:
# `posit connect login --identity-token`, `api --paginate`, `deploy --metadata`.
POSIT_CLI_SPEC="${POSIT_CLI_SPEC:-posit-cli>=0.1.1}"

# `--with` puts the requirement in the same tool environment, where a direct
# reference beats the range posit-cli declares. The dev version still has to
# satisfy that range; if it ever stops doing so, point UV_OVERRIDE at a
# requirements file, which uv reads without this script having to know.
WITH_ARGS=()
if [ -n "${RSCONNECT_PYTHON_SPEC:-}" ]; then
  WITH_ARGS+=(--with "$RSCONNECT_PYTHON_SPEC")
fi

echo "Installing posit CLI from: $POSIT_CLI_SPEC"
[ ${#WITH_ARGS[@]} -gt 0 ] && echo "Overriding rsconnect-python with: $RSCONNECT_PYTHON_SPEC"

uv tool install "${WITH_ARGS[@]}" "$POSIT_CLI_SPEC"

posit --version
