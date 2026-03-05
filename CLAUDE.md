# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitHub Actions monorepo (`posit-dev/connect-actions`) providing composite actions for deploying Python applications to [Posit Connect](https://posit.co/products/enterprise/connect/) from GitHub Actions. Currently in early beta; only Python app types supported via the `rsconnect` CLI.

## Repository Structure

Two composite GitHub Actions, each in its own directory:

- **`deploy/`** -- Deploys content to Connect. Production deploys on push to default branch; draft preview bundles on pull requests (with PR comment containing preview URL).
- **`cleanup-previews/`** -- Deletes draft bundles from Connect when a PR is closed. Finds bundle IDs by parsing PR comments left by the deploy action.

Each action has an `action.yml` plus a `scripts/` directory containing Bash and Python helper scripts. There is no build system, no tests, no CI, and no linting configuration.

## Architecture

### Shared config resolution pattern

Both actions resolve Connect server URL and content GUID through the same 3-tier priority:
1. Explicit action inputs (`connect-server`, `content-guid`)
2. Specified deployment TOML file (`deployment-file` input)
3. Auto-detection from `.posit/publish/deployments/` (must find exactly one `.toml`)

This logic lives in each action's `scripts/resolve-config.sh`, which calls `scripts/parse-deployment-toml.py` (run via `uv run --with toml`) to parse TOML files. The deploy version also extracts `entrypoint` from the TOML `[configuration]` section; the cleanup-previews version does not.

### Deploy flow (`deploy/`)

1. Install `uv` and `rsconnect` CLI
2. Resolve config (server, GUID, entrypoint) via `resolve-config.sh`
3. Generate `requirements.txt` from `pyproject.toml` if missing (`generate-requirements.sh`)
4. Query Connect API for `app_mode`, map to `rsconnect deploy` subcommand (shiny, fastapi, flask, dash, streamlit, bokeh)
5. Run `rsconnect deploy` with `--draft` flag for PRs
6. Extract content URL from deploy logs, set as action output
7. On PRs: comment preview URL via `actions/github-script`

### Cleanup flow (`cleanup-previews/`)

1. Install `uv`, resolve config
2. Via `actions/github-script`: read PR comments, extract bundle IDs from `draft/(\d+)` URL pattern, call Connect API `DELETE /__api__/v1/content/{guid}/bundles/{bundleId}` for each, post summary comment

## Key Dependencies (runtime in GitHub Actions)

- `uv` (via `astral-sh/setup-uv@v7`) -- Python package management and tool installation
- `rsconnect` (installed via `uv tool install rsconnect`) -- CLI for deploying to Connect
- `actions/github-script@v7` -- inline JavaScript for GitHub API interactions
- `jq`, `curl` -- used in `deploy.sh` to query the Connect API

## Development Notes

- All shell scripts use `set -euo pipefail`.
- `resolve-config.sh` and `parse-deployment-toml.py` are near-duplicates between the two actions (the deploy version extracts an additional `entrypoint` field).
- The `generate-requirements.sh` script has commented-out `uv.lock` support.
