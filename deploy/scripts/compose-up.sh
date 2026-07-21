#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"

mkdir -p "$REPO_ROOT/data" "$REPO_ROOT/media"
docker compose -f "$DEPLOY_DIR/docker-compose.yml" up -d --build
docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps
