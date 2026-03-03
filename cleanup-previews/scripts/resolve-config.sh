#!/bin/bash
# Resolve deployment configuration from inputs or deployment file
# Outputs: connect_server, content_guid

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If server and guid provided directly, use them
if [ -n "${INPUT_CONNECT_SERVER:-}" ] && [ -n "${INPUT_CONTENT_GUID:-}" ]; then
  echo "connect_server=$INPUT_CONNECT_SERVER" >> "$GITHUB_OUTPUT"
  echo "content_guid=$INPUT_CONTENT_GUID" >> "$GITHUB_OUTPUT"
  echo "Using provided connect-server and content-guid"
  exit 0
fi

# Determine which deployment file to use
DEPLOYMENT_FILE="${INPUT_DEPLOYMENT_FILE:-}"
if [ -z "$DEPLOYMENT_FILE" ]; then
  # Auto-detect from .posit/publish/deployments/
  if [ -d ".posit/publish/deployments" ]; then
    TOML_FILES=($(find .posit/publish/deployments -name "*.toml" -type f))
    if [ ${#TOML_FILES[@]} -eq 0 ]; then
      echo "Error: No deployment files found in .posit/publish/deployments/ and connect-server/content-guid not provided"
      exit 1
    elif [ ${#TOML_FILES[@]} -eq 1 ]; then
      DEPLOYMENT_FILE="${TOML_FILES[0]}"
      echo "Auto-detected deployment file: $DEPLOYMENT_FILE"
    else
      echo "Error: Multiple deployment files found in .posit/publish/deployments/:"
      printf '  %s\n' "${TOML_FILES[@]}"
      echo "Please specify one with the deployment-file input"
      exit 1
    fi
  else
    echo "Error: No .posit/publish/deployments/ directory and connect-server/content-guid not provided"
    exit 1
  fi
fi

if [ ! -f "$DEPLOYMENT_FILE" ]; then
  echo "Error: Deployment file not found: $DEPLOYMENT_FILE"
  exit 1
fi

echo "Reading configuration from: $DEPLOYMENT_FILE"

# Parse TOML using Python
export DEPLOYMENT_FILE
uv run --with toml python3 "$SCRIPT_DIR/parse-deployment-toml.py" >> "$GITHUB_OUTPUT"
