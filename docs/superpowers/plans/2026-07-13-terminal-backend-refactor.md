# Web Terminal 后端拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `web_terminal` 的单体 service、consumer 和 HTTP 编排拆成聚焦模块，同时保持全部 Python 导入、URL、WebSocket 路由、请求响应和数据库行为不变。

**Architecture:** 先用导入、路由和 payload 契约测试冻结公共接口；再将 `services.py` 替换为同名包并通过 `services/__init__.py` 重导出。consumer 和 API 采用同样策略，Django app、模型、迁移和路由入口不改名。

**Tech Stack:** Django、Django REST Framework、Django Channels、Python unittest/Django test runner

## Global Constraints

- 不修改 `models.py`、任何 migration 或数据库 schema。
- All names currently imported with `from web_terminal.services import name` must remain importable.
- `TerminalConsumer`、`RdpTerminalConsumer`、HTTP view 函数名及 URL names 保持不变。
- 每批移动只允许机械迁移和必要的相对导入更新，不顺带改变算法。

---

### Task 1: 冻结公开导出、路由和 payload 契约

**Files:**
- Create: `backend/web_terminal/tests/__init__.py`
- Create: `backend/web_terminal/tests/test_public_contract.py`
- Create: `backend/web_terminal/tests/test_routing_contract.py`
- Move/retain: existing tests from `backend/web_terminal/tests.py`

**Interfaces:**
- Produces: 完整服务导出清单、consumer 类契约、HTTP/WebSocket 路由契约。

- [ ] **Step 1: 生成真实 import inventory**

Run:
```powershell
git grep -n -E "from web_terminal\.services import|import web_terminal\.services|from web_terminal\.consumers import" -- '*.py' | Set-Content .codex-logs\web-terminal-imports.txt
Get-Content .codex-logs\web-terminal-imports.txt
```
Expected: 包含所有跨 app 和测试导入；该清单是唯一导出依据，不凭记忆删减。

- [ ] **Step 2: 写公开符号导入测试**

In `test_public_contract.py`, define `EXPECTED_SERVICE_EXPORTS` as the sorted union of all names found in Step 1 plus every non-private top-level class/function currently defined in `services.py`. Assert:
```python
from importlib import import_module
from django.test import SimpleTestCase

class ServiceExportContractTests(SimpleTestCase):
    def test_existing_service_exports_remain_importable(self):
        module = import_module("web_terminal.services")
        missing = [name for name in EXPECTED_SERVICE_EXPORTS if not hasattr(module, name)]
        self.assertEqual(missing, [])

    def test_consumer_classes_remain_importable(self):
        module = import_module("web_terminal.consumers")
        self.assertTrue(hasattr(module, "TerminalConsumer"))
        self.assertTrue(hasattr(module, "RdpTerminalConsumer"))
```
The committed `EXPECTED_SERVICE_EXPORTS` must be a literal complete list, including current public entries such as `TerminalConnectionError`, `LiveTerminalConnection`, payload builders, command audit/session functions, SSH helpers, remote file operations, monitor parsers, RDP parameter helpers and Guacamole helpers。

- [ ] **Step 3: 写路由契约测试**

Assert all current `web_terminal.urls.urlpatterns` names and `web_terminal.routing.websocket_urlpatterns` route strings against literal lists copied before refactor。Resolve each HTTP name and assert callback identity/name remains current。

- [ ] **Step 4: 运行旧实现确认测试通过**

Run:
```powershell
Push-Location backend
$env:DJANGO_SECRET_KEY='terminal-contract-tests'
python manage.py test web_terminal.tests.test_public_contract web_terminal.tests.test_routing_contract --noinput
Pop-Location
```
Expected: PASS against original modules。

- [ ] **Step 5: 提交契约测试**

Run:
```powershell
git add backend/web_terminal/tests backend/web_terminal/tests.py
git commit -m "test: 锁定终端后端公开接口和路由"
```

