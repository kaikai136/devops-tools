# 全站弹窗界面优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Element Plus 与手写弹窗统一为专业运维控制台风格，并修复滚动、布局、按钮层级、关闭行为和窄屏适配问题。

**Architecture:** 新增一个全局 `popup-system.css` 作为弹窗视觉基础层，使用稳定的 `.popup-*` 结构类名和 Element Plus 选择器覆盖统一外观；页面组件只保留业务专属布局与状态逻辑。先用结构测试锁定全站弹窗契约，再按表单、管理列表、抽屉、终端四类逐组改造。

**Tech Stack:** Vue 3、Element Plus、原生 CSS、Vitest、Vite。

## Global Constraints

- 所有 Element Plus `el-dialog` / `el-drawer` 必须使用 `:close-on-click-modal="false"`。
- 自定义弹窗禁止使用 `@click.self` 关闭。
- 弹窗内容超出高度时只滚动内容区，标题栏和底部操作区保持可见。
- 不修改现有业务 API、表单提交逻辑、权限判断和状态管理。
- 主按钮使用稳定运维蓝，不再使用蓝绿渐变。
- 窄屏宽度使用 `min(920px, calc(100vw - 32px))`，表单从两列降为单列。

---

### Task 1: Lock the popup visual and structure contract

**Files:**
- Modify: `frontend/src/shared/utils/__tests__/popupBackdrop.test.ts`
- Create: `frontend/src/shared/utils/__tests__/popupStructure.test.ts`

**Interfaces:**
- Consumes: Vue template source files under `frontend/src`.
- Produces: Static checks that every popup has protected backdrop behavior and key visual structure hooks.

- [ ] **Step 1: Write the failing structure tests**

Add tests that scan Vue files and fail when a visible popup class does not include `popup-header`, `popup-body`, or `popup-footer`, while allowing Element Plus generated wrappers when the component contains equivalent explicit page structure. Add a focused required class list for the four priority flows: `host-editor-dialog`, `host-quick-command-dialog`, `host-export-modal`, and `terminal-file-create-backdrop`.

```ts
it('keeps priority popups on the shared shell structure', () => {
  expect(template('src/features/hosts/components/HostEditorDialog.vue')).toContain('popup-body');
  expect(template('src/features/hosts/components/HostManager.vue')).toContain('popup-header');
  expect(template('src/features/hosts/components/HostExportDialog.vue')).toContain('popup-footer');
  expect(template('src/features/terminal/components/files/FileCreateDialog.vue')).toContain('popup-body');
});
```

- [ ] **Step 2: Run the focused tests and confirm the new contract fails**

Run: `npm test -- --run src/shared/utils/__tests__/popupStructure.test.ts src/shared/utils/__tests__/popupBackdrop.test.ts`

Expected: the existing backdrop test passes and the new structure test fails because the priority popup templates do not yet expose the shared hooks.

- [ ] **Step 3: Extend the backdrop test to cover every Element Plus popup**

Keep the existing assertion for `:close-on-click-modal="false"` and add a source scan that reports file and first-line snippet for any custom modal/backdrop using `@click.self`.

- [ ] **Step 4: Run the focused tests again**

Run: `npm test -- --run src/shared/utils/__tests__/popupStructure.test.ts src/shared/utils/__tests__/popupBackdrop.test.ts`

Expected: the structure test remains the only failing test, proving it is testing the missing visual contract rather than a broken test harness.

---

### Task 2: Add the shared popup visual system

**Files:**
- Create: `frontend/src/styles/base/popup-system.css`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/styles/base/element-plus-overrides.css`

**Interfaces:**
- Consumes: Existing Element Plus popup DOM and custom popup class names.
- Produces: Shared CSS variables, shell layout, fixed header/footer, independent body scroll, button hierarchy, focus state, and responsive rules.

- [ ] **Step 1: Add the popup system import after the existing Element Plus overrides**

Add:

```css
@import "./styles/base/popup-system.css";
```

immediately after `element-plus-overrides.css` in `frontend/src/styles.css`.

- [ ] **Step 2: Write the shared tokens and base shell styles**

Use these exact base values in `popup-system.css`:

```css
:root {
  --popup-width-form: 680px;
  --popup-width-wide: min(920px, calc(100vw - 32px));
  --popup-radius: 8px;
  --popup-border: #d7e2f0;
  --popup-text: #102a4d;
  --popup-muted: #7185a0;
  --popup-primary: #216dff;
  --popup-surface: #ffffff;
  --popup-subtle: #f6f9fd;
}

.el-overlay {
  background: rgba(15, 31, 52, 0.58);
  backdrop-filter: blur(3px);
}

