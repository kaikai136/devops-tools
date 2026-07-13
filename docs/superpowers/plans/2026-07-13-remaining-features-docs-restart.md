# 剩余功能、文档、重建与重启 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将剩余页面迁入 feature 架构，重组项目文档，执行全量验证，重建空数据库，并在合并后的 `main` 上重新启动和浏览器冒烟验证本地程序。

**Architecture:** 按业务域逐个迁移，页面只编排 feature，旧路径在调用方全部切换前保留兼容入口。文档按读者任务拆为开发、部署、架构、故障排查和迁移历史；最后清理兼容层、合并分支、空库迁移并重启。

**Tech Stack:** Vue 3、TypeScript、Django、PowerShell、Docker Compose（可用时）、Markdown

## Global Constraints

- 每个业务域单独测试和提交，不跨域顺手重写。
- 不改变 API、页面交互、权限规则、模型和迁移历史。
- `MIGRATION_PLAN.md` 仅在有效内容进入 `docs/migration-history.md` 后删除。
- 最终服务必须从合并后的本地 `main` 启动，日志写入 `.codex-logs/`。

---

### Task 1: 迁移剩余前端业务域

**Files:**
- Create: `frontend/src/features/dashboard/`
- Create: `frontend/src/features/security/`
- Create: `frontend/src/features/users/`
- Create: `frontend/src/features/settings/`
- Create: `frontend/src/features/authenticators/`
- Create: `frontend/src/features/passwords/`
- Create: `frontend/src/features/network/`
- Create: `frontend/src/features/audits/`
- Create/Modify: `frontend/src/pages/`
- Modify: current callers under `frontend/src/App.vue`, `frontend/src/components/`, `frontend/src/composables/features/`

**Interfaces:**
- Produces: 每个 feature 的 `api/components/composables/types` 边界；pages 只编排 feature。

- [ ] **Step 1: 为每个业务域生成文件和 API inventory**

Run separately per domain:
```powershell
git grep -n -i "dashboard" -- frontend/src
git grep -n -i "security\|scanner" -- frontend/src
git grep -n -i "user\|permission\|role" -- frontend/src
git grep -n -i "setting" -- frontend/src
git grep -n -i "authenticator\|totp" -- frontend/src
git grep -n -i "password" -- frontend/src
git grep -n -i "network" -- frontend/src
git grep -n -i "audit" -- frontend/src
```
Expected: 每个域先形成明确迁移清单，禁止按目录整批盲移。

- [ ] **Step 2: 按固定顺序逐域迁移**

Order: dashboard → security → users → settings → authenticators → passwords → network → audits。For each domain:
1. add pure function/API tests using current payload examples；
2. Use `git mv` into the matching literal directory: `features/dashboard`, `features/security`, `features/users`, `features/settings`, `features/authenticators`, `features/passwords`, `features/network`, or `features/audits`.
3. move page composition into `pages`；
4. retain old path as explicit re-export/wrapper if still referenced；
5. run frontend tests/build；
6. commit only that domain。

- [ ] **Step 3: 使用统一提交格式**

Run one verified commit for each domain:
```powershell
git add frontend/src; git commit -m "refactor: ???????????"
git add frontend/src; git commit -m "refactor: ????????????"
git add frontend/src; git commit -m "refactor: ????????????"
git add frontend/src; git commit -m "refactor: ????????????"
git add frontend/src; git commit -m "refactor: ???????????"
git add frontend/src; git commit -m "refactor: ????????????"
git add frontend/src; git commit -m "refactor: ????????????"
git add frontend/src; git commit -m "refactor: ??????????"
```
Execute each line only after the matching domain?s tests/build pass; never run all eight commands against one combined diff?

- [ ] **Step 4: 清理无引用兼容路径**

Run:
```powershell
git grep -n "src/components\|src/composables/features" -- frontend/src
```
Inspect actual imports, then remove only wrapper/export files with zero callers. Keep common UI only under `shared` and feature-owned UI under its feature。

- [ ] **Step 5: 全量前端验证**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
git diff --check
```
Expected: PASS。

### Task 2: 收紧 App 和页面边界

**Files:**
- Modify: `frontend/src/App.vue`
- Create/Modify: `frontend/src/app/AppShell.vue`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/pages/*.vue`

**Interfaces:**
- Produces: `App.vue` 只负责根上下文和 shell；page 只组合 feature，不直接实现跨域 API。

- [ ] **Step 1: 增加入口构建契约**

Assert both main and terminal Vite inputs remain present in `vite.config.ts`; assert `main.ts` and `terminal.ts` mount the same element IDs as pre-refactor using a small source-contract Vitest test or PowerShell structure test。

- [ ] **Step 2: 将 shell markup 抽入 `app/AppShell.vue`**