### Task 2: 拆分 payload、审计和录像服务

**Files:**
- Create: `backend/web_terminal/services/__init__.py`
- Create: `backend/web_terminal/services/payloads.py`
- Create: `backend/web_terminal/services/audit.py`
- Create: `backend/web_terminal/services/recordings.py`
- Replace: `backend/web_terminal/services.py`

**Interfaces:**
- Produces: 原 payload/session/audit/recording 函数经 `web_terminal.services` 原路径导出。

- [ ] **Step 1: 把 `services.py` 转换为包**

Run:
```powershell
git mv backend/web_terminal/services.py backend/web_terminal/services_legacy.py
New-Item -ItemType Directory backend\web_terminal\services | Out-Null
```
Expected: Python 将 `web_terminal.services` 解析到新包。

- [ ] **Step 2: 机械移动第一批函数**

Move payload builders (`host_payload`, `group_payload`, `terminal_tree_payload`, `session_payload`) to `payloads.py`; audit/risk/session creation functions to `audit.py`; recording cleanup/query helpers to `recordings.py`. Keep signatures, defaults, exception types and query ordering byte-for-byte equivalent where possible。

- [ ] **Step 3: 在包入口显式重导出**

`services/__init__.py` must use explicit imports:
```python
from .audit import classify_command_risk, create_command_audit, create_rdp_terminal_session, create_terminal_session
from .payloads import group_payload, host_payload, session_payload, terminal_tree_payload
```
Add every actually moved recording symbol explicitly；do not use wildcard imports。

- [ ] **Step 4: 让未移动符号临时从 legacy 导出**

Import remaining symbols from `web_terminal.services_legacy` explicitly so the full contract remains green during incremental migration。

- [ ] **Step 5: 运行契约和现有测试并提交**

Run:
```powershell
Push-Location backend
python manage.py test web_terminal --noinput
Pop-Location
```
Expected: PASS。

Run:
```powershell
git add backend/web_terminal/services backend/web_terminal/services_legacy.py backend/web_terminal/tests
git commit -m "refactor: 拆分终端载荷审计和录像服务"
```

### Task 3: 拆分连接和命令服务

**Files:**
- Create: `backend/web_terminal/services/connections.py`
- Create: `backend/web_terminal/services/commands.py`
- Modify: `backend/web_terminal/services/__init__.py`
- Modify: `backend/web_terminal/services_legacy.py`
- Test: `backend/web_terminal/tests/test_services_connections.py`
- Test: `backend/web_terminal/tests/test_services_commands.py`

**Interfaces:**
- Produces: `TerminalConnectionError`、`LiveTerminalConnection`、SSH client/helper、one-shot/live command functions。

- [ ] **Step 1: 增加 mock 契约测试**

Patch the same Paramiko/subprocess/network seams used by existing tests. Assert current timeout values, exception translation, audit calls and return dictionaries exactly；tests must not require a real SSH host。

- [ ] **Step 2: 运行新增测试确认覆盖旧实现**

Run:
```powershell
Push-Location backend
python manage.py test web_terminal.tests.test_services_connections web_terminal.tests.test_services_commands --noinput
Pop-Location
```
Expected: PASS before moving code。

- [ ] **Step 3: 机械移动连接和命令实现**

Move connection exception/classes/open helpers to `connections.py`; move `run_session_command`, `run_live_terminal_command`, one-shot command and related parsing/orchestration to `commands.py`. Update internal imports to `.connections`、`.audit` and `.payloads` without changing call order。

- [ ] **Step 4: 更新显式导出并删除 legacy 中已搬代码**

Every name in the literal public contract must resolve from the package root exactly once。

- [ ] **Step 5: 运行 Web Terminal 与跨 app 测试并提交**

Run:
```powershell
Push-Location backend
python manage.py test web_terminal host_management security_scanner system_management --noinput
Pop-Location
```
Expected: PASS。

