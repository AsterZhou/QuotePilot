#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${QUOTEPILOT_DOMAIN:?Set a domain with DNS pointing to this server}"
: "${MOI_WORKSPACE_ID:?Set workspace ID}"
: "${QP_SECRET_DIR:?Initialize secrets outside project and set absolute directory}"
command -v docker >/dev/null || { echo 'Docker and Compose are required on the deployment host'; exit 1; }
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 180
curl --fail --silent --show-error "https://${QUOTEPILOT_DOMAIN}/healthz"
echo
printf 'Deployment health passed. Complete external browser acceptance before claiming full workflow success.\n'
