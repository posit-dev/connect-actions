#!/usr/bin/env bash
# Log the `posit` CLI in to a Posit Connect server so that downstream
# `posit connect` commands (deploy, api, ...) use the stored credential as the
# default server, without any step having to carry the server URL or key around.
#
# Two auth paths, chosen by whether an API key is provided:
#   * CONNECT_API_KEY set -> save it with `posit connect add`.
#   * otherwise           -> exchange a GitHub Actions OIDC token for a
#                            short-lived key with `posit connect login`, which
#                            performs the RFC 8693 token exchange and stores the
#                            minted key. This requires the workflow to grant
#                            'id-token: write' and a trusted publisher to be
#                            configured for the content on Connect.
#
# Required env:
#   CONNECT_SERVER  Connect server URL (e.g. https://connect.example.com)
# Optional env:
#   CONNECT_API_KEY  Connect API key. If set, used directly (no OIDC exchange).
#   OIDC_AUDIENCE    Audience to request for the OIDC token. Must match the
#                    trusted publisher's configured audience on Connect, whose
#                    default is "connect" (default: connect).

set -euo pipefail

# Fixed nickname for the credential this action stores. Downstream commands rely
# on the default server, so the name only matters for the matching logout step.
NAME="connect-actions"

CONNECT_SERVER="${CONNECT_SERVER:-}"
CONNECT_SERVER="${CONNECT_SERVER%/}"

if [ -z "$CONNECT_SERVER" ]; then
  echo "::error::connect-server is required to log in to Connect."
  exit 1
fi

if [ -n "${CONNECT_API_KEY:-}" ]; then
  posit connect add --name "$NAME" --server "$CONNECT_SERVER" \
    --api-key "$CONNECT_API_KEY" --set-default
  exit 0
fi

# No API key: request a GitHub Actions OIDC token and let the CLI exchange it.
# These env vars are only populated when the workflow (or job) grants
# `id-token: write`; their absence is the most common misconfiguration, so call
# it out explicitly.
if [ -z "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" ] || [ -z "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ]; then
  echo "::error::Unable to request a GitHub OIDC token. Either grant 'id-token: write' permission to your workflow:

  permissions:
    id-token: write

or provide connect-api-key directly."
  exit 1
fi

AUDIENCE="${OIDC_AUDIENCE:-connect}"
ID_TOKEN=$(curl -sf --get \
  -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  --data-urlencode "audience=$AUDIENCE" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL" | jq -r '.value // empty')

if [ -z "$ID_TOKEN" ]; then
  echo "::error::Failed to obtain a GitHub OIDC token from the Actions runtime."
  exit 1
fi
echo "::add-mask::$ID_TOKEN"

# Hand the token to the CLI via the environment rather than an argument, so it
# never lands in process args or logs. `posit connect login` discovers Connect's
# token-exchange endpoint, mints the key, validates it, and stores it as the
# default server credential.
export CONNECT_IDENTITY_TOKEN="$ID_TOKEN"
if ! posit connect login --server "$CONNECT_SERVER" --name "$NAME"; then
  echo "::error::Trusted Publishing (OIDC) login failed. It requires Connect 2026.07.0 or newer with an Enhanced or Advanced license and a trusted publisher configured for this content. If your server doesn't meet these requirements, provide connect-api-key instead."
  exit 1
fi
