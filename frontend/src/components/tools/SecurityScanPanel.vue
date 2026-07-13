<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue';

import { appContextKey } from '@app/context';
import {
  cancelSecurityScanTask,
  createSecurityScanTask,
  deleteSecurityScanTask,
  exportSecurityScanTask,
  getSecurityScanSummary,
  getSecurityScanTask,
  listSecurityScanFindings,
  listSecurityScanTargets,
  listSecurityScanTasks,
  retryFailedSecurityScanTargets,
} from '../../services/securityScans';
import type {
  SecurityScanFinding,
  SecurityScanSeverity,
  SecurityScanStatus,
  SecurityScanSummary,
  SecurityScanTarget,
  SecurityScanTargetResult,
  SecurityScanTask,
  SecurityScanTaskDetail,
} from '../../types';
import { errorMessage } from '@shared/utils/errors';
import AppIcon from '@shared/components/AppIcon.vue';

const DEFAULT_PORTS = '21,22,23,25,53,80,110,139,143,443,445,3306,3389,5432,5900,6379,8080,8443,27017';
const emptyRiskCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
const statusLabels: Record<string, string> = {
  queued: '排队中',
  running: '扫描中',
  completed: '已完成',
  failed: '失败',
  canceled: '已取消',
  pending: '等待中',
  skipped: '已跳过',
};
const severityLabels: Record<SecurityScanSeverity, string> = { critical: '严重', high: '高危', medium: '中危', low: '低危', info: '提示' };
const categoryLabels: Record<string, string> = { baseline: '基线', port: '端口', cve: 'CVE' };
const severityOrder: SecurityScanSeverity[] = ['critical', 'high', 'medium', 'low', 'info'];

