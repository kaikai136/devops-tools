<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue';

import { appContextKey } from '../../appContext';
import AppIcon from '../common/AppIcon.vue';
import {
  createSecurityScanTask,
  deleteSecurityScanTask,
  exportSecurityScanTask,
  getSecurityScanTask,
  listSecurityScanFindings,
  listSecurityScanHosts,
  listSecurityScanTasks,
} from '../../services/securityScans';
import type { SecurityScanFinding, SecurityScanHostTarget, SecurityScanStatus, SecurityScanTask, SecurityScanTaskDetail } from '../../types';
import { errorMessage } from '../../utils/errors';

const DEFAULT_PORTS = '21,22,23,25,53,80,110,139,143,443,445,3306,5432,5900,6379,8080,8443,27017';
const statusLabels: Record<string, string> = { queued: '排队中', running: '扫描中', completed: '已完成', failed: '失败', pending: '等待中' };
const severityLabels = { critical: '严重', high: '高危', medium: '中危', low: '低危', info: '提示' };

const appContext = inject(appContextKey);
const canUsePageAction = appContext?.canUsePageAction ?? (() => true);
const showToast = appContext?.showToast ?? (() => undefined);
const requestConfirm = appContext?.requestConfirm;

const hosts = ref<SecurityScanHostTarget[]>([]);
const tasks = ref<SecurityScanTask[]>([]);
const selectedTask = ref<SecurityScanTaskDetail | null>(null);
const selectedTaskId = ref<number | null>(null);
const findings = ref<SecurityScanFinding[]>([]);
const findingsPage = ref(1);
const findingsTotal = ref(0);
const findingsHasNext = ref(false);
const isLoading = ref(false);
const isLoadingFindings = ref(false);
const isCreating = ref(false);
const isDialogOpen = ref(false);
const keyword = ref('');
const hostKeyword = ref('');
const statusFilter = ref('');
const selectedHostIds = ref<Set<number>>(new Set());
const portsInput = ref(DEFAULT_PORTS);
const enableBaseline = ref(true);
const enablePortScan = ref(true);
const enableCveScan = ref(true);
let pollTimer: number | null = null;
let taskSelectionRequest = 0;

const filteredHosts = computed(() => {
  const term = hostKeyword.value.trim().toLowerCase();
  if (!term) return hosts.value;
  return hosts.value.filter((host) =>
    [host.name, host.privateIp, host.groupName, host.os, host.systemType].some((value) => String(value || '').toLowerCase().includes(term)),
  );
});
const selectedHosts = computed(() => hosts.value.filter((host) => selectedHostIds.value.has(host.id)));
const canStartScan = computed(() => selectedHostIds.value.size > 0 && (enableBaseline.value || enablePortScan.value || enableCveScan.value) && !isCreating.value);
const hasRunningTask = computed(() => tasks.value.some((task) => task.status === 'queued' || task.status === 'running'));
const hostResults = computed(() => selectedTask.value?.hostResults ?? []);

onMounted(async () => {
  await Promise.all([loadHosts(), loadTasks()]);
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});

async function loadHosts() {
  try {
    hosts.value = await listSecurityScanHosts();
  } catch (error) {
    showToast('目标主机加载失败', errorMessage(error), 'error');
  }
}

async function loadTasks() {
  isLoading.value = true;
  try {
    tasks.value = await listSecurityScanTasks({ status: statusFilter.value, keyword: keyword.value.trim() });
    if (!selectedTaskId.value && tasks.value.length) selectedTaskId.value = tasks.value[0].id;
    if (selectedTaskId.value) {
      if (selectedTask.value) await refreshSelectedTaskSummary();
      else await selectTask(selectedTaskId.value, false);
    }
  } catch (error) {
    showToast('扫描任务加载失败', errorMessage(error), 'error');
  } finally {
    isLoading.value = false;
  }
}

