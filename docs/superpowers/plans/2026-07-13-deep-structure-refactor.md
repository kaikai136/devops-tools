# 深度代码结构重构总实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在完全保持现有功能、页面交互、HTTP/WebSocket 契约、Django 模型和迁移历史的前提下，完成仓库清理、前后端模块化重构、文档整理、空库重建和本地重启验证。

**Architecture:** 采用“业务功能优先、分阶段迁移”。前端逐步形成 `app/pages/features/shared`，后端保留 Django app 边界并在 `web_terminal` 内拆分 service、consumer 与 API；迁移期间通过 facade 和包级兼容导出维持旧接口。

**Tech Stack:** Django、Django Channels、Vue 3、TypeScript、Vite、Vitest、PowerShell、Docker Compose（仅在本机 CLI 可用时验证）

## Global Constraints

- 保持现有功能和用户界面行为不变。
- 保持所有 HTTP API、WebSocket 路径、字段名和响应结构不变。
- 保持数据库模型、迁移文件及迁移顺序不变；不新增数据迁移。
- 保留 `.env`、`frontend/public/captain-banner.png`、`frontend/public/ops-captain-icon.png` 和首次启动自动密钥机制。
- 已获用户授权删除本地 SQLite、媒体、RDP 录像、日志、缓存和构建产物。
- 每个阶段先写契约测试，再迁移实现，随后运行针对性测试和构建并单独提交。
- 后端 `from web_terminal.services import ...`、consumer 类名、URL pattern 和 view 函数名保持兼容。
- 前端 `/terminal.html`、查询参数、WebSocket URL、快捷键、tab、SFTP、RDP、录像和监控行为保持兼容。

---

## 工作分解与顺序

### Task 1: 建立隔离工作区

**Files:**
- Read: `docs/superpowers/specs/2026-07-13-deep-structure-refactor-design.md`
- Read: `docs/superpowers/plans/2026-07-13-repository-cleanup-baseline.md`

**Interfaces:**
- Consumes: `main` 当前已验证状态。
- Produces: `.worktrees/deep-structure-refactor` 与 `refactor/deep-structure`。

- [ ] **Step 1: 使用 worktree 技能创建隔离分支**

Run:
```powershell
git worktree add .worktrees/deep-structure-refactor -b refactor/deep-structure main
```
Expected: 新 worktree 指向 `refactor/deep-structure`，主工作区保持 `main`。

- [ ] **Step 2: 验证隔离状态**

Run:
```powershell
git -C .worktrees/deep-structure-refactor status --short --branch
```
Expected: 首行为 `## refactor/deep-structure`，没有业务代码改动。

### Task 2: 执行仓库清理和基线计划

**Files:**
- Execute: `docs/superpowers/plans/2026-07-13-repository-cleanup-baseline.md`

**Interfaces:**
- Consumes: 隔离 worktree。
- Produces: 清洁仓库、结构守卫、可复现基线。

- [ ] **Step 1: 逐项执行清理计划**

Run:
```powershell
Get-Content docs\superpowers\plans\2026-07-13-repository-cleanup-baseline.md -Encoding utf8
```
Expected: 所有复选项按顺序执行；不得跳过路径边界和项目进程归属检查。

- [ ] **Step 2: 通过阶段门禁**

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\tests\test-repository-structure.ps1
```
Expected: exit code `0`。

### Task 3: 执行前端基础层和主机 feature 计划

**Files:**
- Execute: `docs/superpowers/plans/2026-07-13-frontend-foundation-hosts.md`

**Interfaces:**
- Consumes: 结构守卫和当前 Vue 入口。
- Produces: `app/shared/pages/features/hosts`、Vitest、兼容 facade。

- [ ] **Step 1: 按 TDD 顺序执行前端计划**

Run:
```powershell
Get-Content docs\superpowers\plans\2026-07-13-frontend-foundation-hosts.md -Encoding utf8
```
Expected: 每次移动后 `npm run test:run` 和 `npm run build` 均通过。

### Task 4: 执行 Web Terminal 后端计划

**Files:**
- Execute: `docs/superpowers/plans/2026-07-13-terminal-backend-refactor.md`

**Interfaces:**
- Consumes: 原 `web_terminal.services`、`consumers.py`、`views.py` 契约。
- Produces: 兼容的 `services/`、`consumers/`、`api/` 包。

- [ ] **Step 1: 先锁定公开导出和路由契约，再拆包**

Run:
```powershell
Get-Content docs\superpowers\plans\2026-07-13-terminal-backend-refactor.md -Encoding utf8
```
Expected: 每批拆分后 Django Web Terminal 测试和跨 app 导入测试通过。

### Task 5: 执行 Web Terminal 前端计划

**Files:**
- Execute: `docs/superpowers/plans/2026-07-13-terminal-frontend-refactor.md`

**Interfaces:**
- Consumes: 已稳定的后端 HTTP/WebSocket 契约。
- Produces: `features/terminal` 与薄页面入口。

- [ ] **Step 1: 后端计划验收后再开始前端终端拆分**

Run:
```powershell
Get-Content docs\superpowers\plans\2026-07-13-terminal-frontend-refactor.md -Encoding utf8
```
Expected: 不与 Task 4 并行；每个 composable 或组件批次独立测试和构建。

### Task 6: 执行剩余 feature、文档、重建和重启计划

**Files:**
- Execute: `docs/superpowers/plans/2026-07-13-remaining-features-docs-restart.md`

**Interfaces:**
- Consumes: 已迁移的基础层、主机和终端模块。
- Produces: 完整 feature 架构、六份入口文档、空数据库和已验证本地服务。

- [ ] **Step 1: 迁移剩余业务域并整理文档**

Run:
```powershell
Get-Content docs\superpowers\plans\2026-07-13-remaining-features-docs-restart.md -Encoding utf8
```
Expected: 每个业务域单独提交，`MIGRATION_PLAN.md` 的有效内容先合并后删除。

- [ ] **Step 2: 执行最终全量验证**

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\tests\test-repository-structure.ps1
powershell -ExecutionPolicy Bypass -File scripts\tests\test-deployment-config.ps1 -SkipImageChecks
$env:DJANGO_SECRET_KEY='deep-refactor-verification'
Push-Location backend
python manage.py check
python manage.py test --noinput
python manage.py migrate --noinput
Pop-Location
Push-Location frontend
npm run test:run
npm run build
Pop-Location
git diff --check
```
Expected: 全部 exit code `0`；Django 测试数不得少于基线记录。

### Task 7: 代码质量复核与分支收尾

**Files:**
- Review: 全部已修改文件

**Interfaces:**
- Consumes: 已通过全量验证的功能分支。
- Produces: 可合并分支和明确验收记录。

- [ ] **Step 1: 使用 code-quality-guard 复核安全、性能、正确性与维护性**

Run:
```powershell
git diff --stat main...HEAD
git diff --check main...HEAD
```
Expected: 没有空白错误、调试代码、敏感信息或意外生成文件。

- [ ] **Step 2: 使用 verification-before-completion 记录最新证据**

Run: 重新执行 Task 6 Step 2 的完整命令集。
Expected: 最新一次运行全部成功，而不是引用早期结果。

- [ ] **Step 3: 使用 finishing-a-development-branch 提供合并选项**

Run:
```powershell
git status --short --branch
git log --oneline --decorate main..HEAD
```
Expected: 工作树清洁，提交按阶段分离，再由用户决定合并、PR 或保留分支。