interface AssetRiskReportRow {
  id: number;
  index: number;
  hostName: string;
  hostIp: string;
  businessGroup: string;
  owner: string;
  coreAsset: string;
  riskTotal: number;
  riskType: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

interface ImpactReportRow {
  key: string;
  index: number;
  title: string;
  severity: SecurityScanSeverity;
  riskType: string;
  affectedAssets: string;
  affectedAssetCount: number;
  occurrences: number;
}

type ReportTabKey = 'overview' | 'assets' | 'impact' | 'details';

const appContext = inject(appContextKey);
const canUsePageAction = appContext?.canUsePageAction ?? (() => true);
const showToast = appContext?.showToast ?? (() => undefined);
const requestConfirm = appContext?.requestConfirm;

const targets = ref<SecurityScanTarget[]>([]);
const tasks = ref<SecurityScanTask[]>([]);
const selectedTask = ref<SecurityScanTaskDetail | null>(null);
const selectedTaskId = ref<number | null>(null);
const summary = ref<SecurityScanSummary>({
  riskCounts: emptyRiskCounts,
  taskCounts: { total: 0, running: 0, failed: 0 },
  failedTargetCount: 0,
  latestTaskId: null,
  vulnerabilitySource: { onlineCveEnabled: false, nvdApiKeyConfigured: false, sources: [] },
});
const findings = ref<SecurityScanFinding[]>([]);
const findingsPage = ref(1);
const findingsTotal = ref(0);
const findingsHasNext = ref(false);
const isLoading = ref(false);
const isLoadingFindings = ref(false);
const isCreating = ref(false);
const isControlBusy = ref(false);
const isDrawerOpen = ref(false);
const keyword = ref('');
const statusFilter = ref('');
const findingKeyword = ref('');
const severityFilter = ref('');
const categoryFilter = ref('');
const targetResultFilter = ref('');
const targetKeyword = ref('');
const activeReportTab = ref<ReportTabKey>('overview');
const selectedTargetIds = ref<Set<number>>(new Set());
const taskName = ref('');
const portsInput = ref(DEFAULT_PORTS);
const scanBaseline = ref(true);
const scanPorts = ref(true);
const scanCve = ref(false);
let pollTimer: number | null = null;
let taskSelectionRequest = 0;

const filteredTargets = computed(() => {
  const term = targetKeyword.value.trim().toLowerCase();
  if (!term) return targets.value;
  return targets.value.filter((target) =>
    [target.name, target.privateIp, target.groupName, target.os, target.systemType, target.systemArch].some((value) => String(value || '').toLowerCase().includes(term)),
  );
});
const selectedTargets = computed(() => targets.value.filter((target) => selectedTargetIds.value.has(target.id)));
const targetResults = computed(() => selectedTask.value?.targetResults ?? []);
const canStartScan = computed(() => selectedTargetIds.value.size > 0 && (scanBaseline.value || scanPorts.value || scanCve.value) && !isCreating.value);
const hasRunningTask = computed(() => tasks.value.some((task) => task.status === 'queued' || task.status === 'running'));
const failedTargetsInSelectedTask = computed(() => targetResults.value.filter((target) => target.status === 'failed').length);
const selectedTaskCanCancel = computed(() => Boolean(selectedTask.value && ['queued', 'running'].includes(selectedTask.value.status)));
const selectedTaskRiskTotal = computed(() => (selectedTask.value ? riskTotal(selectedTask.value.riskCounts) : 0));
const sourceStatusText = computed(() => (summary.value.vulnerabilitySource.onlineCveEnabled ? '在线 CVE 已开启' : '在线 CVE 已关闭'));
const selectedTaskReportTime = computed(() => formatTime(selectedTask.value?.finishedAt || selectedTask.value?.startedAt || selectedTask.value?.createdAt || null));
const selectedTaskModulesText = computed(() => {
  if (!selectedTask.value) return '-';
  const modules = selectedTask.value.scanModules;
  const labels = [
    modules.baseline ? '基线检查' : '',
    modules.ports ? '端口风险' : '',
    modules.cve ? 'CVE 检查' : '',
  ].filter(Boolean);
  return labels.length ? labels.join(' / ') : '-';
});
const taskOptionsLabel = computed(() => (tasks.value.length ? `扫描任务 ${tasks.value.length} 个` : '暂无扫描任务'));
const findingsByTarget = computed(() => {
  const grouped = new Map<number, SecurityScanFinding[]>();
  for (const finding of findings.value) {
    const bucket = grouped.get(finding.targetResult) ?? [];
    bucket.push(finding);
    grouped.set(finding.targetResult, bucket);
  }
  return grouped;
});
const targetGroupByHostId = computed(() => {
  const grouped = new Map<number, string>();
  for (const target of targets.value) grouped.set(target.id, target.groupName || '-');
  return grouped;
});
const assetRiskRows = computed<AssetRiskReportRow[]>(() =>
  targetResults.value.map((target, index) => {
    const targetFindings = findingsByTarget.value.get(target.id) ?? [];
    const categories = uniqueStrings(targetFindings.map((finding) => categoryLabel(finding.category)));
    const total = riskTotal(target.riskCounts);
    return {
      id: target.id,
      index: index + 1,
      hostName: target.hostName || '-',
      hostIp: target.hostIp || '-',
      businessGroup: target.host ? targetGroupByHostId.value.get(target.host) || '-' : '-',
      owner: target.loginUser || '-',
      coreAsset: '否',
      riskTotal: total,
      riskType: categories.length ? categories.join(' / ') : total ? '风险项' : '无风险',
      critical: target.riskCounts.critical,
      high: target.riskCounts.high,
      medium: target.riskCounts.medium,
      low: target.riskCounts.low,
      info: target.riskCounts.info,
    };
  }),
);
const impactRows = computed<ImpactReportRow[]>(() => {
  const grouped = new Map<
    string,
    {
      title: string;
      severity: SecurityScanSeverity;
      categories: Set<string>;
      assets: Set<string>;
      occurrences: number;
    }
  >();
  for (const finding of findings.value) {
    const key = finding.title || `finding-${finding.id}`;
    const row = grouped.get(key) ?? {
      title: finding.title || '-',
      severity: finding.severity,
      categories: new Set<string>(),
      assets: new Set<string>(),
      occurrences: 0,
    };
    row.severity = higherSeverity(row.severity, finding.severity);
    row.categories.add(categoryLabel(finding.category));
    row.assets.add(finding.targetIp || finding.targetName || '-');
    row.occurrences += 1;
    grouped.set(key, row);
  }
  return [...grouped.entries()]
    .map(([key, row], index) => ({
      key,
      index: index + 1,
      title: row.title,
      severity: row.severity,
      riskType: [...row.categories].join(' / ') || '-',
      affectedAssets: [...row.assets].join(' '),
      affectedAssetCount: row.assets.size,
      occurrences: row.occurrences,
    }))
    .sort((left, right) => severityRank(left.severity) - severityRank(right.severity) || right.occurrences - left.occurrences || left.title.localeCompare(right.title, 'zh-Hans-CN'))
    .map((row, index) => ({ ...row, index: index + 1 }));
});
const reportTabs = computed<Array<{ key: ReportTabKey; label: string; count: number }>>(() => [
  { key: 'overview', label: '综述', count: selectedTaskRiskTotal.value },
  { key: 'assets', label: '资产风险统计', count: assetRiskRows.value.length },
  { key: 'impact', label: '漏洞影响统计', count: impactRows.value.length },
  { key: 'details', label: '漏洞详情', count: findingsTotal.value },
]);

onMounted(async () => {
  await refreshAll();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});

watch([severityFilter, categoryFilter, targetResultFilter], () => {
  void reloadFindings();
});

async function refreshAll() {
  isLoading.value = true;
  try {
    await Promise.all([loadTargets(), loadSummary(), loadTasks()]);
  } finally {
    isLoading.value = false;
  }
}

async function loadTargets() {
  try {
    targets.value = await listSecurityScanTargets();
  } catch (error) {
    showToast('目标主机加载失败', errorMessage(error), 'error');
  }
}

async function loadSummary() {
  try {
    summary.value = await getSecurityScanSummary();
    if (!summary.value.vulnerabilitySource.onlineCveEnabled) scanCve.value = false;
  } catch (error) {
    showToast('安全扫描概览加载失败', errorMessage(error), 'error');
  }
}

async function loadTasks() {
  try {
    tasks.value = await listSecurityScanTasks({ status: statusFilter.value, keyword: keyword.value.trim() });
    if (!tasks.value.length) {
      selectedTaskId.value = null;
      selectedTask.value = null;
      findings.value = [];
      findingsPage.value = 1;
      findingsTotal.value = 0;
      findingsHasNext.value = false;
      return;
    }
    if (!selectedTaskId.value || !tasks.value.some((task) => task.id === selectedTaskId.value)) selectedTaskId.value = tasks.value[0].id;
    if (selectedTaskId.value) {
      if (selectedTask.value) await refreshSelectedTaskSummary();
      else await selectTask(selectedTaskId.value, false);
    }
  } catch (error) {
    showToast('扫描任务加载失败', errorMessage(error), 'error');
  }
}

async function selectTask(taskId: number, showError = true) {
  const requestId = ++taskSelectionRequest;
  selectedTaskId.value = taskId;
  findings.value = [];
  findingsPage.value = 1;
  findingsTotal.value = 0;
  findingsHasNext.value = false;
  targetResultFilter.value = '';
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

async function reloadFindings() {
  if (!selectedTaskId.value) return;
  findings.value = [];
  findingsPage.value = 1;
  await loadFindings(selectedTaskId.value, 1, true);
}

async function loadFindings(taskId = selectedTaskId.value, page = findingsPage.value + 1, replace = false, requestId = taskSelectionRequest) {
  if (!taskId || isLoadingFindings.value) return;
  isLoadingFindings.value = true;
  try {
    const payload = await listSecurityScanFindings(taskId, {
      page,
      pageSize: 50,
      severity: severityFilter.value,
      category: categoryFilter.value,
      hostId: targetResultFilter.value,
      keyword: findingKeyword.value.trim(),
    });
    if (requestId !== taskSelectionRequest || selectedTaskId.value !== taskId) return;
    findings.value = replace ? payload.results : [...findings.value, ...payload.results];
    findingsPage.value = payload.page;
    findingsTotal.value = payload.total;
    findingsHasNext.value = payload.hasNext;
  } catch (error) {
    if (requestId !== taskSelectionRequest || selectedTaskId.value !== taskId) return;
    if (replace) findings.value = [];
    showToast('风险明细加载失败', errorMessage(error), 'error');
  } finally {
    if (requestId === taskSelectionRequest && selectedTaskId.value === taskId) isLoadingFindings.value = false;
  }
}

function toggleTarget(targetId: number, checked: boolean) {
  const next = new Set(selectedTargetIds.value);
  if (checked) next.add(targetId);
  else next.delete(targetId);
  selectedTargetIds.value = next;
}

function toggleAllVisibleTargets(checked: boolean) {
  const next = new Set(selectedTargetIds.value);
  for (const target of filteredTargets.value) {
    if (checked) next.add(target.id);
    else next.delete(target.id);
  }
  selectedTargetIds.value = next;
}

async function startScan() {
  if (!canStartScan.value) return;
  isCreating.value = true;
  try {
    const task = await createSecurityScanTask({
      targetIds: [...selectedTargetIds.value],
      portsInput: portsInput.value,
      name: taskName.value.trim() || undefined,
      scanModules: { baseline: scanBaseline.value, ports: scanPorts.value, cve: scanCve.value },
    });
    isDrawerOpen.value = false;
    selectedTargetIds.value = new Set();
    taskName.value = '';
    await Promise.all([loadSummary(), loadTasks()]);
    await selectTask(task.id);
    showToast('扫描任务已创建', '后台正在执行安全巡检。', 'success');
  } catch (error) {
    showToast('扫描任务创建失败', errorMessage(error), 'error');
  } finally {
    isCreating.value = false;
  }
}

async function cancelSelectedTask() {
  if (!selectedTaskId.value || isControlBusy.value) return;
  isControlBusy.value = true;
  try {
    await cancelSecurityScanTask(selectedTaskId.value);
    await Promise.all([loadSummary(), loadTasks(), refreshSelectedTaskSummary()]);
    showToast('已请求取消', '当前主机扫描结束后会停止后续任务。', 'success');
  } catch (error) {
    showToast('取消任务失败', errorMessage(error), 'error');
  } finally {
    isControlBusy.value = false;
  }
}

async function retryFailedTargets() {
  if (!selectedTaskId.value || isControlBusy.value) return;
  isControlBusy.value = true;
  try {
    await retryFailedSecurityScanTargets(selectedTaskId.value);
    await Promise.all([loadSummary(), loadTasks(), refreshSelectedTaskSummary(), reloadFindings()]);
    showToast('失败主机已重新排队', '后台正在重新扫描失败目标。', 'success');
  } catch (error) {
    showToast('重试失败主机失败', errorMessage(error), 'error');
  } finally {
    isControlBusy.value = false;
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
      await Promise.all([loadSummary(), loadTasks()]);
      showToast('扫描任务已删除', '历史记录和扫描结果已移除。', 'success');
    } catch (error) {
      showToast('删除失败', errorMessage(error), 'error');
    }
  };
  if (requestConfirm) requestConfirm('删除扫描任务', '删除后将同时移除该任务下的主机结果和风险明细。', '删除', run);
  else void run();
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (hasRunningTask.value) {
      await Promise.all([loadSummary(), loadTasks()]);
      if (selectedTaskId.value) await reloadFindings();
    }
  }, 5000);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function riskTotal(counts: SecurityScanTask['riskCounts']) {
  return counts.critical + counts.high + counts.medium + counts.low + counts.info;
}

