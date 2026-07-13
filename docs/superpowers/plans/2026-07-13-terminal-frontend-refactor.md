# Web Terminal 前端拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将约 5922 行 Web Terminal 页面和约 3048 行终端样式拆为可测试的 terminal feature、聚焦组件和薄页面入口，保持 SSH、SFTP、RDP、录像、监控及快捷命令行为不变。

**Architecture:** 先抽类型、API 和纯函数，再按 tabs→SSH→resize→SFTP→RDP→monitor→commands→recordings 顺序提取 composable，最后拆组件和页面。旧 `components/terminal/WebTerminalPage.vue` 在迁移期作为兼容包装，直到所有入口改用 `pages/WebTerminalPage.vue`。

**Tech Stack:** Vue 3、TypeScript、Vite、Vitest、xterm.js、guacamole-common-js、asciinema-player

## Global Constraints

- 保持 `/terminal.html`、所有查询参数和 WebSocket URL 不变。
- 保持键盘快捷键、tab 激活/关闭顺序、SFTP 字段和 RDP input/resize/clipboard 行为不变。
- 不改变后端 payload 或引入新的网络请求。
- 每个 composable 只拥有一类生命周期副作用，并提供清理函数。

---

### Task 1: 冻结入口和纯逻辑契约

**Files:**
- Create: `frontend/src/features/terminal/types.ts`
- Create: `frontend/src/features/terminal/api/terminal.ts`
- Create: `frontend/src/features/terminal/utils/paths.ts`
- Create: `frontend/src/features/terminal/utils/protocol.ts`
- Test: `frontend/src/features/terminal/utils/__tests__/paths.test.ts`
- Test: `frontend/src/features/terminal/utils/__tests__/protocol.test.ts`

**Interfaces:**
- Produces: 终端共享类型、原 HTTP API 包装、无 DOM/网络的路径和协议纯函数。

- [ ] **Step 1: 记录现有入口和网络字符串**

Run:
```powershell
git grep -n -E "terminal\.html|WebSocket|/api/|ws://|wss://|URLSearchParams" -- frontend/src/components/terminal/WebTerminalPage.vue frontend/src/terminal.ts frontend/index.html frontend/terminal.html | Set-Content .codex-logs\terminal-frontend-contract.txt
```
Expected: 得到完整 HTTP、WebSocket、entry 和 query 参数清单。

- [ ] **Step 2: 为路径与协议函数写表驱动测试**

Copy exact current examples for POSIX path joining/parent/name, terminal query parsing, Guacamole message handling or file-size formatting。Assert unchanged strings and edge cases such as root、spaces、Unicode and trailing slash。

- [ ] **Step 3: 抽取纯函数并运行测试**

Run:
```powershell
Push-Location frontend
npm run test:run -- src/features/terminal/utils/__tests__
npm run build
Pop-Location
```
Expected: PASS；network URL strings unchanged。

- [ ] **Step 4: 提交基础模块**

Run:
```powershell
git add frontend/src/features/terminal
git commit -m "refactor: 建立终端前端类型和纯函数边界"
```

### Task 2: 提取 tab 与 SSH 生命周期

**Files:**
- Create: `frontend/src/features/terminal/composables/useTerminalTabs.ts`
- Create: `frontend/src/features/terminal/composables/useSshTerminal.ts`
- Create: `frontend/src/features/terminal/composables/useTerminalResize.ts`
- Test: `frontend/src/features/terminal/composables/__tests__/useTerminalTabs.test.ts`
- Test: `frontend/src/features/terminal/composables/__tests__/useTerminalResize.test.ts`
- Modify: `frontend/src/components/terminal/WebTerminalPage.vue`

**Interfaces:**
- Produces: tab 创建/激活/关闭 API，SSH connect/send/disconnect API，resize observer/window listener 生命周期。

- [ ] **Step 1: 写 tab 状态机测试**

Assert initial state、duplicate host behavior、active tab after closing active/non-active tabs、tab order and terminal disposal count using the exact current behavior。

- [ ] **Step 2: 写 resize 清理测试**

Fake timers and mock `ResizeObserver`/window listeners。Assert resize debounce timing、fit call、WebSocket resize message fields and all listeners removed on dispose。

- [ ] **Step 3: 先抽 tabs，再抽 SSH，再抽 resize**

Move existing refs and methods without renaming the values consumed by the page. `useSshTerminal` owns xterm/WebSocket lifecycle；`useTerminalResize` owns observation/listeners；`useTerminalTabs` calls provided dispose callback instead of directly knowing WebSocket/xterm internals。

