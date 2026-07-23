<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { useAppContext } from '@app/context';
import AppIcon from '@shared/components/AppIcon.vue';
import { errorMessage } from '@shared/utils/errors';
import {
  cancelBulkExecutionTask,
  createBulkExecutionTask,
  deleteBulkExecutionTask,
  getBulkExecutionTask,
  listBulkExecutionTargets,
  listBulkExecutionTasks,
} from '../api/bulkExecution';
import type { BulkExecutionResult, BulkExecutionStatus, BulkExecutionTarget, BulkExecutionTask, BulkExecutionTaskDetail } from '../types';

const DRAFT_TARGET_IDS_KEY = 'ops-tool.bulk-execution.draft-target-ids';
const statusLabels: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  canceled: '已取消',
  pending: '等待中',
  success: '成功',
  skipped: '已跳过',
};

const { activeTool, canUsePageAction, showToast, requestConfirm } = useAppContext();

const targets = ref<BulkExecutionTarget[]>([]);
const taskHistory = ref<BulkExecutionTask[]>([]);
const selectedTask = ref<BulkExecutionTaskDetail | null>(null);
const selectedTaskId = ref<number | null>(null);
const selectedTargetIds = ref<Set<number>>(new Set());
const expandedResultIds = ref<Set<number>>(new Set());
const isCreateOpen = ref(false);
const isLoading = ref(false);
const isTargetsLoading = ref(false);
const isCreating = ref(false);
const isControlBusy = ref(false);
const keyword = ref('');
const statusFilter = ref('');
const hostFilter = ref<number | ''>('');
const targetKeyword = ref('');
const taskName = ref('');
const commandInput = ref('');
let pollTimer: number | null = null;
let taskRequestId = 0;

const canExecute = computed(() => canUsePageAction('bulkExecution', 'execute'));
const canRefresh = computed(() => canUsePageAction('bulkExecution', 'refresh'));
const canCancel = computed(() => canUsePageAction('bulkExecution', 'cancel'));
const canDelete = computed(() => canUsePageAction('bulkExecution', 'delete'));
const hasRunningTask = computed(() => taskHistory.value.some((task) => task.status === 'queued' || task.status === 'running'));
const selectedTargets = computed(() => targets.value.filter((target) => selectedTargetIds.value.has(target.id)));
const filteredTargets = computed(() => {
  const query = targetKeyword.value.trim().toLowerCase();
  if (!query) return targets.value;
  return targets.value.filter((target) =>
    [target.name, target.privateIp, target.publicIp, target.groupName, target.loginUser, target.os, target.systemType, target.systemArch]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query)),
  );
});
const canCreateTask = computed(() => canExecute.value && selectedTargetIds.value.size > 0 && commandInput.value.trim().length > 0 && !isCreating.value);
const selectedTaskCanCancel = computed(() => Boolean(selectedTask.value && ['queued', 'running'].includes(selectedTask.value.status)));
const selectedTaskProgress = computed(() => {
  if (!selectedTask.value || selectedTask.value.targetCount <= 0) return 0;
  return Math.round((selectedTask.value.completedCount / selectedTask.value.targetCount) * 100);
});

onMounted(async () => {
  await refreshAll();
  applyDraftTargetIds();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});

watch([statusFilter, hostFilter], () => {
  void loadTasks();
});

watch(
  () => activeTool.value,
  (tool) => {
    if (tool === 'bulkExecution') {
      void refreshAll().then(applyDraftTargetIds);
    }
  },
);

async function refreshAll() {
  if (!canRefresh.value && !canExecute.value) return;
  isLoading.value = true;
  try {
    await Promise.all([loadTargets(), loadTasks()]);
  } finally {
    isLoading.value = false;
  }
}

async function loadTargets() {
  if (!canExecute.value) return;
  isTargetsLoading.value = true;
  try {
    targets.value = await listBulkExecutionTargets();
  } catch (error) {
    showToast('目标主机加载失败', errorMessage(error), 'error');
  } finally {
    isTargetsLoading.value = false;
  }
}

