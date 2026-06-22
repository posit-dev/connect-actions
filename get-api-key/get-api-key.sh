#!/usr/bin/env bash
set -euo pipefail

# Exchange a GitHub Actions OIDC token for a short-lived Posit Connect API key
# using Connect's trusted-publishing token exchange.
#
# This talks to Connect's OAuth server token endpoint (POST /oauth/v1/token)
# with an RFC 8693 token exchange. Connect verifies the OIDC token and, if it
# matches a service principal that a content owner has bound as a "trusted
# publisher", mints an ephemeral machine API key scoped to that content.
#
# Required env:
#   CONNECT_SERVER  Connect server URL (e.g. https://connect.example.com)
# Optional env:
#   OIDC_AUDIENCE   Audience to request for the OIDC token. Must match the
#                   trusted publisher's configured audience on Connect, whose
#                   default is "connect" (default: connect).
#
# On success, writes `api_key=<key>` to $GITHUB_OUTPUT (masked).

CONNECT_SERVER="${CONNECT_SERVER:-}"
CONNECT_SERVER="${CONNECT_SERVER%/}"
AUDIENCE="${OIDC_AUDIENCE:-connect}"

if [ -z "$CONNECT_SERVER" ]; then
  echo "::error::connect-server is required to exchange an OIDC token for an API key."
  exit 1
fi

# 1. Request an OIDC token from GitHub. These env vars are only populated when
# the workflow (or job) grants `id-token: write`; their absence is the single
# most common misconfiguration, so call it out explicitly.
if [ -z "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" ] || [ -z "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ]; then
  echo "::error::Unable to request a GitHub OIDC token. Either grant 'id-token: write' permission to your workflow:

  permissions:
    id-token: write

or provide connect-api-key directly."
  exit 1
fi

ID_TOKEN=$(curl -sf --get \
  -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  --data-urlencode "audience=$AUDIENCE" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL" | jq -r '.value // empty')

if [ -z "$ID_TOKEN" ]; then
  echo "::error::Failed to obtain a GitHub OIDC token from the Actions runtime."
  exit 1
fi
echo "::add-mask::$ID_TOKEN"

# 2. Exchange the OIDC token at Connect's OAuth token endpoint.
TOKEN_URL="$CONNECT_SERVER/oauth/v1/token"

HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$TOKEN_URL" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=urn:ietf:params:oauth:grant-type:token-exchange" \
  --data-urlencode "subject_token_type=urn:ietf:params:oauth:token-type:id_token" \
  --data-urlencode "requested_token_type=urn:ietf:params:oauth:token-type:access_token" \
  --data-urlencode "subject_token=$ID_TOKEN")

HTTP_BODY=$(printf '%s' "$HTTP_RESPONSE" | sed '$d')
HTTP_STATUS=$(printf '%s' "$HTTP_RESPONSE" | tail -n1)

if [ "$HTTP_STATUS" = "200" ]; then
  API_KEY=$(printf '%s' "$HTTP_BODY" | jq -r '.access_token // empty')
  if [ -z "$API_KEY" ]; then
    echo "::error::Connect returned HTTP 200 but no access_token. Provide connect-api-key directly."
    exit 1
  fi
  echo "::add-mask::$API_KEY"
  echo "api_key=$API_KEY" >> "$GITHUB_OUTPUT"
  echo "Obtained a Connect API key via OIDC token exchange."
  exit 0
fi

# Connect's OAuth server reports failures as RFC 6749 JSON:
# {"error": "...", "error_description": "..."}. Parse it to tell a
# misconfiguration apart from "no trusted publisher is set up".
ERROR_CODE=$(printf '%s' "$HTTP_BODY" | jq -r '.error // empty' 2>/dev/null || true)
ERROR_DESC=$(printf '%s' "$HTTP_BODY" | jq -r '.error_description // empty' 2>/dev/null || true)

case "$HTTP_STATUS" in
  404)
    echo "::error::Connect has no OIDC token-exchange endpoint at $TOKEN_URL. This server is likely too old to support trusted publishing. Upgrade Connect, or provide connect-api-key directly."
    ;;
  400)
    case "$ERROR_CODE" in
      unsupported_grant_type)
        echo "::error::This Connect server's OAuth service does not support token exchange, so it is likely too old to support trusted publishing. Upgrade Connect, or provide connect-api-key directly."
        ;;
      invalid_grant)
        # The OIDC token verified but resolved to no (or more than one)
        # service principal. Disambiguate on the description Connect returns.
        case "$ERROR_DESC" in
          *[Aa]mbiguous*)
            echo "::error::The OIDC token matched more than one trusted publisher on Connect ($ERROR_DESC). This is a misconfiguration on the Connect server; resolve the duplicate trusted publishers, or provide connect-api-key directly."
            ;;
          *verify*|*[Vv]erification*)
            echo "::error::Connect could not verify the OIDC token ($ERROR_DESC). Check the server clock and the OIDC issuer configuration, or provide connect-api-key directly."
            ;;
          *)
            echo "::error::Connect did not recognize this workflow as a trusted publisher ($ERROR_DESC). Confirm a trusted publisher has been configured for this repository on the target content, and that the requested audience ('$AUDIENCE') matches it. Otherwise, provide connect-api-key directly."
            ;;
        esac
        ;;
      invalid_request)
        echo "::error::Connect rejected the token-exchange request as malformed ($ERROR_DESC). This usually indicates a bug or misconfiguration in this action. Otherwise, provide connect-api-key directly."
        ;;
      *)
        echo "::error::Token exchange failed (HTTP 400${ERROR_CODE:+, $ERROR_CODE}${ERROR_DESC:+: $ERROR_DESC}). Provide connect-api-key directly."
        ;;
    esac
    ;;
  *)
    echo "::error::Token exchange failed (HTTP $HTTP_STATUS${ERROR_DESC:+: $ERROR_DESC}). Provide connect-api-key directly."
    ;;
esac
exit 1
