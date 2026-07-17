#!/bin/bash
# Deploy to Posit Connect using the `posit` CLI. Assumes a prior login step has
# stored the server credential as the default (see scripts/login.sh), so no
# server URL or API key is passed here.
# Required env vars: CONTENT_GUID, APP_TYPE (resolved by the "Determine app type"
#   step: a `posit connect deploy` subcommand, or "manifest")
# Optional env vars: CONFIG_ENTRYPOINT, DRAFT, GITHUB_EVENT_NAME, RSCONNECT_ARGS

set -euo pipefail

# The app type is resolved upstream (from a manifest.json or the Connect content
# record's app_mode) so the action can set up Quarto before this step runs.
ENTRYPOINT_ARGS=()
if [ "$APP_TYPE" = "manifest" ]; then
  # A manifest.json already declares app type, entrypoint, and dependencies, so
  # we deploy it directly and ignore CONFIG_ENTRYPOINT.
  echo "Deploying with posit connect deploy manifest"
  DEPLOY_TARGET="manifest.json"
else
  DEPLOY_TARGET="."
  echo "Deploying app type: $APP_TYPE"

  if [ -n "${CONFIG_ENTRYPOINT:-}" ]; then
    # `posit connect deploy quarto` takes the entrypoint document as its
    # FILE_OR_DIRECTORY positional argument and has no --entrypoint option;
    # every other subcommand uses --entrypoint.
    if [ "$APP_TYPE" = "quarto" ]; then
      DEPLOY_TARGET="$CONFIG_ENTRYPOINT"
    else
      ENTRYPOINT_ARGS=(--entrypoint "$CONFIG_ENTRYPOINT")
    fi
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
