# Native UI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Element Plus from the frontend and rebuild the app on native HTML, Vue 3, and in-repo UI primitives without changing business behavior.

**Architecture:** Introduce a small native UI layer for dialogs, buttons, inputs, selects, tables, pagination, alerts, empty states, and feedback. Migrate the shell and feature pages in batches so each batch stays testable and visually reviewable. Keep all data flow, permissions, and APIs intact while replacing framework widgets with semantic HTML plus project CSS.

**Tech Stack:** Vue 3, TypeScript, native HTML/CSS, Lucide icons, Vite, Vitest.

## Global Constraints

- `element-plus` must be removed from runtime code, styles, and tests by the end of the migration.
- No new third-party UI framework may replace it.
- Existing data contracts, permissions, routes, and backend calls must remain unchanged.
- Visual behavior should stay responsive on desktop and usable on mobile.
- Shared UI should live in `frontend/src/shared/ui/native/` and shared styles in `frontend/src/styles/base/native-ui.css` or equivalent in-repo CSS.
- Verification must end with fresh `npm test` and `npm run build` passes.

---

## File Map

- Create native UI primitives under `frontend/src/shared/ui/native/` for dialog, button, input, textarea, select, number input, checkbox, radio group, table, pagination, empty state, alert, and toast/confirm surfaces.
- Replace the global feedback adapter in `frontend/src/composables/app/useFeedback.ts`.
- Update the app shell and top-level overlays in `frontend/src/App.vue`, `frontend/src/components/auth/LoginPage.vue`, `frontend/src/components/auth/login/LoginFormCard.vue`, `frontend/src/components/auth/login/LoginSliderVerify.vue`, and `frontend/src/shared/components/LockScreenOverlay.vue`.
- Migrate host, terminal, bulk execution, company, application market, and tool pages away from `el-*` components.
- Remove Element Plus bootstrapping from `frontend/src/main.ts`, `frontend/src/terminal.ts`, and `frontend/src/host-terminal.ts`.
- Remove `element-plus` from `frontend/package.json` and delete or retire `frontend/src/styles/base/element-plus-theme.css` and `frontend/src/styles/base/element-plus-overrides.css`.
- Update structure tests in `frontend/src/__tests__/elementPlusMigration.structure.test.ts`, `frontend/src/__tests__/appShell.structure.test.ts`, `frontend/src/__tests__/loginPage.elementPlus.structure.test.ts`, `frontend/src/__tests__/systemPages.elementPlus.structure.test.ts`, and the feature-level `*.structure.test.ts` files.

---

### Task 1: Build the Native UI Foundation

**Files:**
- Create: `frontend/src/shared/ui/native/NativeButton.vue`
- Create: `frontend/src/shared/ui/native/NativeDialog.vue`
- Create: `frontend/src/shared/ui/native/NativeField.vue`
- Create: `frontend/src/shared/ui/native/NativeInput.vue`
- Create: `frontend/src/shared/ui/native/NativeTextarea.vue`
- Create: `frontend/src/shared/ui/native/NativeSelect.vue`
- Create: `frontend/src/shared/ui/native/NativeNumberInput.vue`
- Create: `frontend/src/shared/ui/native/NativeCheckbox.vue`
- Create: `frontend/src/shared/ui/native/NativeRadioGroup.vue`
- Create: `frontend/src/shared/ui/native/NativeTabs.vue`
- Create: `frontend/src/shared/ui/native/NativeTable.vue`
- Create: `frontend/src/shared/ui/native/NativePagination.vue`
- Create: `frontend/src/shared/ui/native/NativeEmptyState.vue`
- Create: `frontend/src/shared/ui/native/NativeAlert.vue`
- Create: `frontend/src/shared/ui/native/NativeToastHost.vue`
- Create: `frontend/src/shared/ui/native/NativeConfirmDialog.vue`
- Create: `frontend/src/shared/ui/native/index.ts`
- Create: `frontend/src/styles/base/native-ui.css`
- Modify: `frontend/src/composables/app/useFeedback.ts`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/nativeUi.structure.test.ts`

**Interfaces:**
- Consumes: Vue slots/props/emits, browser focus and form events, and the existing `showToast` / `requestConfirm` call sites.
- Produces: reusable native widgets and a project-owned feedback layer that all pages can use without `element-plus`.

- [ ] **Step 1: Write failing tests for the shared native layer**

Add `frontend/src/__tests__/nativeUi.structure.test.ts` with checks that:

```ts
expect(source).toContain('NativeDialog');
expect(source).toContain('NativePagination');
expect(source).toContain('NativeConfirmDialog');
expect(source).not.toContain("from 'element-plus'");
```

Also update `frontend/src/__tests__/elementPlusMigration.structure.test.ts` so the feedback contract now expects the local toast/confirm layer instead of `ElMessage` and `ElMessageBox`.

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
npm test -- --run src/__tests__/nativeUi.structure.test.ts src/__tests__/elementPlusMigration.structure.test.ts
```

