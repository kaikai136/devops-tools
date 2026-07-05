#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  APP_PORT="${APP_PORT:-8001}"
  DEPLOY_HOST="${DEPLOY_HOST:-172.16.0.99}"

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

docker compose up -d --build
docker compose ps
