# Asset Management Naming And Table Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the sidebar host-management label to "资产管理" and make the visible host table fill the page with compact columns without changing routes or behavior.

**Architecture:** Keep the existing navigation keys and host table CSS-grid implementation. Update only user-facing navigation labels, regular column sizing, grid spacing, row padding, and full-width table sizing; preserve the sticky status/actions widths and all existing host interactions.

**Tech Stack:** Vue 3, TypeScript, Vitest, Vite, CSS Grid.

## Global Constraints

- Preserve existing navigation keys, routes, permissions, sorting, pagination, and column visibility behavior.
- Preserve the current uncommitted changes in the host column defaults and `useColumnVisibility`.
- Keep status at `86px` and actions at `132px`.
- Keep the table at `width: 100%` so the host page fills the available panel.
- Use test-first changes and verify with focused tests plus the frontend build.

---

### Task 1: Lock the navigation rename and compact table contract with failing tests

**Files:**
- Modify: `frontend/src/features/hosts/components/__tests__/HostManager.structure.test.ts`
- Test: `frontend/src/features/hosts/components/__tests__/HostManager.structure.test.ts`

**Interfaces:**
- Consumes: Existing SFC source readers and style readers in the structure test.
- Produces: Regression assertions for the visible navigation labels and the new compact table sizing contract.

- [ ] **Step 1: Add a failing navigation label assertion**

Read `src/app/navigation.ts` with the existing `readFileSync` helper and assert that the host group label and `hosts` item label are both `资产管理`, while the old visible label is absent.

```ts
it('labels the host navigation as asset management', () => {
  const navigationSource = readFileSync(
    fileURLToPath(new URL('../../../../app/navigation.ts', import.meta.url)),
    'utf8',
  );

  expect(navigationSource).toContain("label: '资产管理'");
  expect(navigationSource.match(/label: '资产管理'/g)).toHaveLength(2);
  expect(navigationSource).not.toContain("label: '主机管理'");
});
```

- [ ] **Step 2: Add failing compact sizing assertions**

Extend the existing host table density test to assert the reduced gap, padding, representative minimum widths, full-width table behavior, and preserved status/actions widths.

```ts
it('keeps the host table compact while preserving action space', () => {
  const managerScript = readSfc('src/features/hosts/components/HostManager.vue').scriptSetup?.content ?? '';
  const styles = readStyle('../../../../styles/tools/host/table.css');

  expect(managerScript).toContain("{ key: 'group', label: '主机分组', width: 'minmax(84px, 0.7fr)', minWidth: 84 }");
  expect(managerScript).toContain("{ key: 'ip', label: 'IP地址', width: 'minmax(126px, 0.95fr)', minWidth: 126 }");
  expect(managerScript).toContain("{ key: 'spec', label: '主机规格', width: 'minmax(150px, 1fr)', minWidth: 150 }");
  expect(managerScript).toContain("'--host-select-column-width': '32px'");
  expect(managerScript).toContain("'--host-status-column-width': '86px'");
  expect(managerScript).toContain("'--host-actions-column-width': '132px'");
  expect(managerScript).toContain("'--host-status-sticky-right': actionsVisible ? 'calc(var(--host-actions-column-width) + 6px)' : '0px'");
  expect(styles).toMatch(/\.host-table\s*\{[\s\S]*width:\s*100%;[\s\S]*min-width:\s*var\(--host-table-min-width,\s*1300px\);/);
  expect(styles).toMatch(/\.host-table-row\s*\{[\s\S]*gap:\s*6px;[\s\S]*padding:\s*0 10px;/);
});
```

- [ ] **Step 3: Run the focused test and verify it fails for the expected reasons**

Run:

```powershell
npm --prefix frontend run test:run -- src/features/hosts/components/__tests__/HostManager.structure.test.ts
```

Expected: FAIL because the navigation source still contains the old label and the current table values still use the wider gap, padding, and minimum widths.

### Task 2: Apply the navigation rename and compact table sizing

**Files:**
- Modify: `frontend/src/app/navigation.ts`
- Modify: `frontend/src/features/hosts/components/HostManager.vue`
- Modify: `frontend/src/styles/tools/host/table.css`

**Interfaces:**
- Consumes: The failing assertions from Task 1.
- Produces: Navigation labels showing "资产管理" and a narrower CSS-grid host table.

- [ ] **Step 1: Rename only the visible host navigation labels**

In `frontend/src/app/navigation.ts`, keep `key: 'host'` and `key: 'hosts'` unchanged and replace only their two `label: '主机管理'` values with `label: '资产管理'`.

- [ ] **Step 2: Reduce regular host column widths**

In `frontend/src/features/hosts/components/HostManager.vue`, use these values for the regular columns:

```ts
{ key: 'group', label: '主机分组', width: 'minmax(84px, 0.7fr)', minWidth: 84 },
{ key: 'name', label: '节点', width: 'minmax(102px, 0.85fr)', minWidth: 102 },
{ key: 'ip', label: 'IP地址', width: 'minmax(126px, 0.95fr)', minWidth: 126 },
{ key: 'machine', label: '机器名称', width: 'minmax(92px, 0.7fr)', minWidth: 92 },
{ key: 'spec', label: '主机规格', width: 'minmax(150px, 1fr)', minWidth: 150 },
{ key: 'platformType', label: '平台类型', width: 'minmax(76px, 0.52fr)', minWidth: 76 },
{ key: 'remark', label: '备注', width: 'minmax(104px, 0.82fr)', minWidth: 104 },
```

Also reduce the computed selection width from `38px` to `32px`, use the 6px
gap in the status sticky offset, and leave the existing status and actions
widths at `86px` and `132px`.

- [ ] **Step 3: Reduce table spacing**

In `frontend/src/styles/tools/host/table.css`, change `.host-table-row` to:

```css
.host-table-row {
  display: grid;
  grid-template-columns: var(--host-table-columns);
  align-items: center;
  gap: 6px;
  min-height: 72px;
  border-bottom: 1px solid #edf1f6;
  padding: 0 10px;
}
```

Do not change row height or sticky positioning.

- [ ] **Step 4: Keep the table filling the page width**

In `frontend/src/styles/tools/host/table.css`, keep `.host-table` full width
while preserving the computed minimum width:

```css
.host-table {
  width: 100%;
  min-width: var(--host-table-min-width, 1300px);
  border-top: 1px solid #edf1f6;
}
```

### Task 3: Verify the focused behavior and build

**Files:**
- No additional files.

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: Verified tests and a successful frontend production build.

- [ ] **Step 1: Run the focused structure test**

Run:

```powershell
npm --prefix frontend run test:run -- src/features/hosts/components/__tests__/HostManager.structure.test.ts
```

Expected: PASS with zero failures.

- [ ] **Step 2: Run the shared column-visibility tests**

Run:

```powershell
npm --prefix frontend run test:run -- src/shared/composables/__tests__/useColumnVisibility.test.ts
```

Expected: PASS with zero failures, confirming the existing uncommitted column visibility behavior remains intact.

- [ ] **Step 3: Run the frontend build**

Run:

```powershell
npm --prefix frontend run build
```

Expected: exit code 0 with the Vite production bundle generated successfully.

- [ ] **Step 4: Review the final diff and whitespace**

Run:

```powershell
git diff --check
git status --short
git diff -- frontend/src/app/navigation.ts frontend/src/features/hosts/components/HostManager.vue frontend/src/styles/tools/host/table.css frontend/src/features/hosts/components/__tests__/HostManager.structure.test.ts
```

Confirm that only the requested labels, table sizing, regression tests, and the already-present user changes are visible.
