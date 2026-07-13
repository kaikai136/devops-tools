# Default Environment and Auto-Generated Secret Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a fresh clone directly deployable with `docker compose up -d --build` while generating and persisting a unique Django secret on first container startup.

**Architecture:** Commit a safe root `.env` containing deployment defaults but no secret. Let `docker/entrypoint.sh` resolve the secret from an explicit environment variable, an existing `/app/data/django-secret-key`, or a newly generated secure value, in that priority order. Keep local and remote deployment scripts thin and preserve existing private `.env` files during remote upgrades.

**Tech Stack:** Docker Compose, POSIX shell, Python 3.12 `secrets`, Django 5, Markdown.

## Global Constraints

- The repository must not contain a real production secret, token, password, or certificate.
- `docker compose up -d --build` must work from a fresh clone without manually creating `.env`.
- Generated secrets must persist in `/app/data/django-secret-key` and must never be printed.
- Explicit non-empty `DJANGO_SECRET_KEY` always overrides the persisted file.
- Existing remote private `.env` content and `./data` must survive upgrades.
- Docker Compose v2 is the primary target; the remote script must retain `docker-compose` compatibility.
- Production documentation must require tightening `DJANGO_ALLOWED_HOSTS` and configuring CSRF origins.

---

## File Map

- Create `.env`: versioned safe defaults consumed by Docker Compose.
- Modify `.gitignore`: allow only root `.env` while keeping private variants ignored.
- Modify `.dockerignore`: continue excluding environment files from the image build context, because Compose consumes `.env` on the host.
- Modify `docker-compose.yml`: accept an empty secret and pass all documented defaults.
- Modify `docker/entrypoint.sh`: resolve, generate, persist, and export the Django secret before Django commands run.
- Modify `scripts/compose-up.sh`: remove host-side secret generation and only prepare directories/start Compose.
- Modify `scripts/deploy-remote.sh`: preserve pre-existing private `.env` while updating tracked files.
- Create `scripts/tests/test-deployment-config.ps1`: deterministic deployment configuration and secret lifecycle checks without requiring a full production database.
- Modify `README.md`: document zero-setup startup, environment precedence, production overrides, upgrades, and backup implications.

---

### Task 1: Add Deployment Contract Tests

**Files:**
- Create: `scripts/tests/test-deployment-config.ps1`
- Test: `scripts/tests/test-deployment-config.ps1`

**Interfaces:**
- Consumes: repository root files and a POSIX shell available through Docker image execution or Git Bash.
- Produces: a PowerShell test command that exits non-zero on a broken default environment, Compose contract, entrypoint secret precedence, or documentation contract.

- [ ] **Step 1: Write the failing deployment contract test**

Create a PowerShell script that asserts:

```powershell
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$defaultEnv = Join-Path $root '.env'
$compose = Join-Path $root 'docker-compose.yml'
$entrypoint = Join-Path $root 'docker\entrypoint.sh'
$readme = Join-Path $root 'README.md'

if (-not (Test-Path $defaultEnv)) { throw 'Tracked root .env is missing.' }
$envText = Get-Content -Raw -Encoding UTF8 $defaultEnv
if ($envText -notmatch '(?m)^DJANGO_SECRET_KEY=$') { throw 'Default secret must be empty.' }
if ($envText -notmatch '(?m)^APP_PORT=8001$') { throw 'Default APP_PORT is missing.' }

$composeText = Get-Content -Raw -Encoding UTF8 $compose
if ($composeText -match 'DJANGO_SECRET_KEY:\s*"\$\{DJANGO_SECRET_KEY:\?') { throw 'Compose still requires a pre-created secret.' }
if ($composeText -notmatch 'DJANGO_SECRET_KEY:\s*"\$\{DJANGO_SECRET_KEY:-\}"') { throw 'Compose does not pass an optional secret.' }

$entrypointText = Get-Content -Raw -Encoding UTF8 $entrypoint
foreach ($required in @('DJANGO_SECRET_KEY_FILE', 'secrets.token_urlsafe', 'umask 077', 'export DJANGO_SECRET_KEY')) {
  if ($entrypointText -notmatch [regex]::Escape($required)) { throw "Entrypoint is missing: $required" }
}

$readmeText = Get-Content -Raw -Encoding UTF8 $readme
foreach ($required in @('docker compose up -d --build', '/app/data/django-secret-key', '--env-file .env.production')) {
  if ($readmeText -notmatch [regex]::Escape($required)) { throw "README is missing: $required" }
}
```

