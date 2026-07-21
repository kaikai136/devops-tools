$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

function Assert-PathExists {
    param([string]$RelativePath, [string]$Message)
    if (-not (Test-Path -LiteralPath (Join-Path $root $RelativePath))) { throw $Message }
}

function Assert-PathMissing {
    param([string]$RelativePath, [string]$Message)
    if (Test-Path -LiteralPath (Join-Path $root $RelativePath)) { throw $Message }
}

function Assert-Match {
    param([string]$Text, [string]$Pattern, [string]$Message)
    if ($Text -notmatch $Pattern) { throw $Message }
}

function Assert-IgnoredByTrackedGitignore {
    param([string]$RelativePath)
    $output = & git -C $root check-ignore -v --no-index -- $RelativePath 2>&1
    if ($LASTEXITCODE -ne 0) { throw ".gitignore does not ignore: $RelativePath" }

    $line = (@($output) | Select-Object -First 1)
    if (-not $line) { throw ".gitignore check returned no evidence for: $RelativePath" }

    $metadata = ($line -split "`t", 2)[0]
    if ($metadata -notmatch '(^|[\\/])?\.gitignore:\d+:') {
        throw "Ignore rule for $RelativePath is not from tracked .gitignore: $line"
    }
}

$forbiddenTracked = @(
    'login-implemented.png',
    'login-prototype.png',
    'prototype-home.png',
    'restored-login.png',
    'docker-compose.yml',
    'Dockerfile',
    '.env',
    'docker/entrypoint.sh',
    'scripts/compose-up.sh',
    'scripts/build-image.sh',
    'scripts/deploy-remote.sh'
)
$required = @(
    'frontend/public/captain-banner.png',
    'frontend/public/ops-captain-icon.png',
    'deploy/config/app.conf',
    'deploy/docker-compose.yml',
    'deploy/Dockerfile',
    'deploy/docker/entrypoint.sh',
    'deploy/scripts/compose-up.sh',
    'deploy/scripts/build-image.sh',
    'deploy/scripts/deploy-remote.sh'
)

foreach ($relative in $forbiddenTracked) {
    Assert-PathMissing $relative "Forbidden file exists: $relative"
}
foreach ($relative in $required) {
    Assert-PathExists $relative "Required file missing: $relative"
}

$tracked = & git -C $root ls-files
if ($LASTEXITCODE -ne 0) { throw 'Unable to list tracked files.' }
$forbiddenTrackedPatterns = @('(^|/)db\.sqlite3$', '(^|/)(media|data)/', '\.log$', '^frontend/dist/')
foreach ($path in $tracked) {
    foreach ($pattern in $forbiddenTrackedPatterns) {
        if ($path -match $pattern) { throw "Generated/local file is tracked: $path" }
    }
}

$gitignorePath = Join-Path $root '.gitignore'
$ignore = Get-Content -LiteralPath $gitignorePath -Raw -Encoding UTF8
Assert-Match $ignore '(?m)^\s*\.codex-logs/?\s*$' '.gitignore missing tracked rule: .codex-logs/'

foreach ($ignoredPath in @(
    'scratch.log',
    '.env',
    '.env.production',
    'deploy/config/app.local.conf',
    'backend/db.sqlite3',
    'backend/media/upload.bin',
    'data/runtime.bin',
    'media/runtime.bin',
    'frontend/dist/app.js',
    'backend/__pycache__/module.pyc',
    'frontend/node_modules/package/index.js'
)) {
    Assert-IgnoredByTrackedGitignore $ignoredPath
}

Write-Host 'Repository structure contract passed.'