Run:
```powershell
git add backend/web_terminal/services backend/web_terminal/services_legacy.py backend/web_terminal/tests
git commit -m "refactor: 拆分终端连接和命令服务"
```

### Task 4: 拆分文件、解析和监控服务

**Files:**
- Create: `backend/web_terminal/services/files.py`
- Create: `backend/web_terminal/services/file_parsers.py`
- Create: `backend/web_terminal/services/monitoring.py`
- Modify: `backend/web_terminal/services/__init__.py`
- Modify/Delete: `backend/web_terminal/services_legacy.py`
- Test: `backend/web_terminal/tests/test_file_parsers.py`
- Test: `backend/web_terminal/tests/test_monitoring_parsers.py`

**Interfaces:**
- Produces: 所有 `remote_*` normalization/stat parsing、SFTP operations、resource monitor functions。

- [ ] **Step 1: 为纯解析函数增加表驱动测试**

Copy representative existing Linux command outputs and assert exact dictionaries, permission fields, timestamps, disk/memory/cpu values, malformed-line behavior and empty-output behavior。

- [ ] **Step 2: 运行测试确认旧实现行为**

Run:
```powershell
Push-Location backend
python manage.py test web_terminal.tests.test_file_parsers web_terminal.tests.test_monitoring_parsers --noinput
Pop-Location
```
Expected: PASS。

- [ ] **Step 3: 按边界移动实现**

`file_parsers.py` contains no Django model or network access；`files.py` owns list/download/upload/create/rename/delete/properties operations；`monitoring.py` owns resource command execution and monitor parsing。Preserve public signatures and result key spelling。

- [ ] **Step 4: 清空并删除 legacy 文件**

After every symbol is moved and contract passes:
```powershell
git rm backend/web_terminal/services_legacy.py
```

- [ ] **Step 5: 验证并提交**

Run:
```powershell
Push-Location backend
python manage.py test web_terminal host_management security_scanner system_management --noinput
Pop-Location
```
Expected: PASS。

Run:
```powershell
git add backend/web_terminal/services backend/web_terminal/tests backend/web_terminal/services_legacy.py
git commit -m "refactor: 拆分终端文件和监控服务"
```
If `services_legacy.py` is already removed, stage with `git add -A backend/web_terminal` instead。

### Task 5: 拆分 RDP 与 Guacamole 服务

**Files:**
- Create: `backend/web_terminal/services/rdp.py`
- Create: `backend/web_terminal/services/guacamole.py`
- Modify: `backend/web_terminal/services/__init__.py`
- Test: `backend/web_terminal/tests/test_rdp_services.py`
- Test: `backend/web_terminal/tests/test_guacamole_protocol.py`

**Interfaces:**
- Produces: RDP connection parameters、recording cleanup、Guacamole instruction parsing/encoding helpers。

- [ ] **Step 1: 增加无外部服务的参数和协议测试**

Assert current defaults, credential mapping, width/height/dpi handling, instruction escaping/splitting and invalid payload behavior using exact pre-refactor results。

- [ ] **Step 2: 移动实现并显式导出**

Keep Guacamole wire-format pure helpers in `guacamole.py`; keep Django settings/model/recording orchestration in `rdp.py`. Preserve exception classes and messages used by consumers/tests。

- [ ] **Step 3: 运行全部服务测试并提交**

Run:
```powershell
Push-Location backend
python manage.py test web_terminal --noinput
Pop-Location
```
Expected: PASS。

Run:
```powershell
git add backend/web_terminal/services backend/web_terminal/tests
git commit -m "refactor: 拆分终端 RDP 和 Guacamole 服务"
```

### Task 6: 拆分 WebSocket consumers