.el-dialog,
.el-drawer {
  border: 1px solid var(--popup-border);
  border-radius: var(--popup-radius);
  background: var(--popup-surface);
  color: var(--popup-text);
  box-shadow: 0 22px 60px rgba(22, 45, 80, 0.18);
  overflow: hidden;
}
```

- [ ] **Step 3: Add shared header/body/footer and responsive rules**

Implement `.popup-header`, `.popup-body`, `.popup-footer`, `.popup-title-group`, `.popup-close`, `.popup-form-grid`, `.popup-actions`, and matching Element Plus `.el-dialog__header`, `.el-dialog__body`, `.el-dialog__footer`, `.el-drawer__header`, `.el-drawer__body`, `.el-drawer__footer` rules. Body scroll must use `min-height: 0; overflow: auto`, and at `max-width: 720px` grid columns must become one column.

- [ ] **Step 4: Run the build to validate selectors and CSS syntax**

Run: `npm run build`

Expected: Vite build exits with code 0.

---

### Task 3: Refine form popups

**Files:**
- Modify: `frontend/src/features/hosts/components/HostEditorDialog.vue`
- Modify: `frontend/src/features/hosts/components/HostMoveDialog.vue`
- Modify: `frontend/src/features/hosts/components/HostExportDialog.vue`
- Modify: `frontend/src/features/hosts/components/HostImportDialog.vue`
- Modify: `frontend/src/components/tools/AccountManager.vue`
- Modify: `frontend/src/components/tools/user/UserAccountDialog.vue`
- Modify: `frontend/src/components/tools/user/UserResetPasswordDialog.vue`
- Modify: `frontend/src/components/tools/user/UserResetTwoFactorDialog.vue`
- Modify: `frontend/src/components/tools/user/UserDeleteDialog.vue`
- Modify: `frontend/src/components/tools/RoleManager.vue`
- Modify: `frontend/src/components/tools/SecurityScanPanel.vue`
- Modify: `frontend/src/styles/tools/host/layout-groups.css`
- Modify: `frontend/src/styles/tools/user-manager.css`
- Modify: `frontend/src/styles/tools/role-manager.css`
- Modify: `frontend/src/styles/tools/security-scan.css`

**Interfaces:**
- Consumes: Existing props, emits, refs, form bindings, and permission guards.
- Produces: Shared popup hooks and stable two-column form layouts without behavior changes.

- [ ] **Step 1: Add the failing template assertions for the host editor**

Extend `frontend/src/features/hosts/components/__tests__/HostManager.structure.test.ts` to assert the editor body has `popup-body`, the form has `popup-form-grid`, and the footer has `popup-footer popup-actions`.

- [ ] **Step 2: Run the host structure test and confirm it fails**

Run: `npm test -- --run src/features/hosts/components/__tests__/HostManager.structure.test.ts`

Expected: the new popup hook assertions fail while existing business wiring assertions remain visible.

- [ ] **Step 3: Add shared hooks to host form and transfer popups**

Wrap host editor content with `popup-body`, add `popup-form-grid` to the existing form class, and add `popup-footer popup-actions` to the footer wrapper. Apply the same header/body/footer classes to move, import, and export templates without changing emitted events or form IDs.

- [ ] **Step 4: Apply the same shell hooks to account, user, role, and security forms**

Use existing semantic wrappers where present. Do not duplicate title text already rendered by Element Plus; add only structural classes and adjust field grid classes.

- [ ] **Step 5: Replace local Element Plus shell overrides with shared spacing rules**

Remove conflicting `.host-editor-dialog .el-dialog__header`, `.el-dialog__body`, and fixed-height rules from `layout-groups.css`. Keep only host-specific field widths and credential selector styles. Repeat for local user, role, and security rules where they override the shared shell spacing.

- [ ] **Step 6: Run focused form tests and build**

Run: `npm test -- --run src/features/hosts/components/__tests__/HostManager.structure.test.ts src/shared/utils/__tests__/popupStructure.test.ts`

Run: `npm run build`

Expected: popup structure tests pass; existing unrelated HostManager assertions must be reported if they still expect the old width or nesting.

---

### Task 4: Refine management dialogs and drawers

**Files:**
- Modify: `frontend/src/features/hosts/components/HostManager.vue`
- Modify: `frontend/src/features/bulk-execution/components/BulkExecutionPanel.vue`
- Modify: `frontend/src/features/application-market/components/ApplicationMarketPanel.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/styles/tools/host/quick-commands.css`
- Modify: `frontend/src/styles/tools/bulk-execution.css`
- Modify: `frontend/src/styles/tools/application-market.css`
- Modify: `frontend/src/styles/base/workspace-header.css`

**Interfaces:**
- Consumes: Existing list data, filter state, action handlers, drawer close handlers, and selection state.
- Produces: Usable two-pane management dialogs, grouped detail drawers, and consistent action footers.

- [ ] **Step 1: Add management-popup structure assertions**

Extend `frontend/src/shared/utils/__tests__/popupStructure.test.ts` with required hooks for the quick command manager, host export, target picker, application detail, and QR dialog.

- [ ] **Step 2: Run the focused structure tests and confirm the new assertions fail**

Run: `npm test -- --run src/shared/utils/__tests__/popupStructure.test.ts`

- [ ] **Step 3: Add shell hooks and remove horizontal overflow causes**

Add `popup-header`, `popup-body`, and `popup-footer` to explicit custom content wrappers. For quick commands, make the manager body a bounded grid with `min-width: 0`; ensure list rows can shrink and use `overflow-wrap: anywhere` for command text. For export, keep selection cards and field groups inside the body without relying on the Element Plus default width.

- [ ] **Step 4: Normalize drawer content sections**

Add section wrappers with consistent heading spacing to application detail, task detail, security scan, and bulk execution detail surfaces. Keep destructive and primary action semantics unchanged.

- [ ] **Step 5: Run management tests and build**

Run: `npm test -- --run src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts src/features/application-market/__tests__/applicationMarket.structure.test.ts src/shared/utils/__tests__/popupStructure.test.ts`

Run: `npm run build`

---

### Task 5: Refine terminal file and custom overlays

**Files:**
- Modify: `frontend/src/features/terminal/components/files/FileCreateDialog.vue`
- Modify: `frontend/src/features/terminal/components/files/FilePropertiesDialog.vue`
- Modify: `frontend/src/features/terminal/components/files/FileUploadDialog.vue`
- Modify: `frontend/src/features/terminal/components/files/FileDownloadDialog.vue`
- Modify: `frontend/src/features/terminal/components/files/SftpPanel.vue`
- Modify: `frontend/src/components/terminal/WebTerminalPage.vue`
- Modify: `frontend/src/styles/terminal.css`

**Interfaces:**
- Consumes: Existing terminal dialog state and save/close callbacks.
- Produces: Terminal dialogs with the same shell geometry, compact density, and independent body scroll.

- [ ] **Step 1: Add terminal overlay structure assertions**

Assert that create, properties, upload, download, delete, and quick-command overlays contain `popup-body` and `popup-actions`, and that their backdrop nodes do not have self-close handlers.

- [ ] **Step 2: Run the focused tests and confirm they fail for missing hooks**

Run: `npm test -- --run src/shared/utils/__tests__/popupStructure.test.ts src/shared/utils/__tests__/popupBackdrop.test.ts`

- [ ] **Step 3: Add shared hooks without changing terminal state transitions**

Add structural classes to existing sections and footer wrappers. Preserve all `emit('close')`, `browser.close*`, save, upload, and delete handlers exactly.

- [ ] **Step 4: Replace fixed viewport heights with body scroll constraints**

Update terminal-specific CSS so the shell uses `max-height: min(760px, calc(100vh - 32px))`, the body uses `overflow: auto`, and footer actions remain visible. Keep terminal-specific colors and compact spacing only where they do not conflict with the shared shell.

- [ ] **Step 5: Run terminal tests and build**

Run: `npm test -- --run src/features/terminal/composables/__tests__/useSftpBrowser.test.ts src/components/terminal/__tests__/WebTerminalPage.structure.test.ts src/shared/utils/__tests__/popupStructure.test.ts`

Run: `npm run build`

---

### Task 6: Full verification and visual smoke check

**Files:**
- Modify: `frontend/src/shared/utils/__tests__/popupStructure.test.ts` only if a discovered popup is missing from the contract.

**Interfaces:**
- Consumes: All popup changes from Tasks 1-5.
- Produces: Verified desktop and narrow-screen popup behavior.

- [ ] **Step 1: Run the complete test suite**

Run: `npm test -- --run`

Expected: record total passing tests and any unrelated existing failures separately; no new popup structure or backdrop failures are allowed.

- [ ] **Step 2: Run the production build**

Run: `npm run build`

Expected: exit code 0.

- [ ] **Step 3: Run the source hygiene checks**

Run: `git diff --check`

Run: `rg -n '<el-(dialog|drawer)\\b' frontend/src --glob '*.vue'`

Run: `npm test -- --run src/shared/utils/__tests__/popupBackdrop.test.ts src/shared/utils/__tests__/popupStructure.test.ts`

- [ ] **Step 4: Start the local Vite server**

Run: `npm run dev -- --port 4173`

Expected: `http://localhost:4173/` returns HTTP 200.

- [ ] **Step 5: Check the priority popup flows**

Verify the host editor, quick command manager, and host export popup at desktop width and a narrow viewport. Confirm title/close alignment, no horizontal overflow, body-only scrolling, visible footer actions, and no accidental backdrop close.

- [ ] **Step 6: Perform the code-quality gate**

Review changed files for event/data-flow regressions, stale CSS specificity, accidental API changes, focus visibility, and responsive overflow. Fix any in-scope issues before reporting completion.
