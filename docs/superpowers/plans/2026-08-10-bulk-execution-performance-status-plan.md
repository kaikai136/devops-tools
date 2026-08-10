# 批量执行性能与状态统计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让批量执行列表在执行期间保持流畅，并在状态列实时显示每个任务的成功和失败数量。

**Architecture:** 继续使用现有任务列表接口返回的轻量 `BulkExecutionTask` 数据。`loadTasks()` 只刷新列表；详情结果仅由详情弹窗主动加载或在弹窗打开期间轮询刷新。轮询使用单个进行中标记防止请求重叠，状态列使用任务已有的 `successCount` 和 `failedCount` 字段。

**Tech Stack:** Vue 3 Composition API、TypeScript、Vitest、现有批量执行 CSS。

## Global Constraints

- 不修改后端任务状态定义、数据库字段和执行协议。
- 不改变任务筛选、分页、取消、删除和重新执行行为。
- 列表轮询间隔为 5 秒。
- 详情弹窗未打开时不得请求或渲染主机级 `results` 数据。
- 状态列格式固定为 `成功 X / 失败 Y`，计数缺失时按 `0` 显示。

---

### Task 1: 添加性能与状态展示回归测试

**Files:**
- Modify: `frontend/src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts`

**Interfaces:**
- Consumes: `BulkExecutionPanel.vue` source text through the existing `readSource()` helper.
- Produces: structural regression coverage for lazy detail loading, polling deduplication, and status counts.

- [ ] **Step 1: Write the failing tests**

在现有测试文件末尾新增测试，断言：

```ts
it('keeps task polling lightweight and shows success and failure counts in the status column', () => {
  const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');
  const listLoader = panel.match(/async function loadTasks\(\)[\s\S]*?async function selectTask/)?.[0] ?? '';
  const polling = panel.match(/function startPolling\(\)[\s\S]*?function stopPolling/)?.[0] ?? '';
  const taskRow = panel.match(/<tr[\s\S]*?v-for="task in taskHistory"[\s\S]*?<\/tr>/)?.[0] ?? '';

  expect(listLoader).not.toContain('selectTask(');
  expect(panel).toContain('const pollInFlight = ref(false)');
  expect(polling).toContain('if (pollInFlight.value) return');
  expect(polling).toContain('isTaskDetailOpen.value');
  expect(polling).toContain('5000');
  expect(panel).toContain('function taskResultSummary(task: BulkExecutionTask)');
  expect(taskRow).toContain('{{ taskResultSummary(task) }}');
  expect(taskRow).not.toContain('{{ statusLabel(task.status) }}');
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```text
npm run test:run -- src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts
```

Expected: the new test fails because `loadTasks()` currently calls `selectTask()`, the poll interval is `3000`, no `pollInFlight` guard exists, and the row still renders `statusLabel(task.status)`.

- [ ] **Step 3: Keep the test focused**

Do not add backend tests or a new API contract because the task list serializer already exposes `successCount` and `failedCount`; this regression is caused by frontend request flow and rendering.

### Task 2: Make task list loading and polling lazy

**Files:**
- Modify: `frontend/src/features/bulk-execution/components/BulkExecutionPanel.vue`

**Interfaces:**
- Consumes: existing `listBulkExecutionTasks()`, `selectTask()`, `isTaskDetailOpen`, `selectedTaskId`, and task status fields.
- Produces: `loadTasks()` as a list-only loader and `startPolling()` with a single in-flight request.

- [ ] **Step 1: Add the polling guard state**

Near `pollTimer`, add:

```ts
let pollTimer: number | null = null;
const pollInFlight = ref(false);
let taskRequestId = 0;
```

- [ ] **Step 2: Remove implicit detail loading from `loadTasks()`**

Keep list pagination, selection fallback, empty-list cleanup, and error handling unchanged. Remove the final implicit detail call:

```ts
if (selectedTaskId.value) await selectTask(selectedTaskId.value, false, false);
```

The function must return after updating `taskHistory`; it must not fetch `results` while the modal is closed.

- [ ] **Step 3: Gate detail refresh on the open modal and running task**

Add a helper beside `hasRunningTask`:

```ts
function isTaskRunning(taskId: number) {
  const task = taskHistory.value.find((item) => item.id === taskId);
  return task?.status === 'queued' || task?.status === 'running';
}
```

Use it in polling so a selected completed task is not refreshed just because another task is running:

```ts
if (isTaskDetailOpen.value && selectedTaskId.value && isTaskRunning(selectedTaskId.value)) {
  await selectTask(selectedTaskId.value, false, false);
}
```

- [ ] **Step 4: Add the non-overlapping 5-second poll loop**

Replace the current interval callback with:

```ts
pollTimer = window.setInterval(async () => {
  if (!hasRunningTask.value || pollInFlight.value) return;
  pollInFlight.value = true;
  try {
    await loadTasks();
    if (isTaskDetailOpen.value && selectedTaskId.value && isTaskRunning(selectedTaskId.value)) {
      await selectTask(selectedTaskId.value, false, false);
    }
  } finally {
    pollInFlight.value = false;
  }
}, 5000);
```

Keep `stopPolling()` clearing the timer. Do not start a second timer from any other path.

- [ ] **Step 5: Preserve explicit detail loading flows**

Keep `openTaskDetail()` calling `selectTask()` before opening the modal. Keep create, rerun, cancel, delete, and manual refresh flows working by leaving their explicit `selectTask()` calls intact where they are needed.

- [ ] **Step 6: Run the focused test**

Run:

```text
npm run test:run -- src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts
```

Expected: Task 1's new test passes and all existing structure tests remain green.

### Task 3: Replace the task status cell with success/failure counts

**Files:**
- Modify: `frontend/src/features/bulk-execution/components/BulkExecutionPanel.vue`
- Modify: `frontend/src/styles/tools/bulk-execution.css`
- Test: `frontend/src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts`

**Interfaces:**
- Consumes: `BulkExecutionTask.successCount` and `BulkExecutionTask.failedCount`.
- Produces: `taskResultSummary(task: BulkExecutionTask): string` and a compact status summary cell.

- [ ] **Step 1: Add the pure formatter before changing the template**

Add:

```ts
function taskResultSummary(task: BulkExecutionTask) {
  return `成功 ${task.successCount ?? 0} / 失败 ${task.failedCount ?? 0}`;
}
```

- [ ] **Step 2: Replace the list status cell**

Change the task row status cell to:

```vue
<td class="is-center cell-status-summary" :title="statusLabel(task.status)">
  {{ taskResultSummary(task) }}