async function loadTasks() {
  if (!canRefresh.value) return;
  try {
    const page = await listBulkExecutionTasks({
      status: statusFilter.value,
      keyword: keyword.value.trim(),
      host: hostFilter.value,
      page: 1,
      pageSize: 50,
    });
    taskHistory.value = page.results;
    if (!taskHistory.value.length) {
      selectedTaskId.value = null;
      selectedTask.value = null;
      expandedResultIds.value = new Set();
      return;
    }
    if (!selectedTaskId.value || !taskHistory.value.some((task) => task.id === selectedTaskId.value)) {
      selectedTaskId.value = taskHistory.value[0].id;
    }
    if (selectedTaskId.value) await selectTask(selectedTaskId.value, false);
  } catch (error) {
    showToast('任务历史加载失败', errorMessage(error), 'error');
  }
}

async function selectTask(taskId: number, showError = true) {
  const requestId = ++taskRequestId;
  selectedTaskId.value = taskId;
  try {
    const detail = await getBulkExecutionTask(taskId);
    if (requestId !== taskRequestId || selectedTaskId.value !== taskId) return;
    selectedTask.value = detail;
    expandedResultIds.value = new Set([...expandedResultIds.value].filter((id) => detail.results.some((result) => result.id === id)));
  } catch (error) {
    if (requestId !== taskRequestId || selectedTaskId.value !== taskId) return;
    selectedTask.value = null;
    if (showError) showToast('任务详情加载失败', errorMessage(error), 'error');
  }
}

function applyDraftTargetIds() {
  if (typeof window === 'undefined') return;
  const raw = window.sessionStorage.getItem(DRAFT_TARGET_IDS_KEY);
  if (!raw) return;
  window.sessionStorage.removeItem(DRAFT_TARGET_IDS_KEY);
  try {
    const ids = JSON.parse(raw);
    if (!Array.isArray(ids)) return;
    const executableIds = new Set(targets.value.map((target) => target.id));
    const next = ids.map((id) => Number(id)).filter((id) => executableIds.has(id));
    if (!next.length) {
      showToast('没有可执行主机', '所选主机中没有已验证的 Linux SSH 主机。', 'error');
      return;
    }
    selectedTargetIds.value = new Set(next);
    isCreateOpen.value = true;
  } catch {
    selectedTargetIds.value = new Set();
  }
}

function toggleTarget(targetId: number, checked: boolean) {
  const next = new Set(selectedTargetIds.value);
  if (checked) next.add(targetId);
  else next.delete(targetId);
  selectedTargetIds.value = next;
}

function toggleAllFilteredTargets(checked: boolean) {
  const next = new Set(selectedTargetIds.value);
  for (const target of filteredTargets.value) {
    if (checked) next.add(target.id);
    else next.delete(target.id);
  }
  selectedTargetIds.value = next;
}

function toggleTargetFromEvent(targetId: number, event: Event) {
  toggleTarget(targetId, (event.target as HTMLInputElement).checked);
}

function toggleAllFilteredTargetsFromEvent(event: Event) {
  toggleAllFilteredTargets((event.target as HTMLInputElement).checked);
}

function openCreateDialog() {
  isCreateOpen.value = true;
}

function closeCreateDialog() {
  if (isCreating.value) return;
  isCreateOpen.value = false;
}

function createTaskWithConfirmation() {
  if (!canCreateTask.value) return;
  const run = async () => {
    await createTask();
  };
  const message = `将对 ${selectedTargetIds.value.size} 台主机执行命令：\n${commandInput.value.trim()}`;
  if (requestConfirm) requestConfirm('确认批量执行', message, '执行', run);
  else if (window.confirm(message)) void run();
}

async function createTask() {
  isCreating.value = true;
  try {
    const task = await createBulkExecutionTask({
      targetIds: [...selectedTargetIds.value],
      command: commandInput.value.trim(),
      name: taskName.value.trim() || undefined,
    });
    isCreateOpen.value = false;
    taskName.value = '';
    commandInput.value = '';
    selectedTargetIds.value = new Set();
    await loadTasks();
    await selectTask(task.id);
    showToast('批量执行已创建', '后台正在并发执行所选主机命令。', 'success');
  } catch (error) {
    showToast('任务创建失败', errorMessage(error), 'error');
  } finally {
    isCreating.value = false;
  }
}

async function cancelSelectedTask() {
  if (!selectedTaskId.value || !canCancel.value || isControlBusy.value) return;
  isControlBusy.value = true;
  try {
    await cancelBulkExecutionTask(selectedTaskId.value);
    await Promise.all([loadTasks(), selectTask(selectedTaskId.value, false)]);
    showToast('已请求取消', '任务会在当前 Ansible 执行结束后停止。', 'success');
  } catch (error) {
    showToast('取消任务失败', errorMessage(error), 'error');
  } finally {
    isControlBusy.value = false;
  }
}