- [ ] **Step 4: 每批运行测试和构建**

Run after each extraction:
```powershell
Push-Location frontend
npm run test:run -- src/features/terminal/composables/__tests__
npm run build
Pop-Location
```
Expected: PASS。

- [ ] **Step 5: 提交 SSH 基础拆分**

Run:
```powershell
git add frontend/src/features/terminal frontend/src/components/terminal/WebTerminalPage.vue
git commit -m "refactor: 拆分终端标签和 SSH 生命周期"
```

### Task 3: 提取 SFTP 状态和组件

**Files:**
- Create: `frontend/src/features/terminal/composables/useSftpBrowser.ts`
- Create: `frontend/src/features/terminal/components/files/SftpPanel.vue`
- Create: `frontend/src/features/terminal/components/files/FileToolbar.vue`
- Create: `frontend/src/features/terminal/components/files/FileTable.vue`
- Create: `frontend/src/features/terminal/components/files/FilePropertiesDialog.vue`
- Create: `frontend/src/features/terminal/components/files/FileCreateDialog.vue`
- Create: `frontend/src/features/terminal/components/files/FileUploadDialog.vue`
- Create: `frontend/src/features/terminal/components/files/FileDownloadDialog.vue`
- Test: `frontend/src/features/terminal/composables/__tests__/useSftpBrowser.test.ts`
- Modify: `frontend/src/components/terminal/WebTerminalPage.vue`

**Interfaces:**
- Produces: list/navigate/select/create/upload/download/rename/delete/properties API；组件只消费 typed props/emits。

- [ ] **Step 1: 写 mocked API 状态测试**

Assert current request payloads、loading flag order、directory refresh timing、selection after rename/delete、upload progress、download filename and error message behavior。

- [ ] **Step 2: 提取 `useSftpBrowser`**

Move all SFTP refs and operations. Accept the existing terminal session identifier/ref as input；call `api/terminal.ts` wrappers only；preserve toast/dialog side-effect order via injected callbacks where already available。

- [ ] **Step 3: 按无状态到有状态顺序拆组件**

Order: toolbar → table → simple dialogs → upload/download dialogs → SftpPanel。Copy existing markup/classes first；do not redesign UI。Each child emits current actions to `useSftpBrowser` owner。

- [ ] **Step 4: 验证并提交**

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
git add frontend/src/features/terminal frontend/src/components/terminal/WebTerminalPage.vue
git commit -m "refactor: 拆分终端 SFTP 浏览器"
```

### Task 4: 提取 RDP 和资源监控

**Files:**
- Create: `frontend/src/features/terminal/composables/useRdpSession.ts`
- Create: `frontend/src/features/terminal/composables/useResourceMonitor.ts`
- Create: `frontend/src/features/terminal/components/rdp/RdpViewport.vue`
- Create: `frontend/src/features/terminal/components/rdp/RdpToolbar.vue`
- Create: `frontend/src/features/terminal/components/rdp/RdpClipboardDialog.vue`
- Create: `frontend/src/features/terminal/components/rdp/ResourceMonitorPanel.vue`
- Test: `frontend/src/features/terminal/composables/__tests__/useRdpSession.test.ts`
- Test: `frontend/src/features/terminal/composables/__tests__/useResourceMonitor.test.ts`
- Modify: `frontend/src/components/terminal/WebTerminalPage.vue`

**Interfaces:**
- Produces: RDP connect/disconnect/input/resize/clipboard API；monitor polling start/stop/refresh API。

- [ ] **Step 1: 写 RDP 生命周期测试**

Mock Guacamole client/tunnel and timers。Assert connection parameters、keyboard/mouse attach-detach、display scaling、resize payload、clipboard encoding、disconnect cleanup and error state exactly match current behavior。

- [ ] **Step 2: 写 monitor polling 测试**

Use fake timers。Assert immediate first fetch、current interval、no overlapping request、stop on tab/session teardown and unchanged chart data mapping。

- [ ] **Step 3: 先提取 composables，再复制现有 UI 到组件**

`useRdpSession` exclusively owns Guacamole objects and input listeners；`useResourceMonitor` exclusively owns polling timer；components receive refs/data and emit commands。

- [ ] **Step 4: 验证并提交**

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
git add frontend/src/features/terminal frontend/src/components/terminal/WebTerminalPage.vue
git commit -m "refactor: 拆分终端 RDP 和资源监控"
```

### Task 5: 提取快捷命令和录像

