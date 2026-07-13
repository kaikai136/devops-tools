# 前端基础层与主机管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `app/shared/pages/features` 前端边界，拆分应用状态和主机管理大文件，同时保持所有页面行为与 `useAppState()`、`useHostManager()` 的调用契约不变。

**Architecture:** 先引入 Vitest 和路径别名，再移动无业务归属基础模块并保留兼容导出。主机管理按 list/groups/credentials/editor/verification/import-export 拆为 composable，原 `useHostManager()` 仅负责组合并返回原有 key；视图按工具栏、树、表格和对话框拆分。

**Tech Stack:** Vue 3 Composition API、TypeScript、Vite、Vitest

## Global Constraints

- 不改变页面文本、事件顺序、API URL、请求字段或响应解析。
- 旧 facade 的导出名、参数和返回 key 在迁移期间保持不变。
- 每个移动批次先有测试，再更新 import，最后构建。

---

### Task 1: 增加前端测试入口与别名

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.json`
- Create: `frontend/src/shared/utils/__tests__/errors.test.ts`

**Interfaces:**
- Produces: `npm run test:run`；别名 `@app`、`@shared`、`@features`、`@pages`。

- [ ] **Step 1: 安装 Vitest 并写入脚本**

Run:
```powershell
Push-Location frontend
npm install --save-dev vitest
npm pkg set scripts.test="vitest"
npm pkg set scripts.test:run="vitest run"
Pop-Location
```
Expected: `package.json` 和 lockfile 仅增加 Vitest 相关依赖和两个脚本。

- [ ] **Step 2: 配置 Vite alias**

Add to the existing `resolve.alias` in `frontend/vite.config.ts`:
```ts
import { fileURLToPath, URL } from 'node:url'

alias: {
  '@app': fileURLToPath(new URL('./src/app', import.meta.url)),
  '@shared': fileURLToPath(new URL('./src/shared', import.meta.url)),
  '@features': fileURLToPath(new URL('./src/features', import.meta.url)),
  '@pages': fileURLToPath(new URL('./src/pages', import.meta.url)),
}
```
Add matching `compilerOptions.paths` in `frontend/tsconfig.json`:
```json
{
  "@app/*": ["src/app/*"],
  "@shared/*": ["src/shared/*"],
  "@features/*": ["src/features/*"],
  "@pages/*": ["src/pages/*"]
}
```

- [ ] **Step 3: 写一个纯函数冒烟测试并运行**

Create `frontend/src/shared/utils/__tests__/errors.test.ts` after moving the existing exported error normalizer:
```ts
import { describe, expect, it } from 'vitest'
import { getErrorMessage } from '../errors'

describe('getErrorMessage', () => {
  it('returns the Error message without changing it', () => {
    expect(getErrorMessage(new Error('boom'))).toBe('boom')
  })
})
```
Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
```
Expected: test and build PASS；若现有导出名不是 `getErrorMessage`，先从 `frontend/src/utils/errors.ts` 读取真实公开名并在测试中使用该真实名字，不新增重复 API。

- [ ] **Step 4: 提交测试基础设施**

Run:
```powershell
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/tsconfig.json frontend/src/shared
git commit -m "test: 增加前端单元测试和模块别名"
```

### Task 2: 迁移 app 与 shared 基础模块

**Files:**
- Create: `frontend/src/app/context.ts`
- Create: `frontend/src/app/navigation.ts`
- Create: `frontend/src/shared/components/`
- Create: `frontend/src/shared/composables/useColumnVisibility.ts`
- Create: `frontend/src/shared/composables/usePasswordStrength.ts`
- Create: `frontend/src/shared/utils/errors.ts`
- Modify: `frontend/src/appContext.ts`
- Modify: `frontend/src/navigation.ts`
- Modify: current callers under `frontend/src/`

**Interfaces:**
- Produces: 新路径导出原有符号；旧 `appContext.ts`、`navigation.ts` 在过渡期仅 `export * from ...`。

- [ ] **Step 1: 记录公开导出**

Run:
```powershell
Select-String -Path frontend\src\appContext.ts,frontend\src\navigation.ts,frontend\src\utils\errors.ts -Pattern '^export '
```
Expected: 保存真实导出名，后续不得改名。