async function selectTask(taskId: number, showError = true) {
  const requestId = ++taskSelectionRequest;
  selectedTaskId.value = taskId;
  findings.value = [];
  findingsPage.value = 1;
  findingsTotal.value = 0;
  findingsHasNext.value = false;
  isLoadingFindings.value = false;
  try {
    const detail = await getSecurityScanTask(taskId);
    if (requestId !== taskSelectionRequest || selectedTaskId.value !== taskId) return;
    selectedTask.value = detail;
    await loadFindings(taskId, 1, true, requestId);
  } catch (error) {
    if (requestId !== taskSelectionRequest || selectedTaskId.value !== taskId) return;
    selectedTask.value = null;
    if (showError) showToast('任务详情加载失败', errorMessage(error), 'error');
  }
}

async function refreshSelectedTaskSummary() {
  if (!selectedTaskId.value) return;
  try {
    selectedTask.value = await getSecurityScanTask(selectedTaskId.value);
  } catch {
    selectedTask.value = null;
  }
}

async function loadFindings(taskId = selectedTaskId.value, page = findingsPage.value + 1, replace = false, requestId = taskSelectionRequest) {
  if (!taskId || isLoadingFindings.value) return;
  isLoadingFindings.value = true;
  try {
    const payload = await listSecurityScanFindings(taskId, { page, pageSize: 50 });
    if (requestId !== taskSelectionRequest || selectedTaskId.value !== taskId) return;
    findings.value = replace ? payload.results : [...findings.value, ...payload.results];
    findingsPage.value = payload.page;
    findingsTotal.value = payload.total;
    findingsHasNext.value = payload.hasNext;
  } catch (error) {
    if (requestId !== taskSelectionRequest || selectedTaskId.value !== taskId) return;
    if (replace) findings.value = [];
    showToast('婕忔礊鏄庣粏鍔犺浇澶辫触', errorMessage(error), 'error');
  } finally {
    if (requestId === taskSelectionRequest && selectedTaskId.value === taskId) {
      isLoadingFindings.value = false;
    }
  }
}

function toggleHost(hostId: number, checked: boolean) {
  const next = new Set(selectedHostIds.value);
  if (checked) next.add(hostId);
  else next.delete(hostId);
  selectedHostIds.value = next;
}

function toggleAllVisibleHosts(checked: boolean) {
  const next = new Set(selectedHostIds.value);
  for (const host of filteredHosts.value) {
    if (checked) next.add(host.id);
    else next.delete(host.id);
  }
  selectedHostIds.value = next;
}

async function startScan() {
  if (!canStartScan.value) return;
  isCreating.value = true;
  try {
    const task = await createSecurityScanTask({
      hostIds: [...selectedHostIds.value],
      portsInput: portsInput.value,
      enableBaseline: enableBaseline.value,
      enablePortScan: enablePortScan.value,
      enableCveScan: enableCveScan.value,
    });
    isDialogOpen.value = false;
    selectedHostIds.value = new Set();
    await loadTasks();
    await selectTask(task.id);
    showToast('扫描任务已创建', '后台正在执行安全扫描。', 'success');
  } catch (error) {
    showToast('扫描任务创建失败', errorMessage(error), 'error');
  } finally {
    isCreating.value = false;
  }
}

async function exportTask(format: 'csv' | 'json') {
  if (!selectedTaskId.value) return;
  try {
    const blob = await exportSecurityScanTask(selectedTaskId.value, format);
    downloadBlob(blob, `security-scan-${selectedTaskId.value}.${format}`);
  } catch (error) {
    showToast('报告导出失败', errorMessage(error), 'error');
  }
}