Add an integration section that runs the built image with a temporary host directory mounted at `/app/data`, overrides the command with a Python assertion, and verifies these cases:

```powershell
# Case 1: empty environment generates a non-empty persistent file.
# Case 2: second run returns the same value.
# Case 3: explicit DJANGO_SECRET_KEY=explicit-test-secret is exported unchanged.
# Every container command must bypass migrations by overriding entrypoint command through
# ENTRYPOINT's final exec, and must never print the actual generated secret.
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tests/test-deployment-config.ps1 -SkipImageChecks
```

Expected: FAIL with `Tracked root .env is missing.`

- [ ] **Step 3: Keep the test staged for later tasks**

Do not weaken assertions. Tasks 2–5 make this contract pass.

---

### Task 2: Add Safe Default Environment and Compose Wiring

**Files:**
- Create: `.env`
- Modify: `.gitignore:1-12`
- Modify: `docker-compose.yml:1-45`
- Test: `scripts/tests/test-deployment-config.ps1`

**Interfaces:**
- Consumes: Docker Compose variable interpolation.
- Produces: default variables `APP_PORT`, `IMAGE_NAME`, `CONTAINER_NAME`, `GUACD_CONTAINER_NAME`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_CORS_ALLOW_ALL_ORIGINS`, `GUACD_HOST`, `GUACD_PORT`, `RDP_RECORDING_RETENTION_DAYS`, and `RDP_RECORDING_DEFAULT_ENABLED`.

- [ ] **Step 1: Create the tracked default `.env`**

Use exactly this safe baseline:

```dotenv
# Safe defaults for local, test, and controlled intranet deployments.
# Production deployments should use a private env file and restrict hosts/origins.
APP_PORT=8001
IMAGE_NAME=devops-tools:latest
CONTAINER_NAME=devops-tools
GUACD_CONTAINER_NAME=devops-tools-guacd

# Leave empty to generate and persist a unique key in ./data/django-secret-key.
DJANGO_SECRET_KEY=
DJANGO_ALLOWED_HOSTS=*
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_CORS_ALLOW_ALL_ORIGINS=0

GUACD_HOST=guacd
GUACD_PORT=4822
RDP_RECORDING_RETENTION_DAYS=30
RDP_RECORDING_DEFAULT_ENABLED=0
```

- [ ] **Step 2: Allow only the root default `.env` in Git**

Replace the environment ignore block with:

```gitignore
.env
.env.*
!/.env
```

This keeps `.env.production`, `.env.local`, and nested private files ignored while allowing the versioned root file.

- [ ] **Step 3: Make the Compose secret optional**

Change the app environment mapping to:

```yaml
DJANGO_SECRET_KEY: "${DJANGO_SECRET_KEY:-}"
DJANGO_ALLOWED_HOSTS: "${DJANGO_ALLOWED_HOSTS:-*}"
DJANGO_CSRF_TRUSTED_ORIGINS: "${DJANGO_CSRF_TRUSTED_ORIGINS:-}"
```

Keep the existing fixed container paths and safe CORS default.

- [ ] **Step 4: Validate Compose interpolation**

Run:

```powershell
docker compose config --quiet
```

Expected: exit code 0 with no missing-variable error.

---

### Task 3: Implement Persistent Secret Resolution in Entrypoint

**Files:**
- Modify: `docker/entrypoint.sh:1-9`
- Test: `scripts/tests/test-deployment-config.ps1`

**Interfaces:**
- Consumes: optional `DJANGO_SECRET_KEY` and optional `DJANGO_SECRET_KEY_FILE` (default `/app/data/django-secret-key`).
- Produces: exported non-empty `DJANGO_SECRET_KEY` for Django processes and a mode-600 persisted file when generated.

- [ ] **Step 1: Add secret resolution before migrations**

Implement this behavior in POSIX shell:

```sh
SECRET_KEY_FILE="${DJANGO_SECRET_KEY_FILE:-/app/data/django-secret-key}"

