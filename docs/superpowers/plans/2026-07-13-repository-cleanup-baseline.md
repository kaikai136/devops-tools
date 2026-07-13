# 仓库清理与基线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可重复的仓库结构守卫和测试基线，并安全删除用户已授权清理的本地数据、日志、缓存与未引用原型图。

**Architecture:** 先用 PowerShell 契约测试声明“允许保留”和“必须消失”的文件，再核实引用、进程归属和删除路径边界。Git 跟踪文件使用 `git rm`，忽略文件使用解析后路径和原生 PowerShell 删除，避免跨 shell 拼接递归删除命令。

**Tech Stack:** Git、PowerShell、Django test runner、Vite、现有部署契约脚本

## Global Constraints

- 不删除 `.env`、源代码、品牌图片或无法确认归属的 Docker volume。
- 递归删除前必须确认所有目标的绝对路径均位于当前仓库根目录。
- 只停止命令行明确包含当前仓库绝对路径的 Python/Node 进程。
- 数据库模型和迁移文件不变。

---

### Task 1: 记录初始基线

**Files:**
- Create: `.codex-logs/baseline/backend-tests.txt`（临时忽略文件）
- Create: `.codex-logs/baseline/frontend-build.txt`（临时忽略文件）
- Create: `.codex-logs/baseline/deployment-tests.txt`（临时忽略文件）

**Interfaces:**
- Consumes: 未重构代码。
- Produces: 后续阶段可比较的测试数和构建结果。

- [ ] **Step 1: 运行 Django 全量测试并保存退出码**

Run:
```powershell
New-Item -ItemType Directory -Force .codex-logs\baseline | Out-Null
Push-Location backend
$env:DJANGO_SECRET_KEY='deep-refactor-baseline'
python manage.py test --noinput 2>&1 | Tee-Object ..\.codex-logs\baseline\backend-tests.txt
if ($LASTEXITCODE -ne 0) { throw 'Django baseline failed' }
Pop-Location
```
Expected: exit code `0`，输出记录当前测试数量（预期约 182 个）。

- [ ] **Step 2: 运行前端构建**

Run:
```powershell
Push-Location frontend
npm run build 2>&1 | Tee-Object ..\.codex-logs\baseline\frontend-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Frontend baseline failed' }
Pop-Location
```
Expected: Vite build 成功。

- [ ] **Step 3: 运行部署契约测试**

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\tests\test-deployment-config.ps1 -SkipImageChecks 2>&1 | Tee-Object .codex-logs\baseline\deployment-tests.txt
if ($LASTEXITCODE -ne 0) { throw 'Deployment contract baseline failed' }
```
Expected: exit code `0`。

### Task 2: 增加仓库结构守卫

**Files:**
- Create: `scripts/tests/test-repository-structure.ps1`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 设计文档中的保留/删除清单。
- Produces: `scripts/tests/test-repository-structure.ps1`，成功返回 `0`，违规时抛出错误。

- [ ] **Step 1: 写入预期先失败的结构测试**

Create `scripts/tests/test-repository-structure.ps1`:
```powershell
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$forbiddenTracked = @(
  'login-implemented.png',
  'login-prototype.png',
  'prototype-home.png',
  'restored-login.png'
)
$required = @(
  'frontend/public/captain-banner.png',
  'frontend/public/ops-captain-icon.png',
  '.env'
)
foreach ($relative in $forbiddenTracked) {
  if (Test-Path -LiteralPath (Join-Path $root $relative)) { throw "Forbidden file exists: $relative" }
}
foreach ($relative in $required) {
  if (-not (Test-Path -LiteralPath (Join-Path $root $relative))) { throw "Required file missing: $relative" }
}
$tracked = git -C $root ls-files
$forbiddenTrackedPatterns = @('(^|/)db\.sqlite3$', '(^|/)(media|data)/', '\.log$', '^frontend/dist/')
foreach ($path in $tracked) {
  foreach ($pattern in $forbiddenTrackedPatterns) {
    if ($path -match $pattern) { throw "Generated/local file is tracked: $path" }
  }
}
$ignore = Get-Content -LiteralPath (Join-Path $root '.gitignore') -Raw
foreach ($pattern in @('*.log', 'db.sqlite3', 'frontend/dist', '.codex-logs')) {
  if ($ignore -notmatch [regex]::Escape($pattern)) { throw ".gitignore missing rule: $pattern" }
}
Write-Host 'Repository structure contract passed.'
```

- [ ] **Step 2: 运行测试确认它因原型图仍存在而失败**

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\tests\test-repository-structure.ps1
```
Expected: FAIL，错误包含 `Forbidden file exists`。

- [ ] **Step 3: 补齐忽略规则**

Ensure `.gitignore` includes exactly scoped entries:
```gitignore
*.log
.codex-logs/
backend/db.sqlite3
backend/media/
/data/
/media/
frontend/dist/
**/__pycache__/
*.py[cod]
frontend/node_modules/
```

### Task 3: 再次确认历史图片无引用并删除

**Files:**
- Delete: `login-implemented.png`
- Delete: `login-prototype.png`
- Delete: `prototype-home.png`
- Delete: `restored-login.png`