- [ ] **Step 2: 移动实现并增加兼容转发**

Use `git mv` for each existing implementation. Replace old entry files with:
```ts
export * from './app/context'
```
and:
```ts
export * from './app/navigation'
```
Move common components and the two generic composables with `git mv`; update imports to `@shared/...` without修改组件 props/emits。

- [ ] **Step 3: 验证无循环依赖和构建回归**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
git grep -n "components/common\|composables/useColumnVisibility\|composables/usePasswordStrength\|utils/errors" -- frontend/src
```
Expected: tests/build PASS；旧路径只允许出现在兼容转发文件，不能出现在业务调用方。

- [ ] **Step 4: 提交基础层迁移**

Run:
```powershell
git add frontend/src frontend/vite.config.ts frontend/tsconfig.json
git commit -m "refactor: 整理前端应用层和共享模块"
```

### Task 3: 拆分 useAppState 并保持 facade

**Files:**
- Create: `frontend/src/app/composables/useSessionState.ts`
- Create: `frontend/src/app/composables/usePageState.ts`
- Create: `frontend/src/app/composables/useAppShell.ts`
- Modify: `frontend/src/composables/useAppState.ts`
- Test: `frontend/src/app/composables/__tests__/useAppState.contract.test.ts`

**Interfaces:**
- Produces: `useAppState()` 返回 key 集合与重构前一致。

- [ ] **Step 1: 生成 facade key 快照**

Create a temporary script/test that calls `useAppState()` in the same app-context setup as current callers and asserts sorted keys against an explicit array copied from the pre-refactor return object:
```ts
expect(Object.keys(state).sort()).toEqual([
  // 逐项复制当前 useAppState return object 的真实 key，并按字母排序
])
```
Before committing, replace the comment with the complete explicit key list obtained from the source; the committed test must contain no omitted key。

- [ ] **Step 2: 运行契约测试确认通过旧实现**

Run:
```powershell
Push-Location frontend
npm run test:run -- src/app/composables/__tests__/useAppState.contract.test.ts
Pop-Location
```
Expected: PASS against original implementation。

- [ ] **Step 3: 按职责移动原实现**

Move authentication/session refs and actions to `useSessionState.ts`, active-page/navigation orchestration to `usePageState.ts`, shell/dialog/global layout state to `useAppShell.ts`. Keep `frontend/src/composables/useAppState.ts` as composition only:
```ts
export function useAppState() {
  const session = useSessionState()
  const pages = usePageState(session)
  const shell = useAppShell(session, pages)
  return { ...session, ...pages, ...shell }
}
```
Use the actual dependency parameters/types discovered in the source; do not duplicate refs between modules。

- [ ] **Step 4: 运行契约和构建**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
```
Expected: explicit return-key contract and build PASS。

- [ ] **Step 5: 提交应用状态拆分**

Run:
```powershell
git add frontend/src/app/composables frontend/src/composables/useAppState.ts
git commit -m "refactor: 拆分前端应用状态编排"
```

### Task 4: 建立 hosts 类型、API 和纯函数边界

**Files:**
- Create: `frontend/src/features/hosts/types.ts`
- Create: `frontend/src/features/hosts/api/hosts.ts`
- Create: `frontend/src/features/hosts/utils/export.ts`
- Create: `frontend/src/features/hosts/utils/groups.ts`
- Test: `frontend/src/features/hosts/utils/__tests__/groups.test.ts`
- Test: `frontend/src/features/hosts/utils/__tests__/export.test.ts`

**Interfaces:**
- Produces: 主机相关类型、HTTP 调用和无 Vue 状态的导入导出/分组纯函数。

- [ ] **Step 1: 从现有 useHostManager 提取纯函数测试样例**

Write explicit fixtures copied from current accepted input/output。For group flattening, assert root/child order and unchanged IDs；for export, assert current header names and field serialization exactly。

- [ ] **Step 2: 运行测试确认新模块尚不存在**

Run:
```powershell
Push-Location frontend
npm run test:run -- src/features/hosts/utils/__tests__
Pop-Location
```
Expected: FAIL because imports do not exist。

- [ ] **Step 3: 使用 `git mv`/copy-extract 移动原函数**

