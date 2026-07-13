# 深度代码结构重构与仓库整理设计

**日期：** 2026-07-13
**状态：** 已确认
**目标分支：** 从 `main` 创建独立功能分支执行

## 1. 目标

在不改变现有功能、页面交互、HTTP/WebSocket API 路径、请求响应格式、Django 模型和迁移历史的前提下，重组前后端代码，使业务职责聚合、超大文件可维护、跨模块依赖清晰，并清理无用文件、本地运行数据和过期文档。

## 2. 已确认边界

- 保持现有功能和用户界面行为不变。
- 保持所有 HTTP API、WebSocket 路径、字段名和响应结构不变。
- 保持数据库模型、迁移文件及迁移顺序不变；不新增数据迁移。
- 可以删除全部本地运行日志和本地业务数据，包括 SQLite、媒体文件和本地 RDP 录像。
- 可以删除未被代码或文档引用的历史原型截图。
- 必须保留实际使用的品牌图片 `frontend/public/captain-banner.png` 和 `frontend/public/ops-captain-icon.png`。
- 每个阶段必须保持可构建、可测试；禁止一次性无验证地移动全部代码。

## 3. 现状与主要问题

- `frontend/src/components/terminal/WebTerminalPage.vue` 约 5922 行，混合 SSH 终端、SFTP、RDP、录像、监控、快捷命令和大量弹窗状态。
- `backend/web_terminal/services.py` 约 1389 行，混合连接、命令、审计、文件传输、监控、RDP 和解析逻辑。
- `frontend/src/composables/features/useHostManager.ts` 约 1368 行，承担主机、分组、凭据、导入导出、验证和批量操作。
- `frontend/src/components/tools/HostManager.vue` 约 1070 行，视图职责过多。
- `frontend/src/composables/useAppState.ts` 和 `frontend/src/App.vue` 聚合过多全局状态和页面编排逻辑。
- 根目录存在 4 张未引用原型图及大量本地日志；`MIGRATION_PLAN.md` 已无引用。
- README 同时承载介绍、开发、部署和运维细节，入口过长。

## 4. 目标架构

### 4.1 前端

采用业务功能优先结构：

```text
frontend/src/
├── app/                 # 应用装配、上下文、导航、全局会话和壳层
├── pages/               # 页面级入口，仅编排 feature
├── features/            # hosts、terminal、security、users、settings 等业务域
├── shared/              # 无业务归属的组件、HTTP、类型、通用 composable 和工具
├── main.ts
└── terminal.ts
```

每个 feature 可以包含 `api/`、`components/`、`composables/`、`types.ts` 和 `utils.ts`，文件仅承担一个清晰职责。迁移期间保留必要的兼容导出，最终移除没有引用的旧路径。

### 4.2 后端

保留现有 Django app 和 URL namespace，不重命名模型或 app。只在复杂 app 内拆包：

```text
backend/web_terminal/
├── api/                 # HTTP 参数解析和响应编排
├── services/            # connections、commands、files、monitoring、audit、rdp
├── consumers/           # SSH 与 RDP WebSocket consumer
├── models.py
├── urls.py
└── tests/
```

`web_terminal.services` 由单文件变为包，`services/__init__.py` 继续导出原有公开符号，使其他 app 的导入路径保持不变。视图函数名和 URL patterns 保持不变。

## 5. 分阶段策略

1. 建立清理保护、结构契约和基线测试。
2. 清理本地日志、数据库、媒体、录像、缓存和未引用截图。
3. 重构前端 app/shared 基础层，但保留页面行为。
4. 重构主机管理 feature。
5. 拆分后端 Web Terminal 服务和 consumer。
6. 拆分前端 Web Terminal 页面。
7. 整理用户、权限、安全扫描、系统设置等剩余功能。
8. 重组 README 和 docs，执行全量验证，创建空数据库并重新启动本地程序。

## 6. 文件清理规则

删除 Git 跟踪文件：

- `login-implemented.png`
- `login-prototype.png`
- `prototype-home.png`
- `restored-login.png`
- `MIGRATION_PLAN.md`（有效内容合并进新文档后）

删除本地忽略文件/目录：

- 根目录 `django-vue-*.log`
- `.codex-logs/`
- `backend/db.sqlite3`
- `backend/media/`
- 根目录 `data/`、`media/`
- 本地 RDP 录像目录或本地 Compose volume（仅在本机存在且能明确识别时）
- Python/Node/Vite 缓存和已生成的 `frontend/dist/`

删除前必须停止仅属于本项目的本地进程，并验证所有递归删除目标解析后仍位于仓库根目录内。不得删除 `.env`、源代码、虚拟环境之外的系统文件或无法确认归属的 Docker volume。

## 7. 文档目标

- `README.md`：项目简介、功能概览、快速启动、文档导航。
- `docs/development.md`：本地环境、目录结构、编码边界、测试命令。
- `docs/deployment.md`：Docker、环境变量、密钥、远程部署、升级和备份。
- `docs/architecture.md`：前端 feature 架构、后端 app/service 边界、关键数据流。
- `docs/troubleshooting.md`：端口、迁移、静态文件、SSH/RDP、日志排查。
- `docs/migration-history.md`：从旧 Vue/Django 结构迁移而来的仍有效历史信息。

## 8. 验证标准

- Django 全量测试保持通过（当前基线 182 个）。
- 前端 `npm run build` 通过，并增加结构/纯函数测试入口。
- 部署契约、entrypoint 密钥生命周期和远程 `.env` 保留测试通过。
- 所有原 HTTP/WebSocket URL 仍存在。
- `git grep` 不再引用被删除文件或旧模块路径。
- 根目录不再出现运行日志和历史原型图。
- 新建空数据库后迁移成功，前后端可重新启动。
- 浏览器冒烟验证登录、仪表盘、主机管理、安全扫描和 Web Terminal 入口。

## 9. 风险控制

- 每个业务域单独提交，禁止将主机管理和终端重构混入同一提交。
- 先增加契约测试，再移动代码。
- 对后端使用兼容导出，避免跨 app 导入立即失效。
- 对前端先更新入口和导入，再删除旧文件；每批移动后立即构建。
- 若某阶段出现行为回归，只回退该阶段，不影响已经验证的清理和基础层工作。
