#!/usr/bin/env bash
# Install the `posit` CLI. A script rather than inline YAML only because both
# actions call it, so the specs and the version floor live in one place.
#
# USE_DEV_CLI is the actions' `use-dev-cli` input. Off, posit-cli and its
# rsconnect-python dependency come from PyPI; on, both come from `main` on
# GitHub, to test unreleased fixes.

set -euo pipefail

# An unset input arrives as the empty string. Anything that is neither true nor
# false is a typo worth failing on -- silently installing the released CLI when
# the caller asked for dev would be worse.
case "${USE_DEV_CLI:-}" in
  true)
    echo "::warning::use-dev-cli is set: installing unreleased posit-cli and rsconnect-python from GitHub main. Builds are not reproducible, since main moves between runs."
    # `@main` is explicit on purpose: a bare git URL follows whichever branch is
    # upstream's default, so a rename would quietly install a different ref.
    # `--with` puts rsconnect-python in the same tool environment, where a direct
    # reference beats the version range posit-cli declares (it must still satisfy
    # that range, so a major bump upstream surfaces as a uv resolution error).
    uv tool install \
      --with "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python@main" \
      "git+https://github.com/posit-dev/posit-cli@main"
    ;;
  false | '')
    # The floor is the oldest release carrying everything the actions call:
    # `posit connect login --identity-token`, `api --paginate`, `deploy --metadata`.
    uv tool install "posit-cli>=0.1.1"
    ;;
  *)
    echo "::error::use-dev-cli must be 'true' or 'false', got '${USE_DEV_CLI}'."
    exit 1
    ;;
esac

posit --version