**Files:**
- Create: `backend/web_terminal/consumers/__init__.py`
- Create: `backend/web_terminal/consumers/protocol.py`
- Create: `backend/web_terminal/consumers/ssh.py`
- Create: `backend/web_terminal/consumers/rdp.py`
- Replace: `backend/web_terminal/consumers.py`
- Modify: `backend/web_terminal/routing.py`
- Test: `backend/web_terminal/tests/test_consumer_contract.py`

**Interfaces:**
- Produces: `TerminalConsumer`、`RdpTerminalConsumer` 从原包路径导入；route strings 不变。

- [ ] **Step 1: 增加 consumer 消息契约测试**

Use Channels communicators or direct async method tests with patched connections. Assert current auth rejection、connect/accept、message type dispatch、close codes and serialized JSON keys。

- [ ] **Step 2: 将公共 protocol helper 抽到 `protocol.py`**

Move only pure decode/encode/validation helpers first and rerun consumer tests。

- [ ] **Step 3: 分别移动 SSH 与 RDP consumer**

`ssh.py` exports `TerminalConsumer`; `rdp.py` exports `RdpTerminalConsumer`; `consumers/__init__.py` explicitly re-exports both。Keep `routing.py` importing from `web_terminal.consumers` so the public path is exercised。

- [ ] **Step 4: 验证并提交**

Run:
```powershell
Push-Location backend
python manage.py test web_terminal --noinput
Pop-Location
```
Expected: PASS。

Run:
```powershell
git add -A backend/web_terminal
git commit -m "refactor: 拆分终端 WebSocket consumers"
```

### Task 7: 拆分 HTTP API 编排

**Files:**
- Create: `backend/web_terminal/api/__init__.py`
- Create: `backend/web_terminal/api/sessions.py`
- Create: `backend/web_terminal/api/files.py`
- Create: `backend/web_terminal/api/monitoring.py`
- Create: `backend/web_terminal/api/recordings.py`
- Modify: `backend/web_terminal/views.py`
- Preserve: `backend/web_terminal/urls.py`

**Interfaces:**
- Produces: 原 view 名继续从 `web_terminal.views` 导入，URL names 和 response payload 不变。

- [ ] **Step 1: 按现有 URL 为每个 endpoint 增加 APIClient 契约测试**

For each URL, assert method、status、authentication requirement、required fields and exact top-level response keys. Patch SSH/RDP/network side effects。

- [ ] **Step 2: 将实现按 session/file/monitoring/recording 移入 api 模块**

Keep `views.py` as explicit re-export module:
```python
from .api.files import (
    terminal_file_create_directory, terminal_file_create_file,
    terminal_file_create_symlink, terminal_file_delete,
    terminal_file_download, terminal_file_download_attachment,
    terminal_file_download_list, terminal_file_list,
    terminal_file_properties, terminal_file_properties_update,
    terminal_file_rename, terminal_file_upload,
)
from .api.monitoring import terminal_monitor
from .api.recordings import terminal_rdp_recording, terminal_session_recording
from .api.sessions import (
    session_audits, terminal_commands, terminal_quick_command_detail,
    terminal_quick_commands, terminal_quick_commands_reorder,
    terminal_sessions, terminal_tree,
)
```
Keep helper/decorator functions (`next_quick_command_sort_order`, `terminal_login_required`, `quick_command_permission_required`, `session_audit_permission_required`, `quick_command_queryset`, `parse_positive_int`, `parse_audit_datetime`) in the API module that consumes them or in `api/common.py`; retain their names if tests or other modules import them?

- [ ] **Step 3: 运行全量后端验证**

Run:
```powershell
Push-Location backend
python manage.py check
python manage.py test --noinput
Pop-Location
git diff --check
```
Expected: 全部 PASS，测试数不得低于基线，migration files unchanged。

- [ ] **Step 4: 提交 API 拆分**

Run:
```powershell
git add backend/web_terminal/api backend/web_terminal/views.py backend/web_terminal/tests
git commit -m "refactor: 拆分终端 HTTP API 编排"
```