function deleteSelectedTask() {
  if (!selectedTaskId.value || !canDelete.value) return;
  const taskId = selectedTaskId.value;
  const run = async () => {
    isControlBusy.value = true;
    try {
      await deleteBulkExecutionTask(taskId);
      selectedTaskId.value = null;
      selectedTask.value = null;
      await loadTasks();
      showToast('任务已删除', '批量执行历史已移除。', 'success');
    } catch (error) {
      showToast('删除任务失败', errorMessage(error), 'error');
    } finally {
      isControlBusy.value = false;
    }
  };
  if (requestConfirm) requestConfirm('删除批量执行任务', '删除后会同时移除每台主机的执行结果。', '删除', run);
  else void run();
}

function toggleResult(resultId: number) {
  const next = new Set(expandedResultIds.value);
  if (next.has(resultId)) next.delete(resultId);
  else next.add(resultId);
  expandedResultIds.value = next;
}

function isResultExpanded(resultId: number) {
  return expandedResultIds.value.has(resultId);
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (!hasRunningTask.value) return;
    await loadTasks();
    if (selectedTaskId.value) await selectTask(selectedTaskId.value, false);
  }, 3000);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function statusLabel(status: BulkExecutionStatus | BulkExecutionResult['status']) {
  return statusLabels[status] ?? status;
}

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : '-';
}
</script>

<template>
  <section class="bulk-execution-page">
    <article v-if="canRefresh || canExecute" class="bulk-execution-shell">
      <header class="bulk-execution-head">
        <div>
          <h2>批量执行</h2>
          <p>面向已验证 Linux SSH 主机并发执行 shell 命令。</p>
        </div>
        <div class="bulk-execution-actions">
          <button v-if="canExecute" class="primary" type="button" @click="openCreateDialog"><AppIcon name="terminal" :size="16" />新建任务</button>
          <button v-if="canRefresh" type="button" :disabled="isLoading" @click="refreshAll"><AppIcon name="refresh" :size="16" />刷新</button>
        </div>
      </header>

      <section class="bulk-execution-filters">
        <input v-model="keyword" type="search" placeholder="搜索任务或命令" @keyup.enter="loadTasks" />
        <select v-model="statusFilter" aria-label="任务状态">
          <option value="">全部状态</option>
          <option value="queued">排队中</option>
          <option value="running">执行中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
          <option value="canceled">已取消</option>
        </select>
        <select v-model="hostFilter" aria-label="目标主机">
          <option value="">全部主机</option>
          <option v-for="target in targets" :key="target.id" :value="target.id">{{ target.name }} / {{ target.privateIp }}</option>
        </select>
        <button type="button" :disabled="isLoading" @click="loadTasks"><AppIcon name="search" :size="15" />查询</button>
        <span>{{ taskHistory.length }} 个任务 · {{ targets.length }} 台可执行主机</span>
      </section>

      <main class="bulk-execution-layout">
        <aside class="bulk-task-list">
          <button
            v-for="task in taskHistory"
            :key="task.id"
            type="button"
            :class="{ active: selectedTaskId === task.id }"
            @click="selectTask(task.id)"
          >
            <strong>{{ task.name }}</strong>
            <span>{{ statusLabel(task.status) }} · {{ task.completedCount }}/{{ task.targetCount }}</span>
            <em>成功 {{ task.successCount }} / 失败 {{ task.failedCount }} / 跳过 {{ task.skippedCount }}</em>
            <small>{{ task.createdBy }} · {{ formatTime(task.createdAt) }}</small>
          </button>
          <div v-if="!taskHistory.length" class="bulk-empty">{{ isLoading ? '加载中...' : '暂无批量执行任务' }}</div>
        </aside>

        <section class="bulk-task-detail">
          <template v-if="selectedTask">
            <header>
              <div>
                <h3>{{ selectedTask.name }}</h3>
                <p>{{ selectedTask.createdBy }} · {{ statusLabel(selectedTask.status) }} · {{ selectedTaskProgress }}%</p>
              </div>
              <div>
                <button v-if="canCancel" type="button" :disabled="!selectedTaskCanCancel || isControlBusy" @click="cancelSelectedTask">取消</button>
                <button v-if="canDelete" class="danger" type="button" :disabled="isControlBusy" @click="deleteSelectedTask"><AppIcon name="trash" :size="15" />删除</button>
              </div>
            </header>
            <pre class="bulk-command-block">{{ selectedTask.command }}</pre>
            <p v-if="selectedTask.error" class="bulk-error">{{ selectedTask.error }}</p>
            <div class="bulk-progress"><span :style="{ width: `${selectedTaskProgress}%` }"></span></div>

            <div class="bulk-result-table">
              <div class="bulk-result-row head">
                <span>主机</span>
                <span>IP</span>
                <span>用户</span>
                <span>状态</span>
                <span>退出码</span>
                <span>耗时</span>
                <span>输出</span>
              </div>
              <template v-for="result in selectedTask.results" :key="result.id">
                <div class="bulk-result-row">
                  <strong>{{ result.hostName }}</strong>
                  <span>{{ result.hostIp }}:{{ result.hostPort }}</span>
                  <span>{{ result.loginUser || '-' }}</span>
                  <span class="bulk-status" :class="`status-${result.status}`">{{ statusLabel(result.status) }}</span>
                  <span>{{ result.exitCode ?? '-' }}</span>
                  <span>{{ formatTime(result.finishedAt || result.startedAt) }}</span>
                  <button type="button" @click="toggleResult(result.id)">
                    <AppIcon :name="isResultExpanded(result.id) ? 'chevronDown' : 'chevronRight'" :size="15" />
                  </button>
                </div>
                <div v-if="isResultExpanded(result.id)" class="bulk-result-output">
                  <div>
                    <strong>stdout</strong>
                    <pre>{{ result.stdout || '无标准输出' }}</pre>
                  </div>
                  <div>
                    <strong>stderr</strong>
                    <pre>{{ result.stderr || result.error || '无错误输出' }}</pre>
                  </div>
                  <span v-if="result.outputTruncated">输出已截断</span>
                </div>
              </template>
            </div>
          </template>
          <div v-else class="bulk-empty">请选择一个任务查看结果。</div>
        </section>
      </main>
    </article>
    <div v-else class="permission-empty">暂无可用功能</div>

    <div v-if="isCreateOpen" class="modal-backdrop bulk-create-backdrop" @click.self="closeCreateDialog">
      <form class="bulk-create-modal" @submit.prevent="createTaskWithConfirmation">
        <button class="modal-close" type="button" :disabled="isCreating" @click="closeCreateDialog"><AppIcon name="x" :size="16" /></button>
        <h2>新建批量执行</h2>
        <div class="bulk-create-grid">
          <label>
            <span>任务名称</span>
            <input v-model="taskName" maxlength="180" placeholder="留空自动生成" :disabled="isCreating" />
          </label>
          <label>
            <span>命令</span>
            <textarea v-model="commandInput" class="commandInput" rows="6" maxlength="4096" :disabled="isCreating"></textarea>
          </label>
        </div>
        <div class="bulk-target-picker">
          <header>
            <label>
              <input
                type="checkbox"
                :checked="filteredTargets.length > 0 && filteredTargets.every((target) => selectedTargetIds.has(target.id))"
                @change="toggleAllFilteredTargetsFromEvent"
              />
              全选当前列表
            </label>
            <input v-model="targetKeyword" type="search" placeholder="搜索主机 / IP / 分组" />
            <span>已选 {{ selectedTargets.length }} / {{ targets.length }}</span>
          </header>
          <div class="bulk-target-list">
            <label v-for="target in filteredTargets" :key="target.id">
              <input type="checkbox" :checked="selectedTargetIds.has(target.id)" @change="toggleTargetFromEvent(target.id, $event)" />
              <strong>{{ target.name }}</strong>
              <span>{{ target.privateIp }} · {{ target.loginUser }} · {{ target.groupName }}</span>
            </label>
            <div v-if="!filteredTargets.length" class="bulk-empty">{{ isTargetsLoading ? '加载中...' : '暂无可执行 Linux SSH 主机' }}</div>
          </div>
        </div>
        <footer>
          <button type="button" :disabled="isCreating" @click="closeCreateDialog">取消</button>
          <button class="primary" type="submit" :disabled="!canCreateTask">{{ isCreating ? '创建中...' : '执行' }}</button>
        </footer>
      </form>
    </div>
  </section>
</template>
