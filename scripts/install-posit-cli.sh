#!/usr/bin/env bash
# Install the `posit` CLI. Both actions call this instead of running
# `uv tool install` inline, so there is one place that decides where the CLI
# and its rsconnect-python dependency come from.
#
# By default both come from PyPI. When the actions' `use-dev-cli` input is true
# (passed in as USE_DEV_CLI), both come from their `main` branches on GitHub
# instead, to test unreleased fixes.

set -euo pipefail

# The floor is the oldest release carrying everything the actions call:
# `posit connect login --identity-token`, `api --paginate`, `deploy --metadata`.
CLI_SPEC="posit-cli>=0.1.1"
WITH_ARGS=()

# An unset input arrives as the empty string, so treat that as off. Anything
# that is neither on nor off is a typo worth failing on -- silently installing
# the released CLI when the caller asked for dev would be worse.
case "$(printf '%s' "${USE_DEV_CLI:-}" | tr '[:upper:]' '[:lower:]')" in
  true | 1 | yes)
    echo "::warning::use-dev-cli is set: installing unreleased posit-cli and rsconnect-python from GitHub main. Builds are not reproducible, since main moves between runs."
    CLI_SPEC="git+https://github.com/posit-dev/posit-cli"
    # `--with` puts rsconnect-python in the same tool environment, where a
    # direct reference beats the version range posit-cli declares. It does still
    # have to satisfy that range, so a major bump upstream will surface here as
    # a uv resolution error.
    WITH_ARGS=(--with "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python")
    ;;
  '' | false | 0 | no) ;;
  *)
    echo "::error::use-dev-cli must be 'true' or 'false', got '${USE_DEV_CLI}'."
    exit 1
    ;;
esac

echo "Installing posit CLI from: $CLI_SPEC"
uv tool install "${WITH_ARGS[@]}" "$CLI_SPEC"

posit --version
