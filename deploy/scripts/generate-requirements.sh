#!/bin/bash
# Generate requirements.txt if it doesn't exist

set -euo pipefail

if [ -f "requirements.txt" ]; then
  echo "requirements.txt already exists, not regenerating."
  exit 0
fi

# if [ -f "uv.lock" ]; then
#   echo "uv.lock found, generating requirements.txt from uv.lock..."
#   uv export --format requirements.txt --output-file requirements.txt
# el
if [ -f "pyproject.toml" ]; then
  echo "pyproject.toml found, generating requirements.txt from pyproject.toml..."
  uv pip compile pyproject.toml -o requirements.txt
else
  echo "No uv.lock or pyproject.toml file found. Please run 'uv sync' to generate uv.lock or create a pyproject.toml before deploying."
  exit 1
fi
