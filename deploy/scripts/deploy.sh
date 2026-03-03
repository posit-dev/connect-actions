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
ENTRYPOINT_ARGS=""
if [ -n "${CONFIG_ENTRYPOINT:-}" ]; then
  ENTRYPOINT_ARGS="--entrypoint $CONFIG_ENTRYPOINT"
fi

# Deploy with --draft flag for pull requests
if [ "${GITHUB_EVENT_NAME:-}" = "pull_request" ]; then
  DRAFT="--draft"
  URL_PATTERN="Draft content URL:"
else
  DRAFT=""
  URL_PATTERN="Dashboard content URL:"
fi

rsconnect deploy $APP_TYPE $DRAFT --app-id "$CONTENT_GUID" $ENTRYPOINT_ARGS ${RSCONNECT_ARGS:-} . 2>&1 | tee deploy.log

# Extract URL from logs, stripping ANSI color codes
CONTENT_URL=$(grep "$URL_PATTERN" deploy.log | sed "s/.*$URL_PATTERN //" | sed 's/\x1b\[[0-9;]*m//g')
echo "content_url=$CONTENT_URL" >> "$GITHUB_OUTPUT"