Expected: failures because the native layer does not exist yet and the old Element Plus feedback contract is still present.

- [ ] **Step 3: Implement the shared primitives**

Build the primitives with semantic HTML, project CSS, and minimal behavior:

- dialogs should manage overlay, close button, header, footer, escape key, and scrollable body
- tables should cover striped rows, selection, action cells, and empty states
- pagination should cover page buttons, page-size selector, and summary text
- toast and confirm should be app-owned overlays driven by `useFeedback.ts`

Keep the code local and small. Do not add another UI dependency.

- [ ] **Step 4: Re-run the shared-layer tests**

Run:

```powershell
npm test -- --run src/__tests__/nativeUi.structure.test.ts src/__tests__/elementPlusMigration.structure.test.ts
```

Expected: pass.

---

### Task 2: Rebuild the App Shell and Auth Surfaces

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/auth/LoginPage.vue`
- Modify: `frontend/src/components/auth/login/LoginFormCard.vue`
- Modify: `frontend/src/components/auth/login/LoginSliderVerify.vue`
- Modify: `frontend/src/shared/components/LockScreenOverlay.vue`
- Modify: `frontend/src/styles/auth-login.css`
- Modify: `frontend/src/styles/base/shell-nav.css`
- Modify: `frontend/src/styles/lock-screen.css`
- Modify: `frontend/src/styles/base/workspace-header.css`
- Test: `frontend/src/__tests__/appShell.structure.test.ts`
- Test: `frontend/src/__tests__/loginPage.elementPlus.structure.test.ts`

**Interfaces:**
- Consumes: the native primitives from Task 1, app navigation state, authentication state, and existing login/lock behavior.
- Produces: a shell, login flow, and lock overlay that no longer use Element Plus widgets.

- [ ] **Step 1: Write failing shell and login migration tests**

Update the shell tests to assert the app no longer imports `ElementPlus` and no longer renders `el-menu`, `el-dropdown`, `el-breadcrumb`, or `el-tooltip`.

Add or update login tests so they assert the login page uses native inputs, buttons, and overlay components instead of `el-input`, `el-button`, `el-dialog`, or `el-scrollbar`.

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
npm test -- --run src/__tests__/appShell.structure.test.ts src/__tests__/loginPage.elementPlus.structure.test.ts
```

Expected: failure against the current Element Plus shell.

- [ ] **Step 3: Replace the shell widgets**

Rebuild the top bar, side navigation, user menu, tooltips, and breadcrumb trail with native markup, buttons, and project-owned popovers or menus. Keep the existing iconography, workspace state, and permission logic.

- [ ] **Step 4: Rebuild login and lock overlays**

Use native form controls, buttons, and the new modal primitives for:

- login card
- two-factor / slider verification
- lock screen overlay

Keep the current login flow and validation messages unchanged.

- [ ] **Step 5: Re-run shell and login tests**

Run:

```powershell
npm test -- --run src/__tests__/appShell.structure.test.ts src/__tests__/loginPage.elementPlus.structure.test.ts
```

Expected: pass.

---

### Task 3: Migrate Host and Terminal Feature Surfaces

**Files:**
- Modify: `frontend/src/features/hosts/components/CredentialSelector.vue`
- Modify: `frontend/src/features/hosts/components/HostEditorDialog.vue`
- Modify: `frontend/src/features/hosts/components/HostExportDialog.vue`
- Modify: `frontend/src/features/hosts/components/HostGroupTree.vue`
- Modify: `frontend/src/features/hosts/components/HostImportDialog.vue`
- Modify: `frontend/src/features/hosts/components/HostManager.vue`
- Modify: `frontend/src/features/hosts/components/HostMoveDialog.vue`
- Modify: `frontend/src/features/hosts/components/HostTable.vue`
- Modify: `frontend/src/features/hosts/components/HostToolbar.vue`
- Modify: `frontend/src/components/terminal/SimpleHostTerminalPage.vue`
- Modify: `frontend/src/components/terminal/WebTerminalPage.vue`
- Modify: `frontend/src/features/terminal/components/files/FileCreateDialog.vue`
- Modify: `frontend/src/features/terminal/components/files/FileDownloadDialog.vue`
- Modify: `frontend/src/features/terminal/components/files/FilePropertiesDialog.vue`
- Modify: `frontend/src/features/terminal/components/files/FileTable.vue`
- Modify: `frontend/src/features/terminal/components/files/FileToolbar.vue`
- Modify: `frontend/src/features/terminal/components/files/SftpPanel.vue`
- Test: `frontend/src/features/hosts/components/__tests__/HostManager.structure.test.ts`
- Test: `frontend/src/features/terminal/components/files/__tests__/fileNative.structure.test.ts`
- Test: `frontend/src/__tests__/systemPages.elementPlus.structure.test.ts`

