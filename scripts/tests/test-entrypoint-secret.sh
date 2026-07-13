#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENTRYPOINT="$REPO_ROOT/docker/entrypoint.sh"
TEST_ROOT="$(mktemp -d)"
SECRET_FILE="$TEST_ROOT/data/django-secret-key"
FIRST_LOG="$TEST_ROOT/first.log"
SECOND_LOG="$TEST_ROOT/second.log"
EXPLICIT_LOG="$TEST_ROOT/explicit.log"
EXPLICIT_SECRET="explicit-test-secret"

cleanup() {
  rm -rf "$TEST_ROOT"
  rmdir /app/staticfiles /app/media /app/data /app 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$TEST_ROOT/bin" "$TEST_ROOT/work" "$(dirname "$SECRET_FILE")"
printf '\n' > "$SECRET_FILE"
ln -s "$(command -v python3)" "$TEST_ROOT/bin/python"
cat > "$TEST_ROOT/work/manage.py" <<'PY'
import sys

if len(sys.argv) < 2 or sys.argv[1] not in {"migrate", "collectstatic"}:
    raise SystemExit(f"unexpected manage.py invocation: {sys.argv!r}")
PY

assert_persisted_command='import os; from pathlib import Path; path=Path(os.environ["DJANGO_SECRET_KEY_FILE"]); persisted=path.read_text(encoding="utf-8").strip(); assert persisted; assert os.environ["DJANGO_SECRET_KEY"] == persisted'
assert_explicit_command='import os; from pathlib import Path; path=Path(os.environ["DJANGO_SECRET_KEY_FILE"]); persisted=path.read_text(encoding="utf-8").strip(); assert os.environ["DJANGO_SECRET_KEY"] == "explicit-test-secret"; assert persisted != os.environ["DJANGO_SECRET_KEY"]'

(
  cd "$TEST_ROOT/work"
  env -u DJANGO_SECRET_KEY \
    PATH="$TEST_ROOT/bin:$PATH" \
    DJANGO_SECRET_KEY_FILE="$SECRET_FILE" \
    "$ENTRYPOINT" python -c "$assert_persisted_command"
) >"$FIRST_LOG" 2>&1

[ -s "$SECRET_FILE" ] || { echo 'Generated secret file is empty.' >&2; exit 1; }
[ "$(stat -c '%a' "$SECRET_FILE")" = '600' ] || { echo 'Generated secret file mode is not 600.' >&2; exit 1; }
secret="$(tr -d '\r\n' < "$SECRET_FILE")"
first_hash="$(sha256sum "$SECRET_FILE" | awk '{print $1}')"
grep -q 'Generated and persisted a new Django secret key.' "$FIRST_LOG"
if grep -Fq "$secret" "$FIRST_LOG"; then
  echo 'Generated secret leaked into entrypoint logs.' >&2
  exit 1
fi

(
  cd "$TEST_ROOT/work"
  env -u DJANGO_SECRET_KEY \
    PATH="$TEST_ROOT/bin:$PATH" \
    DJANGO_SECRET_KEY_FILE="$SECRET_FILE" \
    "$ENTRYPOINT" python -c "$assert_persisted_command"
) >"$SECOND_LOG" 2>&1

second_hash="$(sha256sum "$SECRET_FILE" | awk '{print $1}')"
[ "$second_hash" = "$first_hash" ] || { echo 'Persisted secret changed on the second start.' >&2; exit 1; }
grep -q 'Using the persisted Django secret key.' "$SECOND_LOG"
if grep -Fq "$secret" "$SECOND_LOG"; then
  echo 'Persisted secret leaked into entrypoint logs.' >&2
  exit 1
fi

(
  cd "$TEST_ROOT/work"
  PATH="$TEST_ROOT/bin:$PATH" \
    DJANGO_SECRET_KEY_FILE="$SECRET_FILE" \
    DJANGO_SECRET_KEY="$EXPLICIT_SECRET" \
    "$ENTRYPOINT" python -c "$assert_explicit_command"
) >"$EXPLICIT_LOG" 2>&1

final_hash="$(sha256sum "$SECRET_FILE" | awk '{print $1}')"
[ "$final_hash" = "$first_hash" ] || { echo 'Explicit override modified the persisted secret.' >&2; exit 1; }
grep -q 'Using DJANGO_SECRET_KEY from the environment.' "$EXPLICIT_LOG"
if grep -Fq "$EXPLICIT_SECRET" "$EXPLICIT_LOG"; then
  echo 'Explicit secret leaked into entrypoint logs.' >&2
  exit 1
fi

printf '%s\n' 'Entrypoint secret lifecycle checks passed.'
