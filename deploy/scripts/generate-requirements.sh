#!/bin/bash
# Generate requirements.txt from a uv.lock or pyproject.toml when it is absent.
#
# Which branch runs depends only on the files in the working directory. A
# missing dependency source is not an error: `posit connect deploy` is what
# decides whether the content needs a requirements.txt (a jupyter-engine Quarto
# doc does; a knitr-engine one and a Node.js app do not) and reports it if so.

set -euo pipefail

if [ -f "manifest.json" ]; then
  echo "manifest.json found, dependencies will be read from it; skipping requirements.txt generation."
  exit 0
fi

if [ -f "requirements.txt" ]; then
  echo "requirements.txt already exists, not regenerating."
  exit 0
fi

if [ -f "uv.lock" ]; then
  # Prefer the lockfile when present: it pins an exact, reproducible resolution,
  # whereas `uv pip compile pyproject.toml` re-resolves at deploy time.
  # --no-hashes: Connect resolves and installs the dependencies itself; hash
  #   lines force pip into hash-checking mode, which the server rejects.
  # --no-emit-project: a packaged project exports itself as a local path
  #   dependency, which Connect cannot install.
  # --frozen: export exactly the committed lockfile; never re-resolve (which
  #   would silently deploy newer versions when uv.lock is stale).
  echo "uv.lock found, exporting requirements.txt from uv.lock..."
  uv export --format requirements-txt --no-hashes --no-emit-project --frozen -o requirements.txt
elif [ -f "pyproject.toml" ]; then
  echo "pyproject.toml found, generating requirements.txt from pyproject.toml..."
  uv pip compile pyproject.toml -o requirements.txt
else
  echo "No uv.lock or pyproject.toml file found; nothing to generate."
fi
