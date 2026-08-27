#!/usr/bin/env bash
# Install the `posit` CLI. Both actions call this instead of running
# `uv tool install` inline, so there is one place that decides where the CLI
# and its rsconnect-python dependency come from.
#
# By default the CLI comes from PyPI. There are two ways to test unreleased
# code, from the blunt to the precise:
#
#   USE_DEV_CLI            the actions' `use-dev-cli` input. When true, install
#                          both posit-cli and rsconnect-python from the `main`
#                          branch on GitHub.
#   POSIT_CLI_SPEC         what to install as the CLI, as any uv-installable
#                          requirement (a PEP 508 spec or a git+URL), e.g.
#                          git+https://github.com/posit-dev/posit-cli@my-branch
#   RSCONNECT_PYTHON_SPEC  a full requirement pulled into the same tool
#                          environment, overriding the version posit-cli would
#                          otherwise resolve, e.g.
#                          "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python@my-branch"
#
# The two specs are read from the environment rather than from inputs, so they
# stay available for one-off pinning (a branch, a commit) without widening the
# actions' documented surface. They take precedence over USE_DEV_CLI, so
# `use-dev-cli: true` plus one spec means "dev everything, but this bit
# exactly". See "Using unreleased posit-cli or rsconnect-python" in the README.

set -euo pipefail

DEV_POSIT_CLI="git+https://github.com/posit-dev/posit-cli"
DEV_RSCONNECT_PYTHON="rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python"

# An unset input arrives as the empty string, so treat that as off. Anything
# that is neither on nor off is a typo worth failing on -- silently deploying
# with the released CLI when the caller asked for dev would be worse.
case "$(printf '%s' "${USE_DEV_CLI:-}" | tr '[:upper:]' '[:lower:]')" in
  true | 1 | yes)
    echo "::warning::use-dev-cli is set: this run does not use the released posit-cli and rsconnect-python from PyPI. Builds installing from a branch are not reproducible, since the branch moves between runs. The exact versions are logged below."
    POSIT_CLI_SPEC="${POSIT_CLI_SPEC:-$DEV_POSIT_CLI}"
    RSCONNECT_PYTHON_SPEC="${RSCONNECT_PYTHON_SPEC:-$DEV_RSCONNECT_PYTHON}"
    ;;
  '' | false | 0 | no) ;;
  *)
    echo "::error::use-dev-cli must be 'true' or 'false', got '${USE_DEV_CLI}'."
    exit 1
    ;;
esac

# The floor is the oldest release carrying everything the actions call:
# `posit connect login --identity-token`, `api --paginate`, `deploy --metadata`.
POSIT_CLI_SPEC="${POSIT_CLI_SPEC:-posit-cli>=0.1.1}"

# `--with` puts the requirement in the same tool environment, where a direct
# reference beats the range posit-cli declares. Whatever version lands still has
# to satisfy that range; if it ever stops doing so, point UV_OVERRIDE at a
# requirements file, which uv reads without this script having to know.
WITH_ARGS=()
if [ -n "${RSCONNECT_PYTHON_SPEC:-}" ]; then
  WITH_ARGS+=(--with "$RSCONNECT_PYTHON_SPEC")
fi

echo "Installing posit CLI from: $POSIT_CLI_SPEC"
[ ${#WITH_ARGS[@]} -gt 0 ] && echo "Overriding rsconnect-python with: $RSCONNECT_PYTHON_SPEC"

uv tool install "${WITH_ARGS[@]}" "$POSIT_CLI_SPEC"

posit --version