function uniqueStrings(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

function severityRank(severity: SecurityScanSeverity) {
  const index = severityOrder.indexOf(severity);
  return index === -1 ? severityOrder.length : index;
}

function higherSeverity(left: SecurityScanSeverity, right: SecurityScanSeverity) {
  return severityRank(left) <= severityRank(right) ? left : right;
}

function statusLabel(status: SecurityScanStatus | SecurityScanTargetResult['status']) {
  return statusLabels[status] ?? status;
}

function formatTime(value: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function severityClass(severity: SecurityScanFinding['severity']) {
  return `severity-${severity}`;
}

function categoryLabel(category: string) {
  return categoryLabels[category] ?? category;
}

function detectionType(finding: SecurityScanFinding) {
  if (finding.category === 'baseline') return '基线检查';
  if (finding.category === 'port') return '端口风险扫描';
  if (finding.category === 'cve') return 'CVE 检查';
  return `${categoryLabel(finding.category)}扫描`;
}

function optionalFindingField(finding: SecurityScanFinding, field: 'description' | 'evidence') {
  const extended = finding as SecurityScanFinding & Partial<Record<'description' | 'evidence', string>>;
  return extended[field] || '';
}

function findingDescription(finding: SecurityScanFinding) {
  return optionalFindingField(finding, 'description') || finding.cwe || finding.source || '-';
}

function findingEvidence(finding: SecurityScanFinding) {
  const explicitEvidence = optionalFindingField(finding, 'evidence');
  if (explicitEvidence) return explicitEvidence;
  return [finding.cveId, finding.packageName, finding.currentVersion, finding.service, finding.port ? `${finding.targetIp}:${finding.port}` : ''].filter(Boolean).join(' / ') || '-';
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
</script>

<template>
  <section class="security-scan-page">
    <header class="security-workbench-header">
      <div>
        <h2>安全扫描</h2>
        <p>面向已验证 Linux SSH 主机的只读风险巡检报告。</p>
      </div>
      <div class="security-workbench-actions">
        <button v-if="canUsePageAction('securityScan', 'scan')" class="primary" type="button" @click="isDrawerOpen = true"><AppIcon name="scan" :size="16" />新建巡检</button>
        <button v-if="canUsePageAction('securityScan', 'refresh')" type="button" :disabled="isLoading" @click="refreshAll"><AppIcon name="refresh" :size="16" />刷新</button>
      </div>
    </header>

    <section class="security-scan-filters finding-toolbar">
      <label>
        <span>报告任务</span>
        <select :value="selectedTaskId ?? ''" :disabled="!tasks.length" @change="selectTask(Number(($event.target as HTMLSelectElement).value))">
          <option v-if="!tasks.length" value="">暂无任务</option>
          <option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.name }}</option>
        </select>
      </label>
      <input v-model="keyword" type="search" placeholder="搜索任务" @keyup.enter="loadTasks" />
      <select v-model="statusFilter" @change="loadTasks">
        <option value="">全部状态</option>
        <option value="queued">排队中</option>
        <option value="running">扫描中</option>
        <option value="completed">已完成</option>
        <option value="failed">失败</option>
        <option value="canceled">已取消</option>
      </select>
      <input v-model="findingKeyword" type="search" placeholder="搜索风险 / CVE / 主机" @keyup.enter="reloadFindings" />
      <select v-model="severityFilter">
        <option value="">全部级别</option>
        <option value="critical">严重</option>
        <option value="high">高危</option>
        <option value="medium">中危</option>
        <option value="low">低危</option>
        <option value="info">提示</option>
      </select>
      <select v-model="categoryFilter">
        <option value="">全部分类</option>
        <option value="baseline">基线</option>
        <option value="port">端口</option>
        <option value="cve">CVE</option>
      </select>
      <select v-model="targetResultFilter">
        <option value="">全部主机</option>
        <option v-for="target in targetResults" :key="target.id" :value="String(target.id)">{{ target.hostName }}</option>
      </select>
      <button type="button" :disabled="isLoadingFindings || !selectedTask" @click="reloadFindings"><AppIcon name="search" :size="15" />筛选</button>
      <span>{{ taskOptionsLabel }} · 可扫描目标 {{ targets.length }} 台</span>
    </section>

    <main class="security-report-pane">
      <template v-if="selectedTask">
        <header class="security-report-head">
          <div>
            <h3>{{ selectedTask.name }}</h3>
            <p>{{ selectedTask.createdBy }} · {{ selectedTask.targetCount }} 台目标 · 风险 {{ selectedTaskRiskTotal }} 项</p>
          </div>
          <div class="security-report-actions">
            <button v-if="canUsePageAction('securityScan', 'scan')" type="button" :disabled="!selectedTaskCanCancel || isControlBusy" @click="cancelSelectedTask">取消</button>
            <button v-if="canUsePageAction('securityScan', 'scan')" type="button" :disabled="!failedTargetsInSelectedTask || isControlBusy" @click="retryFailedTargets">重试失败</button>
            <button v-if="canUsePageAction('securityScan', 'export')" type="button" @click="exportTask('csv')"><AppIcon name="download" :size="15" />CSV</button>
            <button v-if="canUsePageAction('securityScan', 'export')" type="button" @click="exportTask('json')"><AppIcon name="download" :size="15" />JSON</button>
            <button v-if="canUsePageAction('securityScan', 'delete')" class="danger" type="button" @click="removeSelectedTask"><AppIcon name="trash" :size="15" />删除</button>
          </div>
        </header>

        <nav class="report-tabs" aria-label="检查结果分类">
          <button
            v-for="tab in reportTabs"
            :key="tab.key"
            type="button"
            :class="{ active: activeReportTab === tab.key }"
            :aria-current="activeReportTab === tab.key ? 'page' : undefined"
            @click="activeReportTab = tab.key"
          >
            <span>{{ tab.label }}</span>
            <em>{{ tab.count }}</em>
          </button>
        </nav>

        <section v-if="activeReportTab === 'overview'" class="security-report-section">
          <h3>综述</h3>
          <div class="report-table-scroll">
            <table class="report-table overview-table">
              <tbody>
                <tr>
                  <th>报告名称</th>
                  <td colspan="3">{{ selectedTask.name }}</td>
                  <th>报告生成时间</th>
                  <td>{{ selectedTaskReportTime }}</td>
                </tr>
                <tr>
                  <th>用户名称</th>
                  <td>{{ selectedTask.createdBy }}</td>
                  <th>任务状态</th>
                  <td><em class="scan-status" :class="`status-${selectedTask.status}`">{{ statusLabel(selectedTask.status) }}</em></td>
                  <th>扫描模块</th>
                  <td>{{ selectedTaskModulesText }}</td>
                </tr>
                <tr>
                  <th>目标资产</th>
                  <td>{{ selectedTask.targetCount }}</td>
                  <th>已完成</th>
                  <td>{{ selectedTask.completedCount }}</td>
                  <th>失败主机</th>
                  <td>{{ selectedTask.failedCount }}</td>
                </tr>
                <tr>
                  <th>风险总数</th>
                  <td>{{ selectedTaskRiskTotal }}</td>
                  <th>严重</th>
                  <td><b class="severity-critical">{{ selectedTask.riskCounts.critical }}</b></td>
                  <th>高危</th>
                  <td><b class="severity-high">{{ selectedTask.riskCounts.high }}</b></td>
                </tr>
                <tr>
                  <th>中危</th>
                  <td><b class="severity-medium">{{ selectedTask.riskCounts.medium }}</b></td>
                  <th>低危</th>
                  <td><b class="severity-low">{{ selectedTask.riskCounts.low }}</b></td>
                  <th>提示</th>
                  <td><b class="severity-info">{{ selectedTask.riskCounts.info }}</b></td>
                </tr>
                <tr>
                  <th>漏洞源</th>
                  <td colspan="3">{{ sourceStatusText }}</td>
                  <th>全局运行中任务</th>
                  <td>{{ summary.taskCounts.running }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-else-if="activeReportTab === 'assets'" class="security-report-section">
          <h3>资产风险统计</h3>
          <div class="report-table-scroll">
            <table class="report-table asset-report-table">
              <thead>
                <tr>
                  <th>序号</th>
                  <th>IP/URL地址</th>
                  <th>资产名称</th>
                  <th>业务组</th>
                  <th>责任人</th>
                  <th>是否核心</th>
                  <th>风险总数</th>
                  <th>风险类型</th>
                  <th>严重</th>
                  <th>高危</th>
                  <th>中危</th>
                  <th>低危</th>
                  <th>提示</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in assetRiskRows" :key="row.id">
                  <td>{{ row.index }}</td>
                  <td>{{ row.hostIp }}</td>
                  <td>{{ row.hostName }}</td>
                  <td>{{ row.businessGroup }}</td>
                  <td>{{ row.owner }}</td>
                  <td>{{ row.coreAsset }}</td>
                  <td>{{ row.riskTotal }}</td>
                  <td>{{ row.riskType }}</td>
                  <td>{{ row.critical }}</td>
                  <td>{{ row.high }}</td>
                  <td>{{ row.medium }}</td>
                  <td>{{ row.low }}</td>
                  <td>{{ row.info }}</td>
                </tr>
                <tr v-if="!assetRiskRows.length">
                  <td colspan="13">暂无资产风险统计。</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-else-if="activeReportTab === 'impact'" class="security-report-section">
          <h3>漏洞影响统计</h3>
          <div class="report-table-scroll">
            <table class="report-table impact-report-table">
              <thead>
                <tr>
                  <th>序号</th>
                  <th>漏洞名称</th>
                  <th>风险等级</th>
                  <th>风险类型</th>
                  <th>影响资产</th>
                  <th>影响资产数量</th>
                  <th>出现次数</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in impactRows" :key="row.key">
                  <td>{{ row.index }}</td>
                  <td class="report-text-cell">{{ row.title }}</td>
                  <td><b :class="severityClass(row.severity)">{{ severityLabels[row.severity] }}</b></td>
                  <td>{{ row.riskType }}</td>
                  <td class="report-text-cell">{{ row.affectedAssets || '-' }}</td>
                  <td>{{ row.affectedAssetCount }}</td>
                  <td>{{ row.occurrences }}</td>
                </tr>
                <tr v-if="!impactRows.length">
                  <td colspan="7">当前筛选条件下没有漏洞影响统计。</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-else-if="activeReportTab === 'details'" class="security-report-section">
          <h3>漏洞详情</h3>
          <div class="report-table-scroll">
            <table class="report-table finding-detail-table">
              <thead>
                <tr>
                  <th>序号</th>
                  <th>风险等级</th>
                  <th>主机/域名</th>
                  <th>风险端口</th>
                  <th>漏洞名称</th>
                  <th>检测类型</th>
                  <th>漏洞类型</th>
                  <th>CVE编号</th>
                  <th>风险描述</th>
                  <th>风险影响</th>
                  <th>解决方案</th>
                  <th>风险举证</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(finding, index) in findings" :key="finding.id">
                  <td>{{ index + 1 }}</td>
                  <td><b :class="severityClass(finding.severity)">{{ severityLabels[finding.severity] }}</b></td>
                  <td>{{ finding.targetIp || finding.targetName }}</td>
                  <td>{{ finding.port || '-' }}</td>
                  <td class="report-text-cell">{{ finding.title }}</td>
                  <td>{{ detectionType(finding) }}</td>
                  <td>{{ categoryLabel(finding.category) }}</td>
                  <td>{{ finding.cveId || '-' }}</td>
                  <td class="report-text-cell">{{ findingDescription(finding) }}</td>
                  <td class="report-text-cell">{{ finding.cwe || finding.cvss || '-' }}</td>
                  <td class="report-text-cell">{{ finding.recommendation || '-' }}</td>
                  <td class="report-text-cell">{{ findingEvidence(finding) }}</td>
                </tr>
                <tr v-if="!findings.length">
                  <td colspan="12">当前筛选条件下没有漏洞详情。</td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="findingsHasNext" class="finding-load-more" type="button" :disabled="isLoadingFindings" @click="loadFindings()">
            <AppIcon name="chevronsRight" :size="16" />{{ isLoadingFindings ? '加载中...' : '加载更多' }}
          </button>
        </section>
      </template>
      <div v-else class="security-empty">暂无扫描任务，请新建巡检后查看报告。</div>
    </main>

    <div v-if="isDrawerOpen" class="security-drawer-backdrop">
      <section class="security-drawer">
        <header>
          <div>
            <h3>新建安全巡检</h3>
            <p>扫描过程只执行只读命令，不会修改目标主机状态。</p>
          </div>
          <button type="button" aria-label="关闭" @click="isDrawerOpen = false"><AppIcon name="x" :size="16" /></button>
        </header>
        <div class="scan-form-grid">
          <label>
            <span>任务名称</span>
            <input v-model="taskName" maxlength="180" placeholder="留空自动生成" />
          </label>
          <label>
            <span>端口范围</span>
            <textarea v-model="portsInput" rows="3"></textarea>
          </label>
        </div>
        <div class="scan-module-options">
          <label><input v-model="scanBaseline" type="checkbox" />基线检查</label>
          <label><input v-model="scanPorts" type="checkbox" />端口风险</label>
          <label :class="{ disabled: !summary.vulnerabilitySource.onlineCveEnabled }">
            <input v-model="scanCve" type="checkbox" :disabled="!summary.vulnerabilitySource.onlineCveEnabled" />CVE 检查
          </label>
          <span v-if="!summary.vulnerabilitySource.onlineCveEnabled">在线 CVE 默认关闭，可在系统设置中开启。</span>
        </div>
        <div class="target-picker-head">
          <label>
            <input type="checkbox" :checked="filteredTargets.length > 0 && filteredTargets.every((target) => selectedTargetIds.has(target.id))" @change="toggleAllVisibleTargets(($event.target as HTMLInputElement).checked)" />
            全选当前列表
          </label>
          <input v-model="targetKeyword" type="search" placeholder="搜索主机 / IP / 分组" />
          <span>已选 {{ selectedTargets.length }} / {{ targets.length }}</span>
        </div>
        <div class="target-picker-list">
          <label v-for="target in filteredTargets" :key="target.id">
            <input type="checkbox" :checked="selectedTargetIds.has(target.id)" @change="toggleTarget(target.id, ($event.target as HTMLInputElement).checked)" />
            <strong>{{ target.name }}</strong>
            <span>{{ target.privateIp }} · {{ target.os }} · {{ target.groupName }}</span>
          </label>
          <div v-if="!filteredTargets.length" class="security-empty">暂无可扫描 Linux SSH 主机。</div>
        </div>
        <footer>
          <button type="button" @click="isDrawerOpen = false">取消</button>
          <button class="primary" type="button" :disabled="!canStartScan" @click="startScan">{{ isCreating ? '创建中...' : '开始扫描' }}</button>
        </footer>
      </section>
    </div>
  </section>
</template>