**Interfaces:**
- Consumes: the native primitives from Task 1, host data flows, terminal session state, file browser state, and existing action handlers.
- Produces: host management and terminal pages with native dialogs, menus, forms, tables, and pagination.

- [ ] **Step 1: Write failing tests for the host and terminal families**

Add or update structure tests so they assert:

- host dialogs use the native dialog wrapper instead of `el-dialog`
- host tables and toolbars no longer render `el-table`, `el-pagination`, `el-tooltip`, or `el-checkbox`
- terminal file dialogs and tables no longer use `el-*` controls

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
npm test -- --run src/features/hosts/components/__tests__/HostManager.structure.test.ts src/features/terminal/components/files/__tests__/fileNative.structure.test.ts src/__tests__/systemPages.elementPlus.structure.test.ts
```

Expected: failures while Element Plus remains in the feature surfaces.

- [ ] **Step 3: Migrate host management first**

Replace the host editor, move dialog, import/export dialogs, toolbar filters, host table, and quick-command surfaces with native widgets. Keep the existing host group tree behavior, credential selection, file upload, and validation flow intact.

- [ ] **Step 4: Migrate terminal file surfaces next**

Replace the file create/download/properties dialogs, file toolbar, and SFTP panel dialogs with native UI. Preserve selection, upload/download, permissions editing, and error states.

- [ ] **Step 5: Re-run the host and terminal tests**

Run the same targeted test command again.

Expected: pass.

---

### Task 4: Migrate Tool, Admin, Company, Bulk, and Market Pages

**Files:**
- Modify: `frontend/src/components/tools/AccountManager.vue`
- Modify: `frontend/src/components/tools/AuthenticatorPanel.vue`
- Modify: `frontend/src/components/tools/IpScanner.vue`
- Modify: `frontend/src/components/tools/LoginLogManager.vue`
- Modify: `frontend/src/components/tools/OperationLogManager.vue`
- Modify: `frontend/src/components/tools/PasswordGenerator.vue`
- Modify: `frontend/src/components/tools/ProfileCenter.vue`
- Modify: `frontend/src/components/tools/RoleManager.vue`
- Modify: `frontend/src/components/tools/SecurityScanPanel.vue`
- Modify: `frontend/src/components/tools/SessionAuditManager.vue`
- Modify: `frontend/src/components/tools/SubnetCalculator.vue`
- Modify: `frontend/src/components/tools/SystemSettingsPanel.vue`
- Modify: `frontend/src/components/tools/UserManager.vue`
- Modify: `frontend/src/components/tools/user/UserAccountDialog.vue`
- Modify: `frontend/src/components/tools/user/UserDeleteDialog.vue`
- Modify: `frontend/src/components/tools/user/UserResetPasswordDialog.vue`
- Modify: `frontend/src/components/tools/user/UserResetTwoFactorDialog.vue`
- Modify: `frontend/src/components/tools/user/UserTable.vue`
- Modify: `frontend/src/components/tools/machine/PingProbe.vue`
- Modify: `frontend/src/components/tools/machine/PortScanner.vue`
- Modify: `frontend/src/features/company/components/DeviceManager.vue`
- Modify: `frontend/src/features/bulk-execution/components/BulkExecutionPanel.vue`
- Modify: `frontend/src/features/application-market/components/ApplicationMarketPanel.vue`
- Test: `frontend/src/components/tools/__tests__/AccountManager.elementPlus.structure.test.ts`
- Test: `frontend/src/components/tools/__tests__/SystemSettingsPanel.elementPlus.structure.test.ts`
- Test: `frontend/src/features/company/__tests__/DeviceManager.elementPlus.structure.test.ts`
- Test: `frontend/src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts`
- Test: `frontend/src/__tests__/systemPages.elementPlus.structure.test.ts`

**Interfaces:**
- Consumes: the native primitives from Task 1 and the shell polish from Task 2.
- Produces: all remaining utility, admin, company, bulk, and market views without Element Plus.

- [ ] **Step 1: Write failing migration tests for the utility pages**

Update the element-plus structure tests so they reject `el-table`, `el-pagination`, `el-checkbox`, `el-radio-group`, `el-alert`, `el-empty`, `el-upload`, `el-date-picker`, and `el-tooltip` in the migrated utility pages.

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
npm test -- --run src/components/tools/__tests__/AccountManager.elementPlus.structure.test.ts src/components/tools/__tests__/SystemSettingsPanel.elementPlus.structure.test.ts src/features/company/__tests__/DeviceManager.elementPlus.structure.test.ts src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts src/__tests__/systemPages.elementPlus.structure.test.ts
```

