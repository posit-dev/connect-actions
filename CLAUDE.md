# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitHub Actions monorepo (`posit-dev/connect-actions`) providing composite actions for deploying Python applications to [Posit Connect](https://posit.co/products/enterprise/connect/) from GitHub Actions. Currently in early beta; only Python app types supported. All Connect interaction goes through the [`posit` CLI](https://github.com/posit-dev/posit-cli), which mounts the full `rsconnect-python` command set under `posit connect` and adds a `gh api`-style `posit connect api` raw REST client.

## Repository Structure

Two composite GitHub Actions, each in its own directory:

- **`deploy/`** -- Deploys content to Connect. Production deploys on push to default branch; draft preview bundles on pull requests (with PR comment containing preview URL).
- **`cleanup-previews/`** -- Deletes draft bundles from Connect when a PR is closed. Finds bundle IDs by parsing PR comments left by the deploy action.

Each action has an `action.yml`; `deploy/` also has a `scripts/` directory of Bash helpers. Shared Bash helpers live in the repo-root `scripts/` directory (currently `login.sh`, used by both actions). Shared helper logic is migrating into a unit-tested Python package at the repo root (`src/connect_actions/`, see issue #35); config resolution already lives there. There is no linting configuration.

## Architecture

### Shared config resolution pattern

Both actions resolve Connect server URL and content GUID through the same 3-tier priority:
1. Explicit action inputs (`connect-server`, `content-guid`)
2. Specified deployment TOML file (`deployment-file` input)
3. Auto-detection from `.posit/publish/deployments/` (must find exactly one `.toml`)

This logic lives in `src/connect_actions/config.py` (`resolve_config()`), invoked by both actions via `uv run --project ${{ github.action_path }}/.. python -m connect_actions.cli resolve-config`. The pure functions parse TOML with stdlib `tomllib` and return a `Config`; the thin `cli.py` layer reads `INPUT_*` env vars and writes `GITHUB_OUTPUT`. Deploy uses the `entrypoint` field from the TOML `[configuration]` section (cleanup-previews ignores it) and its `extra_files`, derived from the `[configuration].files` array: every declared file minus the entrypoint, `requirements.txt`, and anything under `.posit/`. These are the supplementary sources a single-file entrypoint won't auto-bundle (e.g. a `.py` a Quarto document imports); the deploy step passes them to `posit connect deploy quarto` as trailing `EXTRA_FILES` positionals. `extra_files` is emitted as a newline-delimited multi-line `GITHUB_OUTPUT` value so filenames may contain spaces.

### Shared login pattern

Both actions authenticate once via `scripts/login.sh`, which logs the `posit` CLI in to the Connect server and stores the credential as the **default** server (rsconnect's server store, a file under `$HOME` that persists across composite steps). Two paths: with a `connect-api-key` it runs `posit connect add --set-default`; without one it fetches a GitHub OIDC token and runs `posit connect login`, which performs the RFC 8693 token exchange and stores the minted key. Trusted Publishing requires Connect >= 2026.07.0 with an Enhanced/Advanced license and a trusted publisher configured for the content; rather than pre-checking those (the license and configuration aren't detectable up front), `login.sh` lets `posit connect login` be the authoritative check and prints a clear error explaining the requirements if it fails. Downstream `posit connect deploy`/`api` calls therefore carry no server URL or key. Each action ends with an `if: always()` teardown step (`posit connect remove --name connect-actions`) so the credential doesn't outlive the action.

### Deploy flow (`deploy/`)

1. Install `uv` and the `posit` CLI
2. Resolve config (server, GUID, entrypoint, extra_files) via `connect_actions.cli resolve-config`
3. Log in to Connect (`scripts/login.sh`)
4. Determine app type: if a `manifest.json` is present use `manifest`; otherwise query `app_mode` from the Connect content record (`posit connect api`) and run `connect_actions.cli resolve-app-type`, which maps it to a `posit connect deploy` subcommand (shiny, fastapi, flask, dash, streamlit, bokeh, quarto) and sets `needs_quarto` (true only when the resolved subcommand is `quarto`). R app modes (`shiny`, `rmd-shiny`, `rmd-static`, `api`) can't be built from source here, so without a `manifest.json` this step fails fast with an R-tailored error (pointing to `rsconnect::writeManifest()`) rather than falling through to the Python requirements path
5. Set up Quarto (`quarto-dev/quarto-actions/setup`) only when `needs_quarto` is true — the `quarto` subcommand runs `quarto inspect` locally to build the manifest
6. Check Connect capabilities: read the server version (`posit connect api server_settings -q .version`) and run `connect_actions.cli check-deploy-features`, which fails fast if a draft is requested on a server older than 2025.07.0 and sets the `send_metadata` output (false on servers older than 2025.12.0, or when the version can't be read)
7. Generate `requirements.txt` from `pyproject.toml` if missing (`generate-requirements.sh`)
8. Run `posit connect deploy` with the resolved app type, `--draft` for PRs, passing `--metadata` only when `send_metadata` is true, and appending `extra_files` as trailing positionals for `quarto` deploys
9. Extract content URL from deploy logs, set as action output
10. On PRs: comment preview URL via `actions/github-script`
11. Log out (teardown)

### Cleanup flow (`cleanup-previews/`)

1. Install `uv` and the `posit` CLI
2. Via `actions/github-script`: read PR comments, extract server + GUID + bundle IDs from `draft/(\d+)` URL pattern (plus the accumulated `preview-bundles` metadata), emit a `targets` JSON
3. Log in to Connect (`scripts/login.sh`)
4. Bash step: delete each bundle with `posit connect api v1/content/{guid}/bundles/{id} -X DELETE`
5. Via `actions/github-script`: post a summary comment listing the deleted bundle IDs
6. Log out (teardown)

## Key Dependencies (runtime in GitHub Actions)

- `uv` (via `astral-sh/setup-uv@v7`) -- Python package management and tool installation
- `posit` CLI (installed via `uv tool install git+https://github.com/posit-dev/posit-cli`) -- wraps `rsconnect-python`; used for login, deploy, and raw Connect API requests (`posit connect api`)
- `actions/github-script@v9` -- inline JavaScript for GitHub API interactions (PR comments)
- `jq`, `curl` -- `curl` fetches the GitHub OIDC token in `login.sh`; `jq` parses the cleanup `targets` JSON

## Development Notes

- All shell scripts use `set -euo pipefail`.
- The `connect_actions` package targets `python>=3.11` (for stdlib `tomllib`); `uv` provisions the interpreter. Run tests with `uv run pytest`; the `unit` job in `.github/workflows/test.yml` does the same in CI.
- Keep all logic in pure, importable functions; `cli.py` is the only layer that touches env vars, `GITHUB_OUTPUT`, and subprocesses.
- The `generate-requirements.sh` script has commented-out `uv.lock` support.