function removeSelectedTask() {
  if (!selectedTaskId.value) return;
  const taskId = selectedTaskId.value;
  const run = async () => {
    try {
      await deleteSecurityScanTask(taskId);
      selectedTaskId.value = null;
      selectedTask.value = null;
      findings.value = [];
      findingsPage.value = 1;
      findingsTotal.value = 0;
      findingsHasNext.value = false;
      await loadTasks();
      showToast('扫描任务已删除', '历史记录和扫描结果已移除。', 'success');
    } catch (error) {
      showToast('删除失败', errorMessage(error), 'error');
    }
  };
  if (requestConfirm) {
    requestConfirm('删除扫描任务', '删除后将同时移除该任务下的主机结果和漏洞明细。', '删除', run);
  } else {
    void run();
  }
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (hasRunningTask.value) await loadTasks();
  }, 5000);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function riskTotal(task: SecurityScanTask | SecurityScanTaskDetail) {
  const counts = task.riskCounts;
  return counts.critical + counts.high + counts.medium + counts.low + counts.info;
}

function statusLabel(status: SecurityScanStatus | 'pending') {
  return statusLabels[status] ?? status;
}

function formatTime(value: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function severityClass(severity: SecurityScanFinding['severity']) {
  return `severity-${severity}`;
}
</script>

<template>
  <section class="security-scan-page">
    <header class="security-scan-toolbar">
      <div class="security-scan-title">
        <h2>安全扫描</h2>
        <p>选择已验证 Linux 主机，执行基线、端口风险与 CVE 漏洞扫描。</p>
      </div>
      <div class="security-scan-actions">
        <button v-if="canUsePageAction('securityScan', 'scan')" type="button" @click="isDialogOpen = true"><AppIcon name="scan" :size="16" />新建扫描</button>
        <button v-if="canUsePageAction('securityScan', 'refresh')" type="button" :disabled="isLoading" @click="loadTasks"><AppIcon name="refresh" :size="16" />刷新</button>
        <button v-if="canUsePageAction('securityScan', 'export')" type="button" :disabled="!selectedTaskId" @click="exportTask('csv')"><AppIcon name="download" :size="16" />CSV</button>
        <button v-if="canUsePageAction('securityScan', 'export')" type="button" :disabled="!selectedTaskId" @click="exportTask('json')"><AppIcon name="download" :size="16" />JSON</button>
        <button v-if="canUsePageAction('securityScan', 'delete')" class="danger" type="button" :disabled="!selectedTaskId" @click="removeSelectedTask"><AppIcon name="trash" :size="16" />删除</button>
      </div>
    </header>

    <div class="security-scan-filters">
      <input v-model="keyword" type="search" placeholder="搜索任务 / 主机 / IP" @keyup.enter="loadTasks" />
      <select v-model="statusFilter" @change="loadTasks">
        <option value="">全部状态</option>
        <option value="queued">排队中</option>
        <option value="running">扫描中</option>
        <option value="completed">已完成</option>
        <option value="failed">失败</option>
      </select>
      <span>可扫描 Linux 主机 {{ hosts.length }} 台</span>
    </div>

    <div class="security-scan-layout">
      <section class="security-task-list">
        <table>
          <thead>
            <tr>
              <th>任务</th>
              <th>状态</th>
              <th>进度</th>
              <th>风险</th>
              <th>开始时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id" :class="{ active: task.id === selectedTaskId }" @click="selectTask(task.id)">
              <td><strong>{{ task.name }}</strong><span>{{ task.createdBy }}</span></td>
              <td><em class="scan-status" :class="`status-${task.status}`">{{ statusLabel(task.status) }}</em></td>
              <td>{{ task.completedCount }} / {{ task.targetCount }}</td>
              <td class="risk-inline">
                <b class="severity-critical">{{ task.riskCounts.critical }}</b>
                <b class="severity-high">{{ task.riskCounts.high }}</b>
                <b class="severity-medium">{{ task.riskCounts.medium }}</b>
                <b class="severity-low">{{ task.riskCounts.low }}</b>
                <b class="severity-info">{{ task.riskCounts.info }}</b>
              </td>
              <td>{{ formatTime(task.startedAt || task.createdAt) }}</td>
            </tr>
            <tr v-if="!tasks.length">
              <td colspan="5" class="security-empty">暂无扫描任务。</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="security-task-detail">
        <template v-if="selectedTask">
          <div class="security-summary">
            <article><span>目标</span><strong>{{ selectedTask.targetCount }}</strong></article>
            <article><span>已完成</span><strong>{{ selectedTask.completedCount }}</strong></article>
            <article><span>风险总数</span><strong>{{ riskTotal(selectedTask) }}</strong></article>
            <article><span>状态</span><strong>{{ statusLabel(selectedTask.status) }}</strong></article>
          </div>

          <div class="security-detail-grid">
            <section>
              <h3>主机结果</h3>
              <div class="host-result-list">
                <article v-for="host in hostResults" :key="host.id">
                  <div><strong>{{ host.hostName }}</strong><span>{{ host.hostIp }} · {{ host.os || host.systemType || '-' }}</span></div>
                  <em class="scan-status" :class="`status-${host.status}`">{{ statusLabel(host.status) }}</em>
                  <small>{{ host.packageCount }} packages · {{ host.openPorts.length }} ports</small>
                </article>
              </div>
            </section>
            <section>
              <h3>漏洞明细</h3>
              <span class="finding-count">{{ findings.length }} / {{ findingsTotal }}</span>
              <div class="finding-list">
                <article v-for="finding in findings" :key="finding.id">
                  <div class="finding-head">
                    <span :class="severityClass(finding.severity)">{{ severityLabels[finding.severity] }}</span>
                    <strong>{{ finding.title }}</strong>
                  </div>
                  <p>{{ finding.hostName }} · {{ finding.cveId || finding.category }} · {{ finding.packageName || finding.service || '-' }}</p>
                  <small>{{ finding.recommendation }}</small>
                </article>
                <button v-if="findingsHasNext" class="finding-load-more" type="button" :disabled="isLoadingFindings" @click="loadFindings()">
                  <AppIcon name="chevronsRight" :size="16" />{{ isLoadingFindings ? 'Loading...' : 'Load more' }}
                </button>
                <div v-if="!findings.length" class="security-empty">当前任务还没有漏洞明细。</div>
              </div>
            </section>
          </div>
        </template>
        <div v-else class="security-empty">请选择一个扫描任务查看详情。</div>
      </section>
    </div>

    <div v-if="isDialogOpen" class="security-modal-backdrop">
      <section class="security-modal">
        <header>
          <h3>新建安全扫描</h3>
          <button type="button" aria-label="关闭" @click="isDialogOpen = false"><AppIcon name="x" :size="16" /></button>
        </header>
        <div class="scan-options">
          <label><input v-model="enableBaseline" type="checkbox" />基线扫描</label>
          <label><input v-model="enablePortScan" type="checkbox" />端口风险</label>
          <label><input v-model="enableCveScan" type="checkbox" />CVE 扫描</label>
        </div>
        <label class="ports-input">
          <span>扫描端口</span>
          <textarea v-model="portsInput" rows="3"></textarea>
        </label>
        <div class="host-picker-head">
          <label><input type="checkbox" :checked="filteredHosts.length > 0 && filteredHosts.every((host) => selectedHostIds.has(host.id))" @change="toggleAllVisibleHosts(($event.target as HTMLInputElement).checked)" />全选当前列表</label>
          <input v-model="hostKeyword" type="search" placeholder="搜索主机 / IP / 分组" />
          <span>已选 {{ selectedHosts.length }} / {{ hosts.length }}</span>
        </div>
        <div class="host-picker-list">
          <label v-for="host in filteredHosts" :key="host.id">
            <input type="checkbox" :checked="selectedHostIds.has(host.id)" @change="toggleHost(host.id, ($event.target as HTMLInputElement).checked)" />
            <strong>{{ host.name }}</strong>
            <span>{{ host.privateIp }} · {{ host.os }} · {{ host.groupName }}</span>
          </label>
          <div v-if="!filteredHosts.length" class="security-empty">暂无可扫描 Linux 主机。</div>
        </div>
        <footer>
          <button type="button" @click="isDialogOpen = false">取消</button>
          <button class="primary" type="button" :disabled="!canStartScan" @click="startScan">开始扫描</button>
        </footer>
      </section>
    </div>
  </section>
</template>
