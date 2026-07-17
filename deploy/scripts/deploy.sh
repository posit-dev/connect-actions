#!/bin/bash
# Deploy to Posit Connect using the `posit` CLI. Assumes a prior login step has
# stored the server credential as the default (see scripts/login.sh), so no
# server URL or API key is passed here.
# Required env vars: CONTENT_GUID
# Optional env vars: CONFIG_ENTRYPOINT, DRAFT, GITHUB_EVENT_NAME, RSCONNECT_ARGS

set -euo pipefail

# If a manifest.json is present, deploy with it directly. The manifest already
# declares app type, entrypoint, and dependencies, so we skip the Connect
# app_mode lookup and ignore CONFIG_ENTRYPOINT.
ENTRYPOINT_ARGS=()
if [ -f "manifest.json" ]; then
  echo "Found manifest.json; deploying with posit connect deploy manifest"
  APP_TYPE="manifest"
  DEPLOY_TARGET="manifest.json"
else
  DEPLOY_TARGET="."

  echo "Fetching app mode from Connect API..."
  APP_MODE=$(posit connect api "v1/content/$CONTENT_GUID" -q '.app_mode // empty')

  if [ -z "$APP_MODE" ]; then
    echo "Error: Could not determine app_mode from Connect API for content $CONTENT_GUID"
    exit 1
  fi

  # Map Connect app_mode to posit connect deploy subcommand
  case "$APP_MODE" in
    "python-shiny") APP_TYPE="shiny" ;;
    "python-fastapi") APP_TYPE="fastapi" ;;
    "python-flask") APP_TYPE="flask" ;;
    "python-dash") APP_TYPE="dash" ;;
    "python-streamlit") APP_TYPE="streamlit" ;;
    "python-bokeh") APP_TYPE="bokeh" ;;
    "quarto-static") APP_TYPE="quarto" ;;
    "quarto-shiny") APP_TYPE="shiny" ;;
    *) APP_TYPE="$APP_MODE" ;;
  esac

  echo "Detected app type: $APP_TYPE (from app_mode: $APP_MODE)"

  if [ -n "${CONFIG_ENTRYPOINT:-}" ]; then
    ENTRYPOINT_ARGS=(--entrypoint "$CONFIG_ENTRYPOINT")
  fi
fi

# Deploy as a draft when requested. The DRAFT env var is set from the action's
# `draft` input, which defaults to true on pull_request events. Draft bundles
# are uploaded but not activated, so the previously active bundle keeps serving.
DRAFT_ARGS=()
if [ "${DRAFT:-}" = "true" ]; then
  DRAFT_ARGS=(--draft)
  URL_PATTERN="Draft content URL:"
else
  URL_PATTERN="Dashboard content URL:"
fi

# Build metadata arguments (using array to handle values with spaces).
# --metadata routes through rsconnect's multipart bundle-upload API, which
# requires Connect >= 2025.12.0. The "Check Connect capabilities" step sets
# SEND_METADATA=false on older servers (or when the version can't be read), so
# we deploy without the git provenance metadata rather than failing the upload.
METADATA_ARGS=()
if [ "${SEND_METADATA:-true}" = "true" ]; then
  METADATA_ARGS+=(--metadata "source=github-actions")
  if [ -n "${GITHUB_SHA:-}" ]; then
    METADATA_ARGS+=(--metadata "source_commit=$GITHUB_SHA")
  fi
  if [ -n "${GITHUB_ACTOR:-}" ]; then
    METADATA_ARGS+=(--metadata "source_author=$GITHUB_ACTOR")
  fi
  if [ -n "${GITHUB_RUN_URL:-}" ]; then
    METADATA_ARGS+=(--metadata "source_github_actions_run=$GITHUB_RUN_URL")
  fi

  if [ "${GITHUB_EVENT_NAME:-}" = "pull_request" ]; then
    if [ -n "${PR_HEAD_REF:-}" ]; then
      METADATA_ARGS+=(--metadata "source_branch=$PR_HEAD_REF")
    fi
    if [ -n "${PR_NUMBER:-}" ]; then
      METADATA_ARGS+=(--metadata "source_pull_request=$PR_NUMBER")
    fi
    if [ -n "${PR_TITLE:-}" ]; then
      METADATA_ARGS+=(--metadata "source_description=${PR_TITLE} (#${PR_NUMBER})")
    fi
  else
    if [ -n "${GITHUB_REF_NAME:-}" ]; then
      METADATA_ARGS+=(--metadata "source_branch=$GITHUB_REF_NAME")
    fi
    if [ -n "${COMMIT_MESSAGE:-}" ]; then
      # Use only the first line of the commit message
      FIRST_LINE=$(printf '%s\n' "$COMMIT_MESSAGE" | head -n 1)
      METADATA_ARGS+=(--metadata "source_description=${FIRST_LINE}")
    fi
  fi
fi

# shellcheck disable=SC2086
posit connect deploy "$APP_TYPE" "${DRAFT_ARGS[@]}" --app-id "$CONTENT_GUID" "${ENTRYPOINT_ARGS[@]}" "${METADATA_ARGS[@]}" ${RSCONNECT_ARGS:-} "$DEPLOY_TARGET" 2>&1 | tee deploy.log

# Extract URL from logs, stripping ANSI color codes
CONTENT_URL=$(grep "$URL_PATTERN" deploy.log | sed "s/.*$URL_PATTERN //" | sed 's/\x1b\[[0-9;]*m//g')
echo "content_url=$CONTENT_URL" >> "$GITHUB_OUTPUT"
