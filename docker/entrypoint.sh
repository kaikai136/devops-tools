#!/usr/bin/env sh
set -eu

mkdir -p /app/data /app/media /app/staticfiles

SECRET_KEY_FILE="${DJANGO_SECRET_KEY_FILE:-/app/data/django-secret-key}"

if [ -n "${DJANGO_SECRET_KEY:-}" ]; then
  echo "Using DJANGO_SECRET_KEY from the environment."
elif [ -s "$SECRET_KEY_FILE" ]; then
  DJANGO_SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
  if [ -n "$DJANGO_SECRET_KEY" ]; then
    echo "Using the persisted Django secret key."
  fi
fi

if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  umask 077
  secret_key_dir="$(dirname "$SECRET_KEY_FILE")"
  secret_key_tmp="${SECRET_KEY_FILE}.tmp.$$"
  trap 'rm -f "$secret_key_tmp"' EXIT HUP INT TERM
  mkdir -p "$secret_key_dir"
  DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
  printf '%s\n' "$DJANGO_SECRET_KEY" > "$secret_key_tmp"
  chmod 600 "$secret_key_tmp"
  mv "$secret_key_tmp" "$SECRET_KEY_FILE"
  trap - EXIT HUP INT TERM
  echo "Generated and persisted a new Django secret key."
fi

export DJANGO_SECRET_KEY

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
