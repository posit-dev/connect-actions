#!/bin/bash
# Deploy to Posit Connect using rsconnect
# Required env vars: CONNECT_SERVER, CONNECT_API_KEY, CONTENT_GUID
# Optional env vars: CONFIG_ENTRYPOINT, GITHUB_EVENT_NAME, RSCONNECT_ARGS

set -euo pipefail

# Get app_mode from Connect API
echo "Fetching app mode from Connect API..."
CONTENT_INFO=$(curl -s -H "Authorization: Key $CONNECT_API_KEY" \
  "$CONNECT_SERVER/__api__/v1/content/$CONTENT_GUID")

APP_MODE=$(echo "$CONTENT_INFO" | jq -r '.app_mode // empty')

if [ -z "$APP_MODE" ]; then
  echo "Error: Could not determine app_mode from Connect API"
  echo "Response: $CONTENT_INFO"
  exit 1
fi

# Map Connect app_mode to rsconnect deploy subcommand
case "$APP_MODE" in
  "python-shiny") APP_TYPE="shiny" ;;
  "python-fastapi") APP_TYPE="fastapi" ;;
  "python-flask") APP_TYPE="flask" ;;
  "python-dash") APP_TYPE="dash" ;;
  "python-streamlit") APP_TYPE="streamlit" ;;
  "python-bokeh") APP_TYPE="bokeh" ;;
  "quarto-shiny") APP_TYPE="shiny" ;;
  *) APP_TYPE="$APP_MODE" ;;
esac

echo "Detected app type: $APP_TYPE (from app_mode: $APP_MODE)"

# Build entrypoint args if available
ENTRYPOINT_ARGS=()
if [ -n "${CONFIG_ENTRYPOINT:-}" ]; then
  ENTRYPOINT_ARGS=(--entrypoint "$CONFIG_ENTRYPOINT")
fi

# Deploy with --draft flag for pull requests
DRAFT_ARGS=()
if [ "${GITHUB_EVENT_NAME:-}" = "pull_request" ]; then
  DRAFT_ARGS=(--draft)
  URL_PATTERN="Draft content URL:"
else
  URL_PATTERN="Dashboard content URL:"
fi

# Build metadata arguments (using array to handle values with spaces)
METADATA_ARGS=()
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

# shellcheck disable=SC2086
rsconnect deploy "$APP_TYPE" "${DRAFT_ARGS[@]}" --app-id "$CONTENT_GUID" "${ENTRYPOINT_ARGS[@]}" "${METADATA_ARGS[@]}" ${RSCONNECT_ARGS:-} . 2>&1 | tee deploy.log

# Extract URL from logs, stripping ANSI color codes
CONTENT_URL=$(grep "$URL_PATTERN" deploy.log | sed "s/.*$URL_PATTERN //" | sed 's/\x1b\[[0-9;]*m//g')
echo "content_url=$CONTENT_URL" >> "$GITHUB_OUTPUT"