</td>
```

Keep the task-level `status` field for filtering and polling; do not alter the result table's host-level status badges.

- [ ] **Step 3: Adjust the status column width and text styling**

Increase the fixed status column width enough for the summary and add a compact style:

```css
.bulk-record-grid .col-status { width: 150px; }

.bulk-record-grid .cell-status-summary {
  color: var(--bulk-ink);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
```

Keep the table's existing fixed layout and row density.

- [ ] **Step 4: Run the focused test**

Run:

```text
npm run test:run -- src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts
```

Expected: all frontend structure tests pass.

### Task 4: Verify the complete change

**Files:**
- Check: `frontend/src/features/bulk-execution/components/BulkExecutionPanel.vue`
- Check: `frontend/src/styles/tools/bulk-execution.css`
- Check: `frontend/src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts`

- [ ] **Step 1: Run the complete frontend build**

Run:

```text
npm run build
```

Expected: exit code `0`.

- [ ] **Step 2: Run the backend regression suite**

Run:

```text
python manage.py test bulk_execution
```

Expected: all bulk execution tests pass; no backend behavior was changed, but the existing suite guards the count fields used by the frontend.

- [ ] **Step 3: Check whitespace and inspect the diff**

Run:

```text
git diff --check
git diff -- frontend/src/features/bulk-execution/components/BulkExecutionPanel.vue frontend/src/features/bulk-execution/__tests__/bulkExecution.structure.test.ts frontend/src/styles/tools/bulk-execution.css
```

Expected: no whitespace errors, and the diff contains only the lazy polling, status summary, and related test/style changes.
