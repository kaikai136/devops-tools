#!/usr/bin/env bash
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-172.16.0.99}"
DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt}"
APP_NAME="${APP_NAME:-devops-tools}"
REPO_URL="${REPO_URL:-https://github.com/kaikai136/devops-tools.git}"
BRANCH="${BRANCH:-main}"
APP_PORT="${APP_PORT:-8001}"

REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

quote() {
  printf "%q" "$1"
}

ssh "$REMOTE" \
  "DEPLOY_ROOT=$(quote "$DEPLOY_ROOT") APP_NAME=$(quote "$APP_NAME") REPO_URL=$(quote "$REPO_URL") BRANCH=$(quote "$BRANCH") APP_PORT=$(quote "$APP_PORT") DEPLOY_HOST=$(quote "$DEPLOY_HOST") bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

APP_DIR="${DEPLOY_ROOT%/}/${APP_NAME}"

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

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

cd "$APP_DIR"
mkdir -p data media

if [ ! -f .env ]; then
  if command -v openssl >/dev/null 2>&1; then
    SECRET_KEY="$(openssl rand -hex 32)"
  else
    SECRET_KEY="$(date +%s | sha256sum | awk '{print $1}')"
  fi

  cat > .env <<EOF
APP_PORT=${APP_PORT}
DJANGO_SECRET_KEY=${SECRET_KEY}
DJANGO_ALLOWED_HOSTS=${DEPLOY_HOST},localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://${DEPLOY_HOST}:${APP_PORT},http://localhost:${APP_PORT},http://127.0.0.1:${APP_PORT}
DJANGO_CORS_ALLOW_ALL_ORIGINS=0
EOF
fi

"${COMPOSE[@]}" up -d --build
"${COMPOSE[@]}" ps
REMOTE_SCRIPT