**Interfaces:**
- Consumes: `git grep` 引用结果为空。
- Produces: Git 不再跟踪四张历史原型图。

- [ ] **Step 1: 检查引用**

Run:
```powershell
$names = 'login-implemented.png','login-prototype.png','prototype-home.png','restored-login.png'
foreach ($name in $names) {
  git grep -n -- $name ':!docs/superpowers/specs/2026-07-13-deep-structure-refactor-design.md' ':!docs/superpowers/plans/*'
  if ($LASTEXITCODE -eq 0) { throw "Referenced prototype image: $name" }
}
```
Expected: 所有查询均无业务代码或有效文档引用。

- [ ] **Step 2: 删除跟踪图片**

Run:
```powershell
git rm -- login-implemented.png login-prototype.png prototype-home.png restored-login.png
```
Expected: 四个文件进入 staged deletion。

- [ ] **Step 3: 运行结构测试**

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\tests\test-repository-structure.ps1
```
Expected: PASS。

- [ ] **Step 4: 提交清理守卫和图片删除**

Run:
```powershell
git add .gitignore scripts/tests/test-repository-structure.ps1
git commit -m "chore: 建立仓库结构守卫并清理原型图"
```
Expected: 一个仅包含结构守卫、忽略规则和四张图片删除的提交。

### Task 4: 停止项目本地进程

**Files:**
- No tracked file changes.

**Interfaces:**
- Consumes: 当前 worktree 绝对路径。
- Produces: 不再占用本项目日志、SQLite 或构建目录的项目进程。

- [ ] **Step 1: 精确列出项目 Python/Node 进程**

Run:
```powershell
$root = (Resolve-Path .).Path
$projectProcesses = Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match '^(python|pythonw|node)\.exe$' -and
  $_.CommandLine -and
  $_.CommandLine.IndexOf($root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}
$projectProcesses | Select-Object ProcessId,Name,CommandLine | Format-List
```
Expected: 仅显示命令行包含当前仓库绝对路径的进程；无结果也属正常。

- [ ] **Step 2: 只停止上述进程**

Run:
```powershell
$projectProcesses | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }
```
Expected: 不影响其他目录运行的 Python/Node 程序。

### Task 5: 安全删除本地数据、日志和缓存

**Files:**
- Delete ignored: `django-vue-*.log`, `.codex-logs/`, `backend/db.sqlite3`, `backend/media/`, `data/`, `media/`, `frontend/dist/`, Python caches

**Interfaces:**
- Consumes: 已停止的项目进程与用户删除授权。
- Produces: 无旧业务数据和运行产物的工作树。

- [ ] **Step 1: 构造并验证删除目标边界**

Run:
```powershell
$root = (Resolve-Path .).Path.TrimEnd('\')
$targets = @(
  (Get-ChildItem -LiteralPath $root -Filter 'django-vue-*.log' -File -ErrorAction SilentlyContinue).FullName
  (Join-Path $root '.codex-logs')
  (Join-Path $root 'backend\db.sqlite3')
  (Join-Path $root 'backend\media')
  (Join-Path $root 'data')
  (Join-Path $root 'media')
  (Join-Path $root 'frontend\dist')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
foreach ($target in $targets) {
  $full = [System.IO.Path]::GetFullPath($target)
  if (-not $full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing out-of-repository delete: $full"
  }
}
$targets
```
Expected: 每个输出路径均位于仓库内。

- [ ] **Step 2: 使用原生 PowerShell 删除已验证目标**

Run:
```powershell
foreach ($target in $targets) { Remove-Item -LiteralPath $target -Recurse -Force }
Get-ChildItem -LiteralPath $root -Directory -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -in @('__pycache__','.pytest_cache','.vite') } |
  Sort-Object FullName -Descending |
  ForEach-Object {
    $full = [System.IO.Path]::GetFullPath($_.FullName)
    if ($full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $full -Recurse -Force
    }
  }
```
Expected: 指定数据和缓存不存在；`.env` 与品牌图片仍存在。

### Task 6: 重建空库并复验基线

**Files:**
- Create ignored: `backend/db.sqlite3`

**Interfaces:**
- Consumes: 空本地状态。
- Produces: 仅包含迁移结构的 SQLite 和最新测试证据。

- [ ] **Step 1: 创建空数据库并迁移**

Run:
```powershell
Push-Location backend
$env:DJANGO_SECRET_KEY='deep-refactor-clean-db'
python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
python manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Django check failed' }
Pop-Location
```
Expected: 全部迁移成功，无新增迁移文件。

- [ ] **Step 2: 运行完整基线**

Run:
```powershell
Push-Location backend
python manage.py test --noinput
if ($LASTEXITCODE -ne 0) { throw 'Django tests failed' }
Pop-Location
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
Pop-Location
powershell -ExecutionPolicy Bypass -File scripts\tests\test-deployment-config.ps1 -SkipImageChecks
powershell -ExecutionPolicy Bypass -File scripts\tests\test-repository-structure.ps1
git diff --check
```
Expected: 所有命令 exit code `0`，迁移目录无变化。
