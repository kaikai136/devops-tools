param(
    [switch]$SkipImageChecks,
    [string]$ImageName = 'devops-tools:auto-secret-test'
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$defaultEnv = Join-Path $root '.env'
$compose = Join-Path $root 'docker-compose.yml'
$entrypoint = Join-Path $root 'docker\entrypoint.sh'
$readme = Join-Path $root 'README.md'
$gitignore = Join-Path $root '.gitignore'
$gitattributes = Join-Path $root '.gitattributes'
$composeUp = Join-Path $root 'scripts\compose-up.sh'
$deployRemote = Join-Path $root 'scripts\deploy-remote.sh'
$entrypointLifecycleTest = Join-Path $root 'scripts\tests\test-entrypoint-secret.sh'
$remoteEnvTest = Join-Path $root 'scripts\tests\test-deploy-remote-env.sh'

function Assert-Match {
    param([string]$Text, [string]$Pattern, [string]$Message)
    if ($Text -notmatch $Pattern) { throw $Message }
}

function Invoke-Docker {
    param([string[]]$Arguments)
    $output = & docker @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($Arguments -join ' ') failed:`n$($output -join [Environment]::NewLine)"
    }
    return @($output)
}

if (-not (Test-Path $defaultEnv)) { throw 'Tracked root .env is missing.' }
$envText = Get-Content -Raw -Encoding UTF8 $defaultEnv
Assert-Match $envText '(?m)^DJANGO_SECRET_KEY=\r?$' 'Default secret must be empty.'
Assert-Match $envText '(?m)^APP_PORT=8001\r?$' 'Default APP_PORT is missing.'
Assert-Match $envText '(?m)^DJANGO_ALLOWED_HOSTS=\*\r?$' 'Default hosts must support zero-setup startup.'

$gitignoreText = Get-Content -Raw -Encoding UTF8 $gitignore
Assert-Match $gitignoreText '(?m)^!/.env\r?$' 'Root .env is not explicitly allowed by .gitignore.'

if (-not (Test-Path $gitattributes)) { throw '.gitattributes is missing; shell scripts may be checked out with CRLF.' }
$gitattributesText = Get-Content -Raw -Encoding UTF8 $gitattributes
Assert-Match $gitattributesText '(?m)^\*\.sh text eol=lf\r?$' 'Shell scripts are not pinned to LF line endings.'
foreach ($shellScript in @($entrypoint, $composeUp, $deployRemote, $entrypointLifecycleTest, $remoteEnvTest)) {
    $shellBytes = [IO.File]::ReadAllBytes($shellScript)
    if ([Text.Encoding]::UTF8.GetString($shellBytes).Contains("`r")) { throw "Shell script contains CR line endings: $shellScript" }
}

$composeText = Get-Content -Raw -Encoding UTF8 $compose
if ($composeText -match 'DJANGO_SECRET_KEY:\s*"\$\{DJANGO_SECRET_KEY:\?') { throw 'Compose still requires a pre-created secret.' }
Assert-Match $composeText 'DJANGO_SECRET_KEY:\s*"\$\{DJANGO_SECRET_KEY:-\}"' 'Compose does not pass an optional secret.'
Assert-Match $composeText 'DJANGO_ALLOWED_HOSTS:\s*"\$\{DJANGO_ALLOWED_HOSTS:-\*\}"' 'Compose does not provide the zero-setup hosts default.'

$entrypointText = Get-Content -Raw -Encoding UTF8 $entrypoint
foreach ($required in @('DJANGO_SECRET_KEY_FILE', 'secrets.token_urlsafe', 'umask 077', 'export DJANGO_SECRET_KEY', 'chmod 600')) {
    if ($entrypointText -notmatch [regex]::Escape($required)) { throw "Entrypoint is missing: $required" }
}

$composeUpText = Get-Content -Raw -Encoding UTF8 $composeUp
if ($composeUpText -match 'openssl rand|cat > \.env|SECRET_KEY=') { throw 'compose-up.sh still generates host-side environment secrets.' }

$deployRemoteText = Get-Content -Raw -Encoding UTF8 $deployRemote
foreach ($required in @('ENV_BACKUP', 'mktemp', 'cp "$APP_DIR/.env" "$ENV_BACKUP"', 'git -C "$APP_DIR" checkout -- .env', 'rm -f "$APP_DIR/.env"', 'cp "$ENV_BACKUP" .env')) {
    if ($deployRemoteText -notmatch [regex]::Escape($required)) { throw "deploy-remote.sh is missing private .env preservation: $required" }
}
if ($deployRemoteText -match 'openssl rand|cat > \.env|SECRET_KEY=') { throw 'deploy-remote.sh still generates environment secrets.' }
if ($deployRemoteText -match 'APP_PORT="\$\{APP_PORT:-8001\}"') { throw 'deploy-remote.sh always overrides the existing remote .env APP_PORT.' }
Assert-Match $deployRemoteText 'APP_PORT_OVERRIDE="\$\{APP_PORT:-\}"' 'deploy-remote.sh does not distinguish an explicit APP_PORT override.'

$readmeText = Get-Content -Raw -Encoding UTF8 $readme
foreach ($required in @('docker compose up -d --build', '/app/data/django-secret-key', './data/django-secret-key', '--env-file .env.production', 'DJANGO_ALLOWED_HOSTS=*')) {
    if ($readmeText -notmatch [regex]::Escape($required)) { throw "README is missing: $required" }
}

Write-Host 'Static deployment contract checks passed.'
if ($SkipImageChecks) { Write-Host 'Image lifecycle checks skipped.'; exit 0 }

& docker image inspect $ImageName *> $null
if ($LASTEXITCODE -ne 0) { throw "Image '$ImageName' is not available. Build it before running image checks." }

$volumeName = "devops-tools-secret-test-$([Guid]::NewGuid().ToString('N'))"
$explicitSecret = 'explicit-test-secret'
$assertCommand = 'import os; from pathlib import Path; path=Path(os.environ.get("DJANGO_SECRET_KEY_FILE", "/app/data/django-secret-key")); assert path.is_file(); persisted=path.read_text(encoding="utf-8").strip(); assert persisted; assert os.environ["DJANGO_SECRET_KEY"] == persisted'
$explicitCommand = 'import os; from pathlib import Path; path=Path(os.environ.get("DJANGO_SECRET_KEY_FILE", "/app/data/django-secret-key")); assert path.is_file(); assert os.environ["DJANGO_SECRET_KEY"] == "explicit-test-secret"; assert path.read_text(encoding="utf-8").strip() != os.environ["DJANGO_SECRET_KEY"]'

try {
    Invoke-Docker @('volume', 'create', $volumeName) | Out-Null
    $firstLogs = Invoke-Docker @('run', '--rm', '-v', "${volumeName}:/app/data", $ImageName, 'python', '-c', $assertCommand)
    $secret = (Invoke-Docker @('run', '--rm', '--entrypoint', 'python', '-v', "${volumeName}:/app/data", $ImageName, '-c', 'from pathlib import Path; print(Path("/app/data/django-secret-key").read_text().strip())') -join '').Trim()
    if (-not $secret) { throw 'Generated secret file is empty.' }
    if (($firstLogs -join "`n") -match [regex]::Escape($secret)) { throw 'Generated secret leaked into container logs.' }
    if (($firstLogs -join "`n") -notmatch 'Generated and persisted a new Django secret key') { throw 'First run did not report generated secret source.' }

    $firstHash = (Invoke-Docker @('run', '--rm', '--entrypoint', 'python', '-v', "${volumeName}:/app/data", $ImageName, '-c', 'import hashlib; from pathlib import Path; print(hashlib.sha256(Path("/app/data/django-secret-key").read_bytes()).hexdigest())') -join '').Trim()
    $mode = (Invoke-Docker @('run', '--rm', '--entrypoint', 'python', '-v', "${volumeName}:/app/data", $ImageName, '-c', 'from pathlib import Path; print(oct(Path("/app/data/django-secret-key").stat().st_mode & 0o777))') -join '').Trim()
    if ($mode -ne '0o600') { throw "Generated secret mode is $mode instead of 0o600." }

    $secondLogs = Invoke-Docker @('run', '--rm', '-v', "${volumeName}:/app/data", $ImageName, 'python', '-c', $assertCommand)
    $secondHash = (Invoke-Docker @('run', '--rm', '--entrypoint', 'python', '-v', "${volumeName}:/app/data", $ImageName, '-c', 'import hashlib; from pathlib import Path; print(hashlib.sha256(Path("/app/data/django-secret-key").read_bytes()).hexdigest())') -join '').Trim()
    if ($secondHash -ne $firstHash) { throw 'Persisted secret changed on the second start.' }
    if (($secondLogs -join "`n") -notmatch 'Using the persisted Django secret key') { throw 'Second run did not report persisted secret source.' }
    if (($secondLogs -join "`n") -match [regex]::Escape($secret)) { throw 'Persisted secret leaked into container logs.' }

    $explicitLogs = Invoke-Docker @('run', '--rm', '-e', "DJANGO_SECRET_KEY=$explicitSecret", '-v', "${volumeName}:/app/data", $ImageName, 'python', '-c', $explicitCommand)
    if (($explicitLogs -join "`n") -notmatch 'Using DJANGO_SECRET_KEY from the environment') { throw 'Explicit secret did not take precedence.' }
    if (($explicitLogs -join "`n") -match [regex]::Escape($explicitSecret)) { throw 'Explicit secret leaked into container logs.' }

    $finalHash = (Invoke-Docker @('run', '--rm', '--entrypoint', 'python', '-v', "${volumeName}:/app/data", $ImageName, '-c', 'import hashlib; from pathlib import Path; print(hashlib.sha256(Path("/app/data/django-secret-key").read_bytes()).hexdigest())') -join '').Trim()
    if ($finalHash -ne $firstHash) { throw 'Explicit override modified the persisted secret file.' }
    Write-Host 'Image secret lifecycle checks passed.'
}
finally {
    & docker volume rm -f $volumeName *> $null
}
