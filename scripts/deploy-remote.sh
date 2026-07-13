#!/usr/bin/env bash
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-172.16.0.99}"
DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt}"
APP_NAME="${APP_NAME:-devops-tools}"
REPO_URL="${REPO_URL:-https://github.com/kaikai136/devops-tools.git}"
BRANCH="${BRANCH:-main}"
APP_PORT_OVERRIDE="${APP_PORT:-}"

REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

quote() {
  printf "%q" "$1"
}

ssh "$REMOTE" \
  "DEPLOY_ROOT=$(quote "$DEPLOY_ROOT") APP_NAME=$(quote "$APP_NAME") REPO_URL=$(quote "$REPO_URL") BRANCH=$(quote "$BRANCH") APP_PORT_OVERRIDE=$(quote "$APP_PORT_OVERRIDE") bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

APP_DIR="${DEPLOY_ROOT%/}/${APP_NAME}"
ENV_BACKUP=""
ENV_RESTORED=0

cleanup_env_backup() {
  if [ -n "$ENV_BACKUP" ] && [ -f "$ENV_BACKUP" ]; then
    if [ "$ENV_RESTORED" -ne 1 ] && [ -d "$APP_DIR" ]; then
      cp "$ENV_BACKUP" "$APP_DIR/.env"
      chmod 600 "$APP_DIR/.env"
    fi
    rm -f "$ENV_BACKUP"
  fi
}
trap cleanup_env_backup EXIT HUP INT TERM

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

if [ -d "$APP_DIR/.git" ] && [ -f "$APP_DIR/.env" ]; then
  ENV_BACKUP="$(mktemp)"
  cp "$APP_DIR/.env" "$ENV_BACKUP"
  chmod 600 "$ENV_BACKUP"
  if git -C "$APP_DIR" ls-files --error-unmatch .env >/dev/null 2>&1; then
    git -C "$APP_DIR" checkout -- .env
  else
    rm -f "$APP_DIR/.env"
  fi
fi

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

cd "$APP_DIR"
mkdir -p data media

if [ -n "$ENV_BACKUP" ]; then
  cp "$ENV_BACKUP" .env
  chmod 600 .env
  ENV_RESTORED=1
fi

if [ -n "$APP_PORT_OVERRIDE" ]; then
  export APP_PORT="$APP_PORT_OVERRIDE"
fi

"${COMPOSE[@]}" up -d --build
"${COMPOSE[@]}" ps
REMOTE_SCRIPT
