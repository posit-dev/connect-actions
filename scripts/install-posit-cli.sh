#!/usr/bin/env bash
set -euo pipefail

if [ "${USE_DEV_CLI:-}" = "true" ]; then
  uv tool install \
    --with "rsconnect-python @ git+https://github.com/posit-dev/rsconnect-python@main" \
    "git+https://github.com/posit-dev/posit-cli@main"
else
  uv tool install posit-cli
fi
