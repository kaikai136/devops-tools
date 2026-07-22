#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
RUNTIME_CONFIG="$REPO_ROOT/data/config/app.conf"

mkdir -p "$REPO_ROOT/data/config" "$REPO_ROOT/data/data" "$REPO_ROOT/data/media" "$REPO_ROOT/data/recordings"
if [ ! -f "$RUNTIME_CONFIG" ]; then
  cp "$DEPLOY_DIR/config/app.conf" "$RUNTIME_CONFIG"
  chmod 600 "$RUNTIME_CONFIG"
  echo "Created $RUNTIME_CONFIG from deploy/config/app.conf. Review it before production use."
fi
docker compose -f "$DEPLOY_DIR/docker-compose.yml" up -d --build
docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps
