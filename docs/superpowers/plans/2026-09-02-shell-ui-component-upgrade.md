# Shell UI Component Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the logged-in app shell and navigation to a cleaner component-library-based layout without changing business routes or backend behavior.

**Architecture:** Keep the existing page registry, permissions, and tool components. Replace the handwritten shell chrome in `App.vue` with Element Plus navigation primitives and Element Plus quick actions, then tune the shared shell CSS for the new component sizing and responsive behavior.

**Tech Stack:** Vue 3, TypeScript, Element Plus, Vitest, Vite

## Global Constraints

- Keep the existing navigation keys, page selection, and permission checks unchanged.
- Do not change backend APIs, route structure, or business-page internals.
- Use Element Plus for shell structure controls and global quick actions.
- Preserve dark mode and mobile responsiveness.

---

### Task 1: Add shell regression coverage and UI dependencies

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/main.ts`
- Create: `frontend/src/__tests__/appShell.structure.test.ts`

**Interfaces:**
- Consumes: `App.vue`, `main.ts`, `styles/base/workspace-header.css`, `styles/base/shell-nav.css`
- Produces: shell-level dependency wiring and a failing structure test that expects the new component tags and imports

- [ ] **Step 1: Write the failing test**

```ts
expect(app).toContain('el-menu');
expect(app).toContain('el-dropdown');
expect(app).toContain('el-tooltip');
expect(app).toContain('el-button');
expect(main).toContain("import 'element-plus/dist/index.css';");
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm test -- frontend/src/__tests__/appShell.structure.test.ts`
Expected: fail because the shell still uses handwritten markup and the new styles are not wired in yet

- [ ] **Step 3: Implement the minimal dependency wiring**

```ts
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

const app = createApp(App);
app.use(ElementPlus);
app.mount('#app');
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `npm test -- frontend/src/__tests__/appShell.structure.test.ts`
Expected: pass

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.ts frontend/src/__tests__/appShell.structure.test.ts
git commit -m "feat: add shell ui library wiring"
```

### Task 2: Refactor the app shell to component-library navigation

**Files:**
- Modify: `frontend/src/App.vue`

**Interfaces:**
- Consumes: app state from `useAppState`, navigation metadata from `app/navigation.ts`
- Produces: Element Plus sidebar menu, breadcrumb, dropdown user menu, and quick actions

- [ ] **Step 1: Write the failing test**

```ts
expect(app).toContain('<el-menu');
expect(app).toContain('<el-sub-menu');
expect(app).toContain('<el-breadcrumb');
expect(app).toContain('<el-tooltip');
expect(app).toContain('<el-button');
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm test -- frontend/src/__tests__/appShell.structure.test.ts`
Expected: fail until the shell template is replaced

- [ ] **Step 3: Implement the shell refactor**

```vue
<el-menu :collapse="sidebarCollapsed" :default-active="String(activeTool)">
  <el-menu-item index="dashboard" @click="setActiveTool('dashboard')">...</el-menu-item>
  <el-sub-menu v-for="group in navGroups" :key="group.key" :index="group.key">
    <template #title>...</template>
    <el-menu-item v-for="item in group.items" :key="item.key" :index="item.key" @click="setActiveTool(item.key)">...</el-menu-item>
  </el-sub-menu>
</el-menu>
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `npm test -- frontend/src/__tests__/appShell.structure.test.ts`
Expected: pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: refactor app shell navigation"
```

### Task 3: Tune shell CSS for the new layout

**Files:**
- Modify: `frontend/src/styles/base/workspace-header.css`
- Modify: `frontend/src/styles/base/shell-nav.css`
- Modify: `frontend/src/styles/responsive.css`

**Interfaces:**
- Consumes: the new shell markup from `App.vue`
- Produces: aligned component sizing, float-button spacing, and mobile behavior

- [ ] **Step 1: Write the failing style assertions**

```ts
expect(styles).toContain('.workspace-float-actions');
expect(styles).toContain('.el-menu');
expect(styles).toContain('.el-dropdown');
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm test -- frontend/src/__tests__/appShell.structure.test.ts`
Expected: fail until the styles are updated

- [ ] **Step 3: Update the shared shell CSS**

```css
.workspace-float-actions {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 120;
}
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `npm test -- frontend/src/__tests__/appShell.structure.test.ts`
Expected: pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/base/workspace-header.css frontend/src/styles/base/shell-nav.css frontend/src/styles/responsive.css
git commit -m "feat: tune shell ui styles"
```

### Task 4: Verify shell behavior and build output

**Files:**
- Review: all files touched above

**Interfaces:**
- Consumes: the refactored shell and style updates
- Produces: validated build and a short quality review

- [ ] **Step 1: Run the focused shell test**

Run: `npm test -- frontend/src/__tests__/appShell.structure.test.ts`

- [ ] **Step 2: Run the frontend build**

Run: `npm run build`

- [ ] **Step 3: Review any remaining shell-specific regressions**

Check: navigation order, float-button placement, dropdown behavior, dark mode, and mobile wrap

- [ ] **Step 4: Commit if validation is clean**

```bash
git add frontend/src/App.vue frontend/src/main.ts frontend/src/styles/base/workspace-header.css frontend/src/styles/base/shell-nav.css frontend/src/styles/responsive.css frontend/src/__tests__/appShell.structure.test.ts frontend/package.json frontend/package-lock.json
git commit -m "feat: complete shell ui upgrade"
```