if [ -n "${DJANGO_SECRET_KEY:-}" ]; then
  echo "Using DJANGO_SECRET_KEY from the environment."
elif [ -s "$SECRET_KEY_FILE" ]; then
  DJANGO_SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
  export DJANGO_SECRET_KEY
  echo "Using the persisted Django secret key."
else
  umask 077
  secret_key_dir="$(dirname "$SECRET_KEY_FILE")"
  secret_key_tmp="${SECRET_KEY_FILE}.tmp.$$"
  mkdir -p "$secret_key_dir"
  DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
  printf '%s\n' "$DJANGO_SECRET_KEY" > "$secret_key_tmp"
  chmod 600 "$secret_key_tmp"
  mv "$secret_key_tmp" "$SECRET_KEY_FILE"
  export DJANGO_SECRET_KEY
  echo "Generated and persisted a new Django secret key."
fi

export DJANGO_SECRET_KEY
```

Retain directory creation, migrations, static collection, and `exec "$@"` after secret resolution.

- [ ] **Step 2: Add cleanup for interrupted writes**

Before writing the temporary file, install a trap:

```sh
trap 'rm -f "$secret_key_tmp"' EXIT HUP INT TERM
```

After moving it into place, clear the trap:

```sh
trap - EXIT HUP INT TERM
```

- [ ] **Step 3: Verify static contract checks pass**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tests/test-deployment-config.ps1 -SkipImageChecks
```

Expected: static checks pass; image checks are reported as skipped.

---

### Task 4: Simplify Local and Remote Deployment Scripts

**Files:**
- Modify: `scripts/compose-up.sh:1-26`
- Modify: `scripts/deploy-remote.sh:1-73`
- Test: `scripts/tests/test-deployment-config.ps1`

**Interfaces:**
- Consumes: tracked default `.env`, optional existing private `.env`, Compose v2 or `docker-compose`.
- Produces: local zero-setup startup and remote upgrades that retain existing environment content.

- [ ] **Step 1: Simplify `compose-up.sh`**

Replace host-side environment generation with:

```sh
#!/usr/bin/env bash
set -euo pipefail

mkdir -p data media
docker compose up -d --build
docker compose ps
```

- [ ] **Step 2: Preserve remote `.env` before Git operations**

Inside the remote script, define:

```sh
ENV_BACKUP=""
cleanup_env_backup() {
  if [ -n "$ENV_BACKUP" ] && [ -f "$ENV_BACKUP" ]; then
    rm -f "$ENV_BACKUP"
  fi
}
trap cleanup_env_backup EXIT HUP INT TERM

if [ -f "$APP_DIR/.env" ]; then
  ENV_BACKUP="$(mktemp)"
  cp "$APP_DIR/.env" "$ENV_BACKUP"
  chmod 600 "$ENV_BACKUP"
fi
```

Run this before checkout/pull for an existing repository.

- [ ] **Step 3: Restore the private environment after Git update**

After clone/update and `cd "$APP_DIR"`, restore only when a backup exists:

```sh
if [ -n "$ENV_BACKUP" ]; then
  cp "$ENV_BACKUP" .env
  chmod 600 .env
fi
```

Do not generate a secret or a new `.env`; fresh clones already contain the default file.

- [ ] **Step 4: Run shell syntax checks**

Run:

```powershell
bash -n scripts/compose-up.sh
bash -n scripts/deploy-remote.sh
bash -n docker/entrypoint.sh
```

Expected: all commands exit 0.

---

### Task 5: Update Deployment Documentation

**Files:**
- Modify: `README.md:130-330`
- Test: `scripts/tests/test-deployment-config.ps1`

