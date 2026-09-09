#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
test -f .env
test "$#" -eq 2
BACKEND_IMAGE=$1
FRONTEND_IMAGE=$2
export BACKEND_IMAGE FRONTEND_IMAGE
docker compose -f compose.production.yml pull
previous_backend=''
previous_frontend=''
if test -f .release; then
  previous_backend=$(sed -n '1p' .release)
  previous_frontend=$(sed -n '2p' .release)
fi
if docker compose -f compose.production.yml up -d --wait --wait-timeout 180; then
  printf '%s\n%s\n' "$BACKEND_IMAGE" "$FRONTEND_IMAGE" > .release
else
  if test -n "$previous_backend" && test -n "$previous_frontend"; then
    BACKEND_IMAGE=$previous_backend FRONTEND_IMAGE=$previous_frontend \
      docker compose -f compose.production.yml up -d --wait --wait-timeout 180
  fi
  exit 1
fi
