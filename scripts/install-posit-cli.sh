#!/usr/bin/env bash
set -euo pipefail

case "${USE_DEV_CLI:-}" in
  true)
    echo "::warning::use-dev-cli is set: installing unreleased posit-cli and rsconnect-python from GitHub main."
    uv tool install \
      --with "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python@main" \
      "git+https://github.com/posit-dev/posit-cli@main"
    ;;
  false | '') uv tool install "posit-cli>=0.1.1" ;;
  *) echo "::error::use-dev-cli must be 'true' or 'false', got '${USE_DEV_CLI}'."; exit 1 ;;
esac