**Files:**
- Create: `frontend/src/features/terminal/composables/useQuickCommands.ts`
- Create: `frontend/src/features/terminal/composables/useSessionRecordings.ts`
- Create: `frontend/src/features/terminal/components/commands/QuickCommandPanel.vue`
- Create: `frontend/src/features/terminal/components/recordings/RecordingPlayerDialog.vue`
- Test: `frontend/src/features/terminal/composables/__tests__/useQuickCommands.test.ts`
- Test: `frontend/src/features/terminal/composables/__tests__/useSessionRecordings.test.ts`
- Modify: `frontend/src/components/terminal/WebTerminalPage.vue`

**Interfaces:**
- Produces: 快捷命令分类/筛选/发送 API；录像列表/加载/播放/关闭 API。

- [ ] **Step 1: 写命令和录像契约测试**

Assert command filtering/order/risk confirmation and exact sent text；assert recording request URL、selected recording lifecycle、player disposal and error handling。

- [ ] **Step 2: 移动逻辑和现有模板**

Keep command transmission delegated to `useSshTerminal`；keep recording player DOM ownership inside `RecordingPlayerDialog.vue` and dispose player on close/unmount。

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
git add frontend/src/features/terminal frontend/src/components/terminal/WebTerminalPage.vue
git commit -m "refactor: 拆分快捷命令和终端录像"
```

### Task 6: 建立工作区组件和薄页面入口

**Files:**
- Create: `frontend/src/features/terminal/components/TerminalWorkspace.vue`
- Create: `frontend/src/pages/WebTerminalPage.vue`
- Modify: `frontend/src/components/terminal/WebTerminalPage.vue`
- Modify: `frontend/src/terminal.ts`
- Split/Delete: `frontend/src/styles/terminal.css`
- Create: feature-local style files under `frontend/src/features/terminal/`

**Interfaces:**
- Produces: `pages/WebTerminalPage.vue` 编排 feature；旧组件路径兼容；`terminal.ts` 仍挂载相同根节点。

- [ ] **Step 1: 将剩余页面编排移入 `TerminalWorkspace.vue`**

The workspace composes tabs、SSH surface、SFTP panel、RDP viewport、monitor、commands and recordings。It must not duplicate network/timer ownership already extracted。

- [ ] **Step 2: 创建薄页面**

`frontend/src/pages/WebTerminalPage.vue`:
```vue
<script setup lang="ts">
import TerminalWorkspace from '@features/terminal/components/TerminalWorkspace.vue'
</script>

<template>
  <TerminalWorkspace />
</template>
```
If the old page has required page-level setup, keep only query/bootstrap/context orchestration here and pass typed inputs to the workspace。

- [ ] **Step 3: 保持旧路径和入口兼容**

Replace old component with a wrapper that renders `@pages/WebTerminalPage.vue`; update `frontend/src/terminal.ts` to import the new page directly. Do not change `frontend/terminal.html` or mount element ID。

- [ ] **Step 4: 按组件切分 CSS**

Move selectors with each component and preserve selector text/order where specificity depends on order。Keep only terminal shell/global xterm overrides in a small `features/terminal/styles/terminal-shell.css` imported once。Run build after every style batch。

- [ ] **Step 5: 检查旧大文件和旧路径引用**

Run:
```powershell
(Get-Content frontend\src\components\terminal\WebTerminalPage.vue).Count
git grep -n "styles/terminal.css\|components/terminal/WebTerminalPage" -- frontend/src
```
Expected: wrapper is small；业务入口不再依赖旧页面实现；单体 CSS 不再被引用，确认无引用后删除。

- [ ] **Step 6: 全量验证并提交**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
powershell -ExecutionPolicy Bypass -File scripts\tests\test-repository-structure.ps1
git diff --check
```
Expected: PASS。

Run:
```powershell
git add -A frontend/src
git commit -m "refactor: 完成 Web Terminal 前端模块化"
```

### Task 7: 本地浏览器终端入口冒烟验证

**Files:**
- No source changes unless a verified regression is found.

**Interfaces:**
- Produces: 浏览器验证记录，不声称真实 SSH/RDP 连接，除非存在可达测试主机。

- [ ] **Step 1: 启动后端和前端到 `.codex-logs/`**

Use hidden background processes with explicit working directories and project-scoped log paths；poll HTTP readiness rather than fixed sleep。

- [ ] **Step 2: 使用 Browser 打开终端入口**

Open the actual local `/terminal.html` URL. Verify page loads、query bootstrap does not throw、host/session UI is visible、console has no uncaught exception。

- [ ] **Step 3: 验证可离线操作**

Verify tab/empty state、panels/dialog open-close and responsive resize. Without a configured reachable host, record SSH/RDP real connection as “not executed”，not “passed”。