Expected: failures while the old widgets remain.

- [ ] **Step 3: Migrate the utility/admin pages**

Replace the tool pages in batches that keep related dialogs together:

- account and user management
- profile, role, and system settings
- logs and session audit
- network helpers and password generation
- security scan and authenticator

Use native tables, form controls, and simple modal primitives; preserve search, filter, bulk select, and pagination behavior.

- [ ] **Step 4: Migrate the company, bulk execution, and application market pages**

Replace the remaining heavy tables, detail panes, and action dialogs with the same native primitives. Keep the task history, permission checks, and install/execute flows intact.

- [ ] **Step 5: Re-run the page-family tests**

Run the same targeted test command again.

Expected: pass.

---

### Task 5: Remove Element Plus from Runtime and Clean Up the Old Contract

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/terminal.ts`
- Modify: `frontend/src/host-terminal.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/elementPlusMigration.structure.test.ts`
- Modify: `frontend/src/__tests__/appShell.structure.test.ts`
- Modify: `frontend/src/__tests__/loginPage.elementPlus.structure.test.ts`
- Modify: `frontend/src/__tests__/systemPages.elementPlus.structure.test.ts`
- Delete: `frontend/src/styles/base/element-plus-theme.css`
- Delete: `frontend/src/styles/base/element-plus-overrides.css`

**Interfaces:**
- Consumes: the completed native replacements from Tasks 1-4.
- Produces: a frontend that boots without Element Plus imports, CSS, or runtime registration.

- [ ] **Step 1: Write the failing removal test**

Update the migration contract test so it now asserts:

```ts
expect(packageJson).not.toContain('"element-plus"');
expect(main).not.toContain("app.use(ElementPlus)");
expect(styles).not.toContain('element-plus-overrides.css');
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
npm test -- --run src/__tests__/elementPlusMigration.structure.test.ts src/__tests__/appShell.structure.test.ts src/__tests__/loginPage.elementPlus.structure.test.ts src/__tests__/systemPages.elementPlus.structure.test.ts
```

Expected: failure while the dependency and imports still exist.

- [ ] **Step 3: Remove the runtime wiring**

Delete the Element Plus import and `app.use(ElementPlus)` calls from the app entrypoints, then strip the old Element Plus stylesheet imports from `styles.css`.

- [ ] **Step 4: Remove the dependency and stale theme files**

Delete the `element-plus` dependency from `frontend/package.json`, remove the old theme/override CSS files, and update any remaining imports or tests that mention them.

- [ ] **Step 5: Re-run the removal and app-shell tests**

Run the same targeted test command again.

Expected: pass.

---

### Task 6: Full Verification and Visual QA

**Files:**
- Verify: every modified frontend file from Tasks 1-5
- Test: all touched `*.structure.test.ts` files

**Interfaces:**
- Consumes: the finished native frontend.
- Produces: evidence that the app builds, tests pass, and the migrated UI still renders correctly.

- [ ] **Step 1: Run the complete test suite**

Run:

```powershell
npm test
```

Expected: all tests pass.

- [ ] **Step 2: Run the production build**

Run:

```powershell
npm run build
```

Expected: exit code 0.

- [ ] **Step 3: Open the app and inspect the migrated screens**

Use the local browser against the dev server and visually check:

- auth/login
- app shell
- host manager
- terminal file manager
- one tool page with tables and dialogs

Confirm no Element Plus styling remains and the main forms, tables, and dialogs feel coherent.

- [ ] **Step 4: Run a final repository sanity check**

Run:

```powershell
git status --short
git diff --stat
```

Expected: only the intended migration changes remain.
