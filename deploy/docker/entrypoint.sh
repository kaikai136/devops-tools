#!/usr/bin/env sh
set -eu

mkdir -p /app/config /app/data /app/media /app/staticfiles

APP_CONFIG_FILE="${APP_CONFIG_FILE:-/app/config/app.conf}"

read_config_value() {
  key="$1"
  file="${2:-$APP_CONFIG_FILE}"
  if [ ! -f "$file" ]; then
    return 0
  fi

  awk -v key="$key" '
    /^[[:space:]]*($|#)/ { next }
    index($0, "=") == 0 { next }
    {
      line = $0
      sub(/^[[:space:]]*/, "", line)
      name = line
      sub(/=.*/, "", name)
      sub(/[[:space:]]*$/, "", name)
      if (name == key) {
        value = line
        sub(/^[^=]*=/, "", value)
        sub(/^[[:space:]]*/, "", value)
        sub(/[[:space:]]*$/, "", value)
        print value
        exit
      }
    }
  ' "$file"
}

SECRET_KEY_FILE="$(read_config_value DJANGO_SECRET_KEY_FILE)"
if [ -z "$SECRET_KEY_FILE" ]; then
  SECRET_KEY_FILE="/app/data/django-secret-key"
fi

CONFIG_SECRET_KEY="$(read_config_value DJANGO_SECRET_KEY)"
PERSISTED_SECRET=""

if [ -n "$CONFIG_SECRET_KEY" ]; then
  echo "Using DJANGO_SECRET_KEY from the config file."
elif [ -s "$SECRET_KEY_FILE" ]; then
  PERSISTED_SECRET="$(cat "$SECRET_KEY_FILE")"
  if [ -n "$PERSISTED_SECRET" ]; then
    echo "Using the persisted Django secret key."
  fi
fi

if [ -z "$CONFIG_SECRET_KEY" ] && [ -z "$PERSISTED_SECRET" ]; then
  umask 077
  secret_key_dir="$(dirname "$SECRET_KEY_FILE")"
  secret_key_tmp="${SECRET_KEY_FILE}.tmp.$$"
  trap 'rm -f "$secret_key_tmp"' EXIT HUP INT TERM
  mkdir -p "$secret_key_dir"
  python -c 'import secrets; print(secrets.token_urlsafe(64))' > "$secret_key_tmp"
  chmod 600 "$secret_key_tmp"
  mv "$secret_key_tmp" "$SECRET_KEY_FILE"
  trap - EXIT HUP INT TERM
  echo "Generated and persisted a new Django secret key."
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