Move code without algorithm changes. `api/hosts.ts` must call the same existing HTTP client and same URL strings. `types.ts` initially re-exports shared existing types when moving a type would create a wide diff。

- [ ] **Step 4: 运行测试和构建**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
```
Expected: PASS。

### Task 5: 拆分主机 composables 并保持 useHostManager facade

**Files:**
- Create: `frontend/src/features/hosts/composables/useHostList.ts`
- Create: `frontend/src/features/hosts/composables/useHostGroups.ts`
- Create: `frontend/src/features/hosts/composables/useHostCredentials.ts`
- Create: `frontend/src/features/hosts/composables/useHostEditor.ts`
- Create: `frontend/src/features/hosts/composables/useHostVerification.ts`
- Create: `frontend/src/features/hosts/composables/useHostImportExport.ts`
- Create: `frontend/src/features/hosts/composables/useHostManager.ts`
- Modify: `frontend/src/composables/features/useHostManager.ts`
- Test: `frontend/src/features/hosts/composables/__tests__/useHostManager.contract.test.ts`

**Interfaces:**
- Produces: 新 facade；旧路径 `export { useHostManager } from '@features/hosts/composables/useHostManager'`。

- [ ] **Step 1: 写完整返回 key 契约测试**

Copy every key from the old `useHostManager()` return object into an explicit sorted expected array and assert equality. Also assert representative methods preserve arity and representative refs preserve initial values。

- [ ] **Step 2: 每次只抽取一个职责 composable**

Order: list → groups → credentials → editor → verification → import/export。每抽取一个模块后运行：
```powershell
Push-Location frontend
npm run test:run -- src/features/hosts/composables/__tests__/useHostManager.contract.test.ts
npm run build
Pop-Location
```
Expected: 每一批均 PASS。

- [ ] **Step 3: 将旧路径改为兼容导出**

`frontend/src/composables/features/useHostManager.ts`:
```ts
export { useHostManager } from '@features/hosts/composables/useHostManager'
```

- [ ] **Step 4: 提交 composable 拆分**

Run:
```powershell
git add frontend/src/features/hosts frontend/src/composables/features/useHostManager.ts
git commit -m "refactor: 模块化主机管理状态和操作"
```

### Task 6: 拆分 HostManager 视图

**Files:**
- Create: `frontend/src/features/hosts/components/HostToolbar.vue`
- Create: `frontend/src/features/hosts/components/HostGroupTree.vue`
- Create: `frontend/src/features/hosts/components/HostTable.vue`
- Create: `frontend/src/features/hosts/components/HostEditorDialog.vue`
- Create: `frontend/src/features/hosts/components/HostMoveDialog.vue`
- Create: `frontend/src/features/hosts/components/CredentialSelector.vue`
- Create: `frontend/src/features/hosts/components/HostImportDialog.vue`
- Create: `frontend/src/features/hosts/components/HostExportDialog.vue`
- Create: `frontend/src/features/hosts/components/HostManager.vue`
- Modify: `frontend/src/components/tools/HostManager.vue`

**Interfaces:**
- Produces: props/emits 明确的子组件；旧组件路径继续导出/渲染新组件。

- [ ] **Step 1: 按模板区域记录 props、事件和插槽**

For each extracted region, define typed props and emits using the exact values/methods currently referenced。Do not move business mutations into child components；children emit the current action back to the facade。

- [ ] **Step 2: 依次抽取只读区域和对话框**

Order: toolbar → group tree → table → editor → move → credential selector → import → export。每次抽取后运行 `npm run build`。

- [ ] **Step 3: 保留旧入口**

Replace `frontend/src/components/tools/HostManager.vue` with:
```vue
<script setup lang="ts">
import HostManager from '@features/hosts/components/HostManager.vue'
</script>

<template>
  <HostManager />
</template>
```
If the original component accepts props or emits, mirror the complete real declarations and forward them explicitly rather than using the zero-prop wrapper above。

- [ ] **Step 4: 全量验证并提交**

Run:
```powershell
Push-Location frontend
npm run test:run
npm run build
Pop-Location
git diff --check
```
Expected: PASS。

Run:
```powershell
git add frontend/src/features/hosts frontend/src/components/tools/HostManager.vue
git commit -m "refactor: 拆分主机管理页面组件"
```
