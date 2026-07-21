#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DEPLOY_SCRIPT="$REPO_ROOT/deploy/scripts/deploy-remote.sh"
TEST_ROOT="$(mktemp -d)"
SOURCE_REPO="$TEST_ROOT/source"
ORIGIN_REPO="$TEST_ROOT/origin.git"
DEPLOY_ROOT="$TEST_ROOT/deploy"
APP_NAME="app"
APP_DIR="$DEPLOY_ROOT/$APP_NAME"
CONFIG_PATH="deploy/config/app.conf"
FAKE_BIN="$TEST_ROOT/bin"
DOCKER_LOG="$TEST_ROOT/docker.log"
CUSTOM_CONFIG="$TEST_ROOT/custom-app.conf"

cleanup() {
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$SOURCE_REPO" "$FAKE_BIN" "$DEPLOY_ROOT"
git init --bare --quiet "$ORIGIN_REPO"
git -C "$SOURCE_REPO" init --quiet
git -C "$SOURCE_REPO" config user.name 'Deployment Test'
git -C "$SOURCE_REPO" config user.email 'deployment-test@example.invalid'
git -C "$SOURCE_REPO" checkout -b main --quiet
printf '%s\n' 'initial' > "$SOURCE_REPO/README.md"
mkdir -p "$SOURCE_REPO/deploy/config"
cat > "$SOURCE_REPO/$CONFIG_PATH" <<'CONF'
DJANGO_SECRET_KEY=
DJANGO_ALLOWED_HOSTS=*
CONF
git -C "$SOURCE_REPO" add README.md "$CONFIG_PATH"
git -C "$SOURCE_REPO" commit --quiet -m 'initial'
git -C "$SOURCE_REPO" remote add origin "$ORIGIN_REPO"
git -C "$SOURCE_REPO" push --quiet -u origin main
git --git-dir="$ORIGIN_REPO" symbolic-ref HEAD refs/heads/main
git clone --quiet "$ORIGIN_REPO" "$APP_DIR"

cat > "$CUSTOM_CONFIG" <<'CONF'
DJANGO_SECRET_KEY=private-existing-secret
DJANGO_ALLOWED_HOSTS=ops.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://ops.example.com
CONF
cp "$CUSTOM_CONFIG" "$APP_DIR/$CONFIG_PATH"

cat > "$SOURCE_REPO/$CONFIG_PATH" <<'CONF'
DJANGO_SECRET_KEY=
DJANGO_SECRET_KEY_FILE=/app/data/django-secret-key
DJANGO_ALLOWED_HOSTS=*
CONF
git -C "$SOURCE_REPO" add "$CONFIG_PATH"
git -C "$SOURCE_REPO" commit --quiet -m 'track safe default config'
git -C "$SOURCE_REPO" push --quiet
expected_head="$(git -C "$SOURCE_REPO" rev-parse HEAD)"

cat > "$FAKE_BIN/ssh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
shift
bash -c "$1"
SH

cat > "$FAKE_BIN/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ge 2 ] && [ "$1" = 'compose' ] && [ "$2" = 'version' ]; then
  exit 0
fi
if [ "$#" -ge 4 ] && [ "$1" = 'compose' ] && [ "$2" = '-f' ] && [ "$3" = 'deploy/docker-compose.yml' ] && [ "$4" = 'up' ]; then
  printf 'compose-file=%s\n' "$3" >> "$DOCKER_LOG"
  exit 0
fi
if [ "$#" -ge 4 ] && [ "$1" = 'compose' ] && [ "$2" = '-f' ] && [ "$3" = 'deploy/docker-compose.yml' ] && [ "$4" = 'ps' ]; then
  exit 0
fi
printf 'unexpected docker invocation: %s\n' "$*" >&2
exit 1
SH
chmod +x "$FAKE_BIN/ssh" "$FAKE_BIN/docker"

run_deploy() {
  env \
    PATH="$FAKE_BIN:$PATH" \
    DOCKER_LOG="$DOCKER_LOG" \
    DEPLOY_HOST='deployment-test.invalid' \
    DEPLOY_USER='tester' \
    DEPLOY_ROOT="$DEPLOY_ROOT" \
    APP_NAME="$APP_NAME" \
    REPO_URL="$ORIGIN_REPO" \
    BRANCH='main' \
    bash "$DEPLOY_SCRIPT"
}

run_deploy >"$TEST_ROOT/first.log" 2>&1
cmp -s "$CUSTOM_CONFIG" "$APP_DIR/$CONFIG_PATH" || { echo 'Existing remote config was not preserved during the tracked-file transition.' >&2; exit 1; }
[ "$(git -C "$APP_DIR" rev-parse HEAD)" = "$expected_head" ] || { echo 'Remote repository did not update to the expected commit.' >&2; exit 1; }
[ "$(stat -c '%a' "$APP_DIR/$CONFIG_PATH")" = '600' ] || { echo 'Restored remote config mode is not 600.' >&2; exit 1; }
grep -qx 'compose-file=deploy/docker-compose.yml' "$DOCKER_LOG" || { echo 'Remote deployment did not use deploy/docker-compose.yml.' >&2; exit 1; }

printf '%s\n' 'local dirty change' > "$APP_DIR/README.md"
printf '%s\n' 'upstream change' > "$SOURCE_REPO/README.md"
git -C "$SOURCE_REPO" add README.md
git -C "$SOURCE_REPO" commit --quiet -m 'upstream update'
git -C "$SOURCE_REPO" push --quiet
if run_deploy >"$TEST_ROOT/failure.log" 2>&1; then
  echo 'Expected deployment update to fail because of a conflicting local change.' >&2
  exit 1
fi
cmp -s "$CUSTOM_CONFIG" "$APP_DIR/$CONFIG_PATH" || { echo 'Remote config was not restored after a failed Git update.' >&2; exit 1; }

printf '%s\n' 'Remote deployment config preservation checks passed.'
