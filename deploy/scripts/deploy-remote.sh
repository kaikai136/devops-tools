#!/usr/bin/env bash
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-172.16.0.99}"
DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt}"
APP_NAME="${APP_NAME:-devops-tools}"
REPO_URL="${REPO_URL:-https://github.com/kaikai136/devops-tools.git}"
BRANCH="${BRANCH:-main}"

REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

quote() {
  printf "%q" "$1"
}

ssh "$REMOTE" \
  "DEPLOY_ROOT=$(quote "$DEPLOY_ROOT") APP_NAME=$(quote "$APP_NAME") REPO_URL=$(quote "$REPO_URL") BRANCH=$(quote "$BRANCH") bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

APP_DIR="${DEPLOY_ROOT%/}/${APP_NAME}"
CONFIG_PATH="data/config/app.conf"
CONFIG_BACKUP=""
CONFIG_RESTORED=0

cleanup_config_backup() {
  if [ -n "$CONFIG_BACKUP" ] && [ -f "$CONFIG_BACKUP" ]; then
    if [ "$CONFIG_RESTORED" -ne 1 ] && [ -d "$APP_DIR" ]; then
      mkdir -p "$(dirname "$APP_DIR/$CONFIG_PATH")"
      cp "$CONFIG_BACKUP" "$APP_DIR/$CONFIG_PATH"
      chmod 600 "$APP_DIR/$CONFIG_PATH"
    fi
    rm -f "$CONFIG_BACKUP"
  fi
}
trap cleanup_config_backup EXIT HUP INT TERM

command -v git >/dev/null 2>&1 || { echo "git is required on the target host."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker is required on the target host."; exit 1; }

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "docker compose or docker-compose is required on the target host."
  exit 1
fi

mkdir -p "$DEPLOY_ROOT"

if [ -e "$APP_DIR" ] && [ ! -d "$APP_DIR/.git" ]; then
  echo "$APP_DIR already exists but is not a git repository."
  exit 1
fi

if [ -d "$APP_DIR/.git" ] && [ -f "$APP_DIR/$CONFIG_PATH" ]; then
  CONFIG_BACKUP="$(mktemp)"
  cp "$APP_DIR/$CONFIG_PATH" "$CONFIG_BACKUP"
  chmod 600 "$CONFIG_BACKUP"
fi

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

cd "$APP_DIR"
mkdir -p data/config data/data data/media data/recordings

if [ -n "$CONFIG_BACKUP" ]; then
  cp "$CONFIG_BACKUP" "$CONFIG_PATH"
  chmod 600 "$CONFIG_PATH"
  CONFIG_RESTORED=1
elif [ ! -f "$CONFIG_PATH" ]; then
  cp deploy/config/app.conf "$CONFIG_PATH"
  chmod 600 "$CONFIG_PATH"
fi

"${COMPOSE[@]}" -f deploy/docker-compose.yml up -d --build
"${COMPOSE[@]}" -f deploy/docker-compose.yml ps
REMOTE_SCRIPT
