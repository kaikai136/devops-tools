$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$localConfig = Join-Path $root 'config\local.app.conf'
$backendStart = Join-Path $root 'backend\start-wsl.ps1'
$viteConfig = Join-Path $root 'frontend\vite.config.ts'
$readme = Join-Path $root 'README.md'
$gitignore = Join-Path $root '.gitignore'

function Assert-Match {
    param([string]$Text, [string]$Pattern, [string]$Message)
    if ($Text -notmatch $Pattern) { throw $Message }
}

if (-not (Test-Path $localConfig)) { throw 'Local startup config is missing: config/local.app.conf' }

$configText = Get-Content -Raw -Encoding UTF8 $localConfig
foreach ($required in @(
    'BACKEND_HOST=0.0.0.0',
    'BACKEND_PORT=8001',
    'FRONTEND_HOST=0.0.0.0',
    'FRONTEND_PORT=5173',
    'VITE_API_TARGET=http://127.0.0.1:8001',
    'VITE_WS_TARGET=ws://127.0.0.1:8001',
    'DJANGO_DEBUG=1',
    'DJANGO_ALLOWED_HOSTS=*',
    'DJANGO_CORS_ALLOW_ALL_ORIGINS=1',
    'DATABASE_ENGINE=sqlite',
    'DJANGO_DB_PATH=backend/db.sqlite3',
    'REDIS_ENABLED=0',
    'GUACD_HOST=127.0.0.1',
    'RDP_RECORDING_ROOT=backend/rdp_recordings',
    'SSH_GATEWAY_ENABLED=1',
    'SSH_GATEWAY_PORT=2222',
    'BULK_EXECUTION_MAX_TARGETS=50',
    'DASHBOARD_CACHE_SECONDS=30',
    'EGRESS_CACHE_SECONDS=300',
    'FEATURE_PERMISSION_CACHE_SECONDS=300',
    'NVD_API_KEY=',
    'OPS_TOOL_ADMIN_PASSWORD='
)) {
    Assert-Match $configText "(?m)^$([regex]::Escape($required))\r?$" "Local config is missing: $required"
}

$backendStartText = Get-Content -Raw -Encoding UTF8 $backendStart
foreach ($required in @('config', 'local.app.conf', 'APP_CONFIG_FILE', 'BACKEND_HOST', 'BACKEND_PORT', 'wslpath', 'ops_tool.asgi:application')) {
    Assert-Match $backendStartText $([regex]::Escape($required)) "backend/start-wsl.ps1 does not read local startup config: $required"
}
if ($backendStartText -match [regex]::Escape('-p 8001')) { throw 'backend/start-wsl.ps1 still hard-codes backend port 8001.' }

$viteConfigText = Get-Content -Raw -Encoding UTF8 $viteConfig
foreach ($required in @('local.app.conf', 'FRONTEND_HOST', 'FRONTEND_PORT', 'VITE_API_TARGET', 'VITE_WS_TARGET')) {
    Assert-Match $viteConfigText $([regex]::Escape($required)) "frontend/vite.config.ts does not read local startup config: $required"
}
foreach ($forbidden in @("port: 5173", "'/api': 'http://127.0.0.1:8001'", "target: 'ws://127.0.0.1:8001'")) {
    if ($viteConfigText -match [regex]::Escape($forbidden)) { throw "frontend/vite.config.ts still hard-codes local startup config: $forbidden" }
}

$readmeText = Get-Content -Raw -Encoding UTF8 $readme
foreach ($required in @('config/local.app.conf', 'backend/start-wsl.ps1', 'npm run dev', 'APP_CONFIG_FILE', 'BACKEND_PORT', 'FRONTEND_PORT', 'VITE_API_TARGET', 'deploy/config/app.conf', 'docker build -f deploy/Dockerfile')) {
    Assert-Match $readmeText $([regex]::Escape($required)) "README is missing local/build config guidance: $required"
}

$gitignoreText = Get-Content -Raw -Encoding UTF8 $gitignore
if ($gitignoreText -match '(?m)^config/local\.app\.conf\r?$') {
    throw 'config/local.app.conf should be tracked as the safe local startup default.'
}

Write-Host 'Local startup config contract passed.'