Move navigation/header/sidebar/page selection only；retain all existing classes, labels and transition behavior。Use app context/composables rather than feature-internal imports。

- [ ] **Step 3: 验证并提交**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
```
Expected: PASS。

Run:
```powershell
git add frontend/src/App.vue frontend/src/app frontend/src/main.ts frontend/src/pages
git commit -m "refactor: 收紧前端应用壳和页面边界"
```

### Task 3: 重组 README 和 docs

**Files:**
- Modify: `README.md`
- Create: `docs/development.md`
- Create: `docs/deployment.md`
- Create: `docs/architecture.md`
- Create: `docs/troubleshooting.md`
- Create: `docs/migration-history.md`
- Delete: `MIGRATION_PLAN.md`
- Preserve: `docs/superpowers/specs/2026-07-13-deep-structure-refactor-design.md`
- Preserve: `docs/superpowers/plans/*.md`

**Interfaces:**
- Produces: 一个短 README 和五份按任务组织的长期文档。

- [ ] **Step 1: 提取现有有效内容清单**

Run:
```powershell
Select-String -Path README.md,MIGRATION_PLAN.md -Pattern '^#{1,4} ' | Select-Object Path,LineNumber,Line
```
Expected: 每个现有章节映射到一个目标文档，避免遗漏真实部署变量、端口、命令和历史约束。

- [ ] **Step 2: 重写 README**

README must contain: project purpose、feature overview、prerequisites、clone-and-run quick start、default `.env` explanation、first-start automatic secret behavior、links to five docs、test commands。Keep command examples executable from repository root。

- [ ] **Step 3: 编写开发和架构文档**

`docs/development.md` must include local backend/frontend setup、directory map、feature/service boundaries、test/lint/build commands and generated-file rules。

`docs/architecture.md` must include frontend `app/pages/features/shared` responsibilities、backend Django app/service/API/consumer responsibilities、HTTP/SSH/SFTP/RDP data flows and compatibility facade policy。

- [ ] **Step 4: 编写部署和故障排查文档**

`docs/deployment.md` must include default `.env`、all current environment variables with required/default/secret classification、Docker build/up commands、automatic secret lifecycle、remote `.env` preservation、upgrade/backup/restore steps。

`docs/troubleshooting.md` must include ports、migration/static file issues、SSH/SFTP/RDP/Guacamole checks、log locations `.codex-logs/` or container logs and safe reset steps。

- [ ] **Step 5: 合并迁移历史后删除旧文件**

Write `docs/migration-history.md` from still-valid `MIGRATION_PLAN.md` content and completed design/plan history. Then:
```powershell
git rm MIGRATION_PLAN.md
```
Expected: `git grep -n "MIGRATION_PLAN.md"` only finds historical plan/spec mentions that intentionally document deletion；README and active docs do not link it。

- [ ] **Step 6: 验证文档命令和链接**

Run:
```powershell
$redFlags = @('T' + 'BD', 'T' + 'ODO', 'implement ' + 'later', 'fill in ' + 'details')
foreach ($flag in $redFlags) {
  git grep -n -F $flag -- README.md docs ':!docs/superpowers/plans/2026-07-10-default-env-auto-secret.md'
  if ($LASTEXITCODE -eq 0) { throw "Documentation placeholder found: $flag" }
}
git diff --check
powershell -ExecutionPolicy Bypass -File scripts\tests\test-deployment-config.ps1 -SkipImageChecks
```
Expected: 无占位符、无空白错误、部署契约 PASS。

- [ ] **Step 7: 提交文档重组**

Run:
```powershell
git add README.md docs MIGRATION_PLAN.md
git commit -m "docs: 重组开发部署架构和排障文档"
```
If the deleted file cannot be passed literally, use `git add -A README.md docs MIGRATION_PLAN.md`。

### Task 4: 最终静态和自动化验证

**Files:**
- Review: all changed files

**Interfaces:**
- Produces: 最新、完整、可复现的验证证据。

- [ ] **Step 1: 运行仓库和部署契约**

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\tests\test-repository-structure.ps1
powershell -ExecutionPolicy Bypass -File scripts\tests\test-deployment-config.ps1 -SkipImageChecks
```
Expected: both exit code `0`。

- [ ] **Step 2: 运行后端全量验证**

Run:
```powershell
Push-Location backend
$env:DJANGO_SECRET_KEY='deep-refactor-verification'
python manage.py check
python manage.py test --noinput
python manage.py migrate --noinput
Pop-Location
```
Expected: commands PASS；test count not below recorded baseline；no migration files generated。

- [ ] **Step 3: 运行前端全量验证**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
```
Expected: PASS。

- [ ] **Step 4: 检查引用、生成文件和 diff**

Run:
```powershell
git diff --check
git status --short
git grep -n "login-implemented.png\|login-prototype.png\|prototype-home.png\|restored-login.png" -- ':!docs/superpowers/*'
git status --short backend/*/migrations
```
Expected: 无意外图片引用、无 migration 改动、无未计划生成文件。

- [ ] **Step 5: Docker CLI 可用时验证 Compose**

Run:
```powershell
if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker compose config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'docker compose config failed' }
} else {
  Write-Host 'Docker CLI unavailable; image verification not executed.'
}
```
Expected: 可用时 PASS；不可用时明确记录“未执行”，不得写成通过。

### Task 5: 质量复核并合并到 main

**Files:**
- Review: branch diff

**Interfaces:**
- Produces: 经用户选择后合并的 `main`。

- [ ] **Step 1: 使用 code-quality-guard 复核**

Inspect security boundaries, cleanup paths, SSH/RDP resource cleanup, timer/listener disposal, API compatibility, duplicate logic and files still over reasonable responsibility size. Fix only verified issues and rerun relevant tests。

- [ ] **Step 2: 确认 worktree 清洁**

Run:
```powershell
git status --short --branch
git log --oneline --decorate main..HEAD
git diff --stat main...HEAD
```
Expected: clean branch, phase-separated commits。

- [ ] **Step 3: 使用 finishing-a-development-branch 流程**

Offer merge/PR/keep options. If user chooses local merge, execute from primary workspace:
```powershell
git switch main
git merge --no-ff refactor/deep-structure
```
Expected: merge succeeds；if conflicts occur, stop and resolve with targeted tests before continuing。

### Task 6: 在合并后的 main 重建本地数据并启动

**Files:**
- Create ignored: `backend/db.sqlite3`
- Create ignored: `.codex-logs/backend-main.out.log`
- Create ignored: `.codex-logs/backend-main.err.log`
- Create ignored: `.codex-logs/frontend-main.out.log`
- Create ignored: `.codex-logs/frontend-main.err.log`

**Interfaces:**
- Produces: 运行于本地 `main` 的后端和前端。

- [ ] **Step 1: 确认当前是合并后的 main**

Run:
```powershell
git branch --show-current
git status --short
```
Expected: branch `main`, clean tracked worktree。

- [ ] **Step 2: 再次安全删除旧本地数据库和日志**

Resolve each target under repository root and use `Remove-Item -LiteralPath` only after boundary validation, following repository-cleanup plan。Do not delete `.env`。

- [ ] **Step 3: 迁移空数据库**

Run:
```powershell
Push-Location backend
python manage.py migrate --noinput
python manage.py check
Pop-Location
```
Expected: PASS。

- [ ] **Step 4: 隐藏启动后端和前端**

Run from repository root with process commands matching the project’s documented local entrypoints. Use:
```powershell
New-Item -ItemType Directory -Force .codex-logs | Out-Null
$backend = Start-Process -FilePath 'python' -ArgumentList 'manage.py','runserver','127.0.0.1:8000' -WorkingDirectory (Join-Path (Resolve-Path .) 'backend') -RedirectStandardOutput (Join-Path (Resolve-Path .) '.codex-logs\backend-main.out.log') -RedirectStandardError (Join-Path (Resolve-Path .) '.codex-logs\backend-main.err.log') -WindowStyle Hidden -PassThru
$frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1' -WorkingDirectory (Join-Path (Resolve-Path .) 'frontend') -RedirectStandardOutput (Join-Path (Resolve-Path .) '.codex-logs\frontend-main.out.log') -RedirectStandardError (Join-Path (Resolve-Path .) '.codex-logs\frontend-main.err.log') -WindowStyle Hidden -PassThru
```
Expected: both processes remain running。

- [ ] **Step 5: 使用 readiness polling**

Poll documented backend/frontend URLs with `Invoke-WebRequest` every second, maximum 60 seconds；fail early if either process exits。Do not rely on a fixed sleep。

### Task 7: 浏览器冒烟验收

**Files:**
- No source changes unless a reproducible regression is found.

**Interfaces:**
- Produces: 登录、仪表盘、主机管理、安全扫描和 Web Terminal 入口的浏览器证据。

- [ ] **Step 1: 使用 Browser 打开本地登录页**

Verify page renders, brand assets load, no uncaught console errors, and login form interaction matches current behavior。

- [ ] **Step 2: 登录后依次检查主要页面**

Verify dashboard、host management、security scanner and Web Terminal entry load and basic controls respond。Use a fresh empty-database account/setup path documented by the application；do not invent credentials。

- [ ] **Step 3: 记录外部连接限制**

If no reachable SSH/RDP test host is configured, report those real connection flows as not executed while confirming their entry UI and client initialization only。
