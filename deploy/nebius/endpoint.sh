#!/usr/bin/env bash
# Deploy the Mortgage OS as a Nebius Serverless AI endpoint (CPU only: inference is Nemotron on Token Factory).
# Prereqs: Nebius CLI installed and configured (nebius profile), a subnet ID, and the image published
# (GitHub Actions "container image" workflow -> ghcr.io/alenzacodes/decision-ladder:latest, package made public).
#   NEBIUS_API_KEY=... TAVILY_API_KEY=... SUBNET_ID=... bash deploy/nebius/endpoint.sh
set -euo pipefail
: "${NEBIUS_API_KEY:?set NEBIUS_API_KEY (Token Factory key)}"
: "${SUBNET_ID:?set SUBNET_ID (nebius vpc subnet list)}"
IMAGE=${IMAGE:-ghcr.io/alenzacodes/decision-ladder:latest}
NAME=${NAME:-decision-ladder}
AUTH_TOKEN=${AUTH_TOKEN:-$(openssl rand -hex 32)}

nebius ai endpoint create \
  --name "$NAME" \
  --image "$IMAGE" \
  --platform cpu-d3 \
  --preset 4vcpu-16gb \
  --container-port 8000 \
  --env "NEBIUS_API_KEY=${NEBIUS_API_KEY}" \
  --env "TAVILY_API_KEY=${TAVILY_API_KEY:-}" \
  --env "DL_RATE_PER_MIN=12" \
  --public \
  --auth token \
  --token "$AUTH_TOKEN" \
  --subnet-id "$SUBNET_ID"

ENDPOINT_ID=$(nebius ai endpoint get-by-name --name "$NAME" --format jsonpath='{.metadata.id}')
echo "endpoint id: $ENDPOINT_ID (wait until it is RUNNING, then:)"
echo "  nebius ai endpoint get $ENDPOINT_ID --format json | jq -r '.status.public_endpoints[] | select(startswith(\"https://\"))'"
echo "  curl -H \"Authorization: Bearer $AUTH_TOKEN\" <URL>/api/health"