**Interfaces:**
- Consumes: final `.env`, Compose, entrypoint, and deployment script behavior.
- Produces: copy-pasteable deployment and upgrade instructions.

- [ ] **Step 1: Replace the first-deploy flow**

Document this exact minimal flow:

```bash
git clone https://github.com/kaikai136/devops-tools.git
cd devops-tools
docker compose up -d --build
docker compose ps
```

State that no manual `.env` creation is required.

- [ ] **Step 2: Document the default environment file**

Explain:

- Root `.env` is versioned and contains no real secret.
- Empty `DJANGO_SECRET_KEY` triggers first-start generation.
- Priority is explicit environment value, persisted file, generated value.
- The generated file is `./data/django-secret-key` on the host and `/app/data/django-secret-key` in the container.
- Deleting `./data` deletes both SQLite data and the generated key.

- [ ] **Step 3: Document production overrides**

Provide:

```bash
cp .env .env.production
```

and an example private configuration with a restricted hostname, HTTPS CSRF origin, and optional explicit secret:

```dotenv
APP_PORT=8001
DJANGO_SECRET_KEY=
DJANGO_ALLOWED_HOSTS=ops.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://ops.example.com
DJANGO_CORS_ALLOW_ALL_ORIGINS=0
```

Start it with:

```bash
docker compose --env-file .env.production up -d --build
```

Explain that leaving the private secret empty still uses the persistent auto-generated key.

- [ ] **Step 4: Expand the variable table**

Include all variables from the default `.env`, plus container-only paths and `DJANGO_SECRET_KEY_FILE`. Mark `DJANGO_ALLOWED_HOSTS=*` as convenience-only and unsafe as a production default.

- [ ] **Step 5: Update remote deployment and upgrade notes**

State that `scripts/deploy-remote.sh` preserves an existing remote `.env`, fresh clones use the tracked default, and both `.env` and `data` should be backed up before major upgrades.

- [ ] **Step 6: Run the static deployment contract test**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tests/test-deployment-config.ps1 -SkipImageChecks
```

Expected: all static and documentation assertions pass.

---

### Task 6: Build and Verify the Complete Deployment Lifecycle

**Files:**
- Test: `scripts/tests/test-deployment-config.ps1`
- Verify: `.env`, `docker-compose.yml`, `docker/entrypoint.sh`, `README.md`

**Interfaces:**
- Consumes: Docker Engine and Docker Compose.
- Produces: evidence that a fresh deployment generates one stable secret and serves a healthy app.

- [ ] **Step 1: Build the production image**

Run:

```powershell
docker compose build app
```

Expected: exit code 0.

- [ ] **Step 2: Run full secret lifecycle checks**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/tests/test-deployment-config.ps1
```

Expected: generated-file, stable-reuse, explicit-override, file-permission, and no-secret-in-logs checks all pass.

- [ ] **Step 3: Start the complete stack**

Run:

```powershell
docker compose up -d
```

Expected: `app` and `guacd` start without missing environment errors.

- [ ] **Step 4: Wait for and verify health**

Run a bounded polling loop against:

```text
http://127.0.0.1:8001/api/health/
```

Expected: HTTP 200 and `{"status":"ok"}`.

- [ ] **Step 5: Verify persistence across recreation**

Record the SHA-256 hash of `data/django-secret-key`, run:

```powershell
docker compose up -d --force-recreate app
```

Then verify the file hash is unchanged and health returns HTTP 200 again.

- [ ] **Step 6: Run quality gates**

Run:

```powershell
git diff --check
bash -n docker/entrypoint.sh
bash -n scripts/compose-up.sh
bash -n scripts/deploy-remote.sh
docker compose config --quiet
```

Expected: all exit 0.

- [ ] **Step 7: Review repository state**

Run:

```powershell
git status --short
git diff --stat
git diff
```

Expected: only the intended deployment configuration, scripts, tests, spec/plan, and README changes are present; generated `data`, `media`, logs, and secrets remain ignored.
