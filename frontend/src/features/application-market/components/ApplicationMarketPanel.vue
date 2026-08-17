<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { useAppContext } from '@app/context';
import AppIcon from '@shared/components/AppIcon.vue';
import { errorMessage } from '@shared/utils/errors';
import {
  cancelApplicationMarketTask,
  createApplicationMarketTask,
  getApplicationMarketApp,
  listApplicationMarketCatalog,
  listApplicationMarketSources,
  listApplicationMarketTargets,
  listApplicationMarketTasks,
  previewApplicationMarketAction,
  syncApplicationMarketSources,
} from '../api/applicationMarket';
import type {
  ApplicationMarketAction,
  ApplicationMarketApp,
  ApplicationMarketConfigField,
  ApplicationMarketPlan,
  ApplicationMarketSource,
  ApplicationMarketTarget,
  ApplicationMarketTask,
} from '../types';

const actionLabels: Record<ApplicationMarketAction, string> = {
  install: '安装',
  update: '更新',
  uninstall: '卸载',
  start: '启动',
  stop: '停止',
  restart: '重启',
};
const statusLabels: Record<string, string> = {
  not_installed: '未安装',
  unknown: '待核对',
  queued: '排队中',
  running: '运行中',
  stopped: '已停止',
  success: '成功',
  failed: '失败',
  canceled: '已取消',
};
const sourceSegments = [
  { key: 'all', label: '全部来源' },
  { key: 'builtin', label: '脚本内置' },
  { key: 'thirdparty', label: '第三方' },
];
const statusSegments = [
  { key: 'installed', label: '已安装' },
  { key: 'all', label: '全部应用' },
  { key: 'running', label: '运行中' },
  { key: 'adapted', label: '可直接安装' },
];

const { activeTool, canUsePageAction, showToast, requestConfirm } = useAppContext();

const apps = ref<ApplicationMarketApp[]>([]);
const categories = ref<string[]>([]);
const targets = ref<ApplicationMarketTarget[]>([]);
const sourceList = ref<ApplicationMarketSource[]>([]);
const tasks = ref<ApplicationMarketTask[]>([]);
const totalTasks = ref(0);
const selectedTargetId = ref('local');
const searchKeyword = ref('');
const categoryFilter = ref('all');
const sourceFilter = ref('');
const installStatusFilter = ref('installed');
const selectedApp = ref<ApplicationMarketApp | null>(null);
const configDraft = ref<Record<string, unknown>>({});
const previewPlan = ref<ApplicationMarketPlan | null>(null);
const confirmInstallModal = ref(false);
const taskDetailsOpen = ref(false);
const isLoading = ref(false);
const isPreviewing = ref(false);
const isSubmitting = ref(false);
const isSyncingSources = ref(false);
const taskPage = ref(1);
const taskPageSize = ref(8);
const taskStatusFilter = ref('');
const taskKeyword = ref('');
let pollTimer: number | null = null;
let hadRunningTask = false;
let pollInFlight = false;

const canView = computed(() => canUsePageAction('applicationMarket', 'view'));
const canRefresh = computed(() => canUsePageAction('applicationMarket', 'refresh'));
const canManageSources = computed(() => canUsePageAction('applicationMarket', 'manage_sources'));
const canViewTasks = computed(() => canUsePageAction('applicationMarket', 'view_tasks'));
const canInstall = computed(() => canUsePageAction('applicationMarket', 'install'));
const canUpdate = computed(() => canUsePageAction('applicationMarket', 'update'));
const canUninstall = computed(() => canUsePageAction('applicationMarket', 'uninstall'));
const canStart = computed(() => canUsePageAction('applicationMarket', 'start'));
const canStop = computed(() => canUsePageAction('applicationMarket', 'stop'));
const canRestart = computed(() => canUsePageAction('applicationMarket', 'restart'));
const targetSelector = computed(() => targets.value.find((target) => target.id === selectedTargetId.value) ?? targets.value[0] ?? null);
const totalApps = computed(() => apps.value.length);
const installedApps = computed(() => apps.value.filter((app) => app.installed).length);
const runningApps = computed(() => apps.value.filter((app) => app.status === 'running').length);
const adaptedApps = computed(() => apps.value.filter((app) => app.capabilities.includes('install') || app.capabilities.includes('update')).length);
const runningTasks = computed(() => tasks.value.filter((task) => task.status === 'queued' || task.status === 'running'));
const activeTask = computed(() => runningTasks.value[0] ?? tasks.value[0] ?? null);
const selectedTargetUnsupported = computed(() => Boolean(targetSelector.value && !targetSelector.value.supported));
const sourceSummary = computed(() => {
  if (!sourceList.value.length) return '内置目录';
  const enabled = sourceList.value.filter((source) => source.enabled).length;
  return `${enabled}/${sourceList.value.length} 个远程源启用`;
});
const capabilityStrip = computed(() => {
  const target = targetSelector.value;
  if (!target) return [];
  return [
    { key: 'os', label: '系统', value: target.os || 'unknown', ok: target.os !== 'windows' },
    { key: 'support', label: '安装能力', value: target.supported ? '支持' : target.reason || '不支持', ok: target.supported },
    { key: 'docker', label: 'Docker', value: target.dockerVersion || (target.docker === false ? '未检测到' : '预览时检测'), ok: target.docker !== false },
    { key: 'compose', label: 'Compose', value: target.composeVersion || (target.compose === false ? '未检测到' : '预览时检测'), ok: target.compose !== false },
  ];
});
const configSchema = computed(() => selectedApp.value?.configSchema ?? []);
const categoryCounts = computed(() => {
  const counts: Record<string, number> = { all: apps.value.length };
  apps.value.forEach((app) => {
    counts[app.category] = (counts[app.category] || 0) + 1;
  });
  return counts;
});
const sortedApps = computed(() =>
  [...apps.value].sort((left, right) => {
    if (Boolean(left.installed) !== Boolean(right.installed)) return left.installed ? -1 : 1;
    return left.name.localeCompare(right.name);
  }),
);
const filteredApps = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  return sortedApps.value.filter((app) => {
    if (keyword && ![app.name, app.description, app.appId, app.icon].join('\u0000').toLowerCase().includes(keyword)) return false;
    if (categoryFilter.value && categoryFilter.value !== 'all' && app.category !== categoryFilter.value) return false;
    if (sourceFilter.value === 'builtin' && app.source !== 'builtin') return false;
    if (sourceFilter.value === 'thirdparty' && app.source === 'builtin') return false;
    if (installStatusFilter.value === 'installed' && !app.installed) return false;
    if (installStatusFilter.value === 'running' && app.status !== 'running') return false;
    if (installStatusFilter.value === 'adapted' && !app.capabilities.includes('install') && !app.capabilities.includes('update')) return false;
    return true;
  });
});
const selectedAppActions = computed(() => selectedApp.value?.capabilities ?? []);

onMounted(async () => {
  await refreshAll();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});

watch(
  () => activeTool.value,
  (tool) => {
    if (tool === 'applicationMarket') void refreshAll();
  },
);

watch(selectedTargetId, () => {
  void loadCatalog();
});

watch(selectedApp, (app) => {
  previewPlan.value = null;
  confirmInstallModal.value = false;
  configDraft.value = app ? createDefaultConfig(app.configSchema) : {};
});

async function refreshAll() {
  if (!canView.value && !canRefresh.value) return;
  isLoading.value = true;
  try {
    await Promise.all([loadTargets(), loadCatalog(), loadTasks(), loadSources()]);
  } finally {
    isLoading.value = false;
  }
}

async function loadTargets() {
  try {
    const payload = await listApplicationMarketTargets();
    targets.value = payload.targets;
    if (!targets.value.some((target) => target.id === selectedTargetId.value)) selectedTargetId.value = targets.value[0]?.id ?? 'local';
  } catch (error) {
    showToast('目标主机加载失败', errorMessage(error), 'error');
  }
}

async function loadCatalog() {
  if (!canView.value && !canRefresh.value) return;
  try {
    const payload = await listApplicationMarketCatalog({ target: selectedTargetId.value });
    apps.value = payload.apps;
    categories.value = payload.categories;
    if (selectedApp.value) selectedApp.value = apps.value.find((app) => app.appId === selectedApp.value?.appId) ?? selectedApp.value;
  } catch (error) {
    showToast('应用目录加载失败', errorMessage(error), 'error');
  }
}

async function loadSources() {
  if (!canManageSources.value) return;
  try {
    const payload = await listApplicationMarketSources();
    sourceList.value = payload.sources;
  } catch {
    sourceList.value = [];
  }
}

async function loadTasks() {
  if (!canViewTasks.value || pollInFlight) return;
  pollInFlight = true;
  try {
    const payload = await listApplicationMarketTasks({
      page: taskPage.value,
      pageSize: taskPageSize.value,
      status: taskStatusFilter.value,
      keyword: taskKeyword.value.trim(),
    });
    tasks.value = payload.results;
    totalTasks.value = payload.total;
    const hasRunning = runningTasks.value.length > 0;
    if (hadRunningTask && !hasRunning) await loadCatalog();
    hadRunningTask = hasRunning;
  } finally {
    pollInFlight = false;
  }
}

async function syncSources() {
  if (!canManageSources.value || isSyncingSources.value) return;
  isSyncingSources.value = true;
  try {
    await syncApplicationMarketSources();
    await Promise.all([loadSources(), loadCatalog()]);
    showToast('同步完成', '应用市场目录已刷新', 'success');
  } catch (error) {
    showToast('同步失败', errorMessage(error), 'error');
  } finally {
    isSyncingSources.value = false;
  }
}

async function openApp(app: ApplicationMarketApp) {
  try {
    selectedApp.value = await getApplicationMarketApp(app.appId);
  } catch {
    selectedApp.value = app;
  }
}

function closeAppDetail() {
  selectedApp.value = null;
}

function createDefaultConfig(schema: ApplicationMarketConfigField[]) {
  return schema.reduce<Record<string, unknown>>((draft, field) => {
    draft[field.key] = field.type === 'boolean' ? Boolean(field.default) : field.default ?? '';
    return draft;
  }, {});
}

async function openAndStart(app: ApplicationMarketApp, action: ApplicationMarketAction) {
  await openApp(app);
  await startAction(action);
}

async function startAction(action: ApplicationMarketAction) {
  if (!selectedApp.value || isPreviewing.value) return;
  isPreviewing.value = true;
  previewPlan.value = null;
  try {
    previewPlan.value = await previewApplicationMarketAction({
      appId: selectedApp.value.appId,
      target: selectedTargetId.value,
      action,
      config: configDraft.value,
    });
    confirmInstallModal.value = true;
  } catch (error) {
    showToast('生成预览失败', errorMessage(error), 'error');
  } finally {
    isPreviewing.value = false;
  }
}

function confirmPreviewTask() {
  if (!previewPlan.value) return;
  const actionText = actionLabels[previewPlan.value.action];
  requestConfirm(
    `确认${actionText}应用`,
    `目标 ${targetSelector.value?.name ?? previewPlan.value.target} 将执行 ${previewPlan.value.appName} 的${actionText}任务。`,
    `确认${actionText}`,
    submitConfirmedTask,
  );
}

async function submitConfirmedTask() {
  if (!previewPlan.value || isSubmitting.value) return;
  isSubmitting.value = true;
  try {
    const task = await createApplicationMarketTask({
      appId: previewPlan.value.appId,
      target: previewPlan.value.target,
      action: previewPlan.value.action,
      config: configDraft.value,
      planDigest: previewPlan.value.planDigest,
    });
    confirmInstallModal.value = false;
    previewPlan.value = null;
    taskDetailsOpen.value = true;
    showToast('任务已提交', `${task.appName} 正在后台执行`, 'success');
    await loadTasks();
    startPolling();
  } catch (error) {
    showToast('任务提交失败', errorMessage(error), 'error');
  } finally {
    isSubmitting.value = false;
  }
}

async function cancelTask(task: ApplicationMarketTask) {
  if (!['queued', 'running'].includes(task.status)) return;
  requestConfirm('取消应用任务', `取消 ${task.appName} 的 ${actionLabels[task.action]} 任务。`, '取消任务', async () => {
    await cancelApplicationMarketTask(task.id);
    await loadTasks();
  });
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (activeTool.value !== 'applicationMarket' || !canViewTasks.value) return;
    if (runningTasks.value.length || hadRunningTask) await loadTasks();
  }, 2000);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function canRunAction(action: ApplicationMarketAction) {
  if (selectedTargetUnsupported.value || isPreviewing.value) return false;
  if (action === 'install') return canInstall.value;
  if (action === 'update') return canUpdate.value;
  if (action === 'uninstall') return canUninstall.value;
  if (action === 'start') return canStart.value;
  if (action === 'stop') return canStop.value;
  if (action === 'restart') return canRestart.value;
  return false;
}

function fieldOptions(field: ApplicationMarketConfigField) {
  return (field.options ?? []).map((option) => (typeof option === 'string' ? { label: option, value: option } : option));
}

function appInitials(app: ApplicationMarketApp) {
  return (app.icon || app.name).slice(0, 2).toUpperCase();
}

function formatBytes(value?: number | null) {
  if (!value) return '未知';
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${value} B`;
}

function formatDate(value: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}
</script>

<template>
  <section class="application-market-page app-market">
    <header class="market-page-title">
      <div>
        <h2><AppIcon name="server" :size="20" />应用市场</h2>
        <p>发现、安装和管理服务器应用；所有安装与变更都先预览，再由管理员确认执行。</p>
      </div>
      <label class="market-select-field targetSelector">
        <span>目标主机</span>
        <select v-model="selectedTargetId">
          <option v-for="target in targets" :key="target.id" :value="target.id">{{ target.name }} · {{ target.ip }}</option>
        </select>
      </label>
    </header>

    <section class="market-hero" aria-label="应用概况与操作">
      <div class="market-stats">
        <div><strong>{{ totalApps }}</strong><span>全部应用</span></div>
        <div><strong>{{ installedApps }}</strong><span>已安装</span></div>
        <div><strong>{{ runningApps }}</strong><span>运行中</span></div>
        <div><strong>{{ adaptedApps }}</strong><span>可直接安装</span></div>
      </div>
      <div class="market-hero__actions">
        <span class="market-source-mode">{{ sourceSummary }}</span>
        <button type="button" :disabled="isLoading" @click="refreshAll"><AppIcon name="refresh" :size="15" />刷新状态</button>
        <button v-if="canManageSources" type="button" :disabled="isSyncingSources" @click="syncSources">
          <AppIcon name="download" :size="15" />同步目录
        </button>
      </div>
    </section>

    <section class="capabilityStrip market-capability-strip">
      <article v-for="item in capabilityStrip" :key="item.key" :class="{ ok: item.ok, warn: !item.ok }">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
      <article><span>磁盘剩余</span><strong>{{ formatBytes(targetSelector?.diskFree) }}</strong></article>
      <article><span>目录来源</span><strong>{{ sourceSummary }}</strong></article>
    </section>

    <section v-if="activeTask" class="app-job-banner" :class="`is-${activeTask.status}`">
      <span class="app-job-banner__icon">
        <AppIcon :name="runningTasks.length ? 'refresh' : activeTask.status === 'success' ? 'circleCheck' : 'circleHelp'" :size="20" />
      </span>
      <div class="app-job-banner__body">
        <span><strong>{{ activeTask.appName }}</strong><em>{{ statusLabels[activeTask.status] || activeTask.status }}</em></span>
        <small>{{ actionLabels[activeTask.action] }} · {{ activeTask.targetKey }} · {{ activeTask.error || activeTask.logOutput || '后台任务已提交' }}</small>
        <i class="app-job-banner__progress"><b :style="{ width: runningTasks.length ? '45%' : '100%' }" /></i>
      </div>
      <strong class="app-job-banner__percent">{{ runningTasks.length ? '执行中' : statusLabels[activeTask.status] || activeTask.status }}</strong>
      <div class="app-job-banner__actions">
        <button v-if="['queued', 'running'].includes(activeTask.status)" type="button" class="danger" @click="cancelTask(activeTask)">停止任务</button>
        <button type="button" @click="taskDetailsOpen = true">查看进度 <AppIcon name="chevronRight" :size="14" /></button>
      </div>
    </section>

    <section class="market-toolbar">
      <label class="market-search">
        <AppIcon name="search" :size="18" />
        <input v-model="searchKeyword" type="search" placeholder="搜索应用名称、功能或容器..." />
      </label>
      <div class="market-segment" aria-label="来源筛选">
        <button
          v-for="item in sourceSegments"
          :key="item.key"
          type="button"
          :class="{ 'is-active': sourceFilter === item.key || (!sourceFilter && item.key === 'all') }"
          @click="sourceFilter = item.key === 'all' ? '' : item.key"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="market-segment" aria-label="状态筛选">
        <button
          v-for="item in statusSegments"
          :key="item.key"
          type="button"
          :class="{ 'is-active': installStatusFilter === item.key }"
          @click="installStatusFilter = item.key"
        >
          {{ item.label }}
        </button>
      </div>
    </section>

    <nav class="market-categories" aria-label="应用分类">
      <button :class="{ 'is-active': !categoryFilter || categoryFilter === 'all' }" type="button" @click="categoryFilter = 'all'">
        全部 <span>{{ categoryCounts.all }}</span>
      </button>
      <button v-for="category in categories" :key="category" :class="{ 'is-active': categoryFilter === category }" type="button" @click="categoryFilter = category">
        {{ category }} <span>{{ categoryCounts[category] || 0 }}</span>
      </button>
    </nav>

    <section v-if="filteredApps.length" class="app-grid market-app-grid" aria-live="polite">
      <article v-for="app in filteredApps" :key="app.appId" class="app-card market-app-card" :class="{ 'is-installed': app.installed, active: selectedApp?.appId === app.appId }">
        <button class="app-card__main" type="button" @click="openApp(app)">
          <span class="app-card__icon market-app-icon">{{ appInitials(app) }}</span>
          <span class="app-card__body">
            <span class="app-card__title">
              <strong>{{ app.name }}</strong>
              <em v-if="app.installed" class="status-pill">{{ statusLabels[app.status || 'unknown'] || app.status }}</em>
            </span>
            <span class="app-card__meta market-app-meta">
              <em>{{ app.category }}</em>
              <em>{{ app.source === 'builtin' ? '内置' : '第三方' }}</em>
              <em v-if="app.capabilities.includes('install') || app.capabilities.includes('update')" class="is-adapted">
                <AppIcon name="shield" :size="12" />可直接安装
              </em>
            </span>
            <span class="app-card__description">{{ app.description }}</span>
          </span>
        </button>
        <footer class="app-card__footer">
          <span class="app-card__runtime">
            <span v-if="app.installed" :class="['runtime-dot', `is-${app.status || 'unknown'}`]" />
            {{ app.version }} · {{ app.appId }}
          </span>
          <button v-if="!app.installed && app.capabilities.includes('install')" class="primary" type="button" @click="openAndStart(app, 'install')">
            <AppIcon name="download" :size="14" />安装
          </button>
          <button v-else type="button" @click="openApp(app)">{{ app.installed ? '管理' : '了解详情' }}</button>
        </footer>
      </article>
    </section>

    <p v-else class="market-empty">没有符合条件的应用。尝试清除搜索词或切换分类与状态筛选。</p>

    <section v-if="installStatusFilter === 'installed'" class="install-more-card">
      <span><AppIcon name="globe" :size="22" /></span>
      <div>
        <strong>{{ installedApps ? '还想安装更多应用？' : '还没有安装应用' }}</strong>
        <p>前往完整应用列表，选择支持后台安装的应用；安装期间可以继续使用面板。</p>
      </div>
      <button class="primary" type="button" @click="installStatusFilter = 'all'">浏览全部应用 <AppIcon name="chevronRight" :size="16" /></button>
    </section>

    <footer class="market-result">
      已显示 {{ filteredApps.length }} / {{ totalApps }} 个应用
      <span>目录来源 · {{ sourceSummary }} · 状态来源 · {{ targetSelector?.name || '目标主机' }}</span>
    </footer>

    <div v-if="selectedApp && !confirmInstallModal" class="modal-backdrop market-detail-backdrop">
      <section class="market-detail-modal" role="dialog" aria-modal="true" aria-label="应用详情">
        <header>
          <div class="app-detail-head">
            <span class="app-detail-head__icon market-app-icon large">{{ appInitials(selectedApp) }}</span>
            <div>
              <span class="app-detail-head__badges">
                <span class="source-pill">{{ selectedApp.source === 'builtin' ? '内置' : '第三方' }}</span>
                <span class="source-pill">{{ selectedApp.category }}</span>
                <span class="source-pill">{{ statusLabels[selectedApp.status || 'not_installed'] || selectedApp.status }}</span>
              </span>
              <strong>{{ selectedApp.name }}</strong>
              <small><code>{{ selectedApp.appId }} · {{ selectedApp.version }}</code></small>
            </div>
          </div>
          <button type="button" aria-label="关闭详情" @click="closeAppDetail"><AppIcon name="x" :size="16" /></button>
        </header>

        <div class="market-detail-body">
          <section v-if="selectedApp.installed" class="app-control-panel">
            <div class="app-control-panel__status">
              <div><span>运行状态</span><strong>{{ statusLabels[selectedApp.status || 'unknown'] || selectedApp.status }}</strong><small>{{ selectedApp.version }}</small></div>
              <div><span>目标主机</span><strong>{{ targetSelector?.name }}</strong><small>{{ targetSelector?.ip }}</small></div>
              <div><span>访问策略</span><strong>Compose 端口</strong><small>{{ ((selectedApp.manifest.ports as string[]) || []).join(', ') || '无端口' }}</small></div>
            </div>
            <div class="app-control-panel__actions market-action-bar">
              <button
                v-for="action in selectedAppActions.filter((item) => item !== 'install')"
                :key="action"
                type="button"
                :class="{ danger: action === 'uninstall' || action === 'stop' }"
                :disabled="!canRunAction(action)"
                @click="startAction(action)"
              >
                {{ actionLabels[action] }}
              </button>
            </div>
          </section>

          <div v-else class="app-install-state">
            <AppIcon name="circleCheck" :size="25" />
            <div>
              <strong>当前未安装</strong>
              <p>此应用会通过服务端生成的受控 Compose 计划安装，提交前会展示容器、镜像、端口和目录。</p>
            </div>
            <button class="primary" type="button" :disabled="!canRunAction('install')" @click="startAction('install')">
              <AppIcon name="download" :size="16" />开始安装
            </button>
          </div>

          <section class="market-detail-section">
            <h4>应用介绍</h4>
            <p>{{ selectedApp.description }}</p>
          </section>
          <section class="market-detail-section">
            <h4>运行要求</h4>
            <div class="market-requirements">
              <span>系统 {{ Array.isArray(selectedApp.requirements.os) ? selectedApp.requirements.os.join(', ') : 'linux' }}</span>
              <span>Docker {{ selectedApp.requirements.docker ? '需要' : '可选' }}</span>
              <span>Compose {{ selectedApp.requirements.compose ? '需要' : '可选' }}</span>
            </div>
          </section>
          <section class="market-detail-section">
            <h4>配置表单</h4>
            <div v-if="configSchema.length" class="market-config-form">
              <label v-for="field in configSchema" :key="field.key">
                <span>{{ field.label }}<small v-if="field.required">*</small></span>
                <input v-if="field.type === 'number'" v-model.number="configDraft[field.key]" type="number" :min="field.min" :max="field.max" />
                <input v-else-if="field.type === 'password'" v-model="configDraft[field.key]" type="password" autocomplete="new-password" />
                <label v-else-if="field.type === 'boolean'" class="market-checkbox">
                  <input v-model="configDraft[field.key]" type="checkbox" />
                  <span>启用</span>
                </label>
                <select v-else-if="field.type === 'select'" v-model="configDraft[field.key]">
                  <option v-for="option in fieldOptions(field)" :key="String(option.value)" :value="option.value">{{ option.label }}</option>
                </select>
                <input v-else v-model="configDraft[field.key]" type="text" />
              </label>
            </div>
            <p v-else class="market-muted">该应用无需额外配置。</p>
          </section>
          <section class="market-detail-section">
            <h4>容器信息</h4>
            <div class="market-summary-list">
              <span v-for="container in (selectedApp.manifest.containers as string[] || [])" :key="container">{{ container }}</span>
              <span v-for="port in (selectedApp.manifest.ports as string[] || [])" :key="port">{{ port }}</span>
              <span v-for="image in (selectedApp.manifest.images as string[] || [])" :key="image">{{ image }}</span>
            </div>
          </section>
        </div>
      </section>
    </div>

    <div v-if="taskDetailsOpen" class="modal-backdrop market-detail-backdrop">
      <section class="market-detail-modal market-task-detail-modal" role="dialog" aria-modal="true" aria-label="任务详情">
        <header>
          <div><h3>应用任务进度</h3><p>运行中任务每 2 秒刷新一次，完成后自动更新应用状态。</p></div>
          <button type="button" aria-label="关闭任务详情" @click="taskDetailsOpen = false"><AppIcon name="x" :size="16" /></button>
        </header>
        <div class="market-task-list">
          <article v-for="task in tasks" :key="task.id" class="market-task-row" :class="task.status">
            <div><strong>{{ task.appName }}</strong><span>{{ actionLabels[task.action] }} · {{ task.targetKey }} · {{ formatDate(task.createdAt) }}</span></div>
            <div><b>{{ statusLabels[task.status] || task.status }}</b><button v-if="['queued', 'running'].includes(task.status)" type="button" @click="cancelTask(task)">取消</button></div>
            <pre v-if="task.logOutput || task.error">{{ task.logOutput || task.error }}</pre>
          </article>
          <p v-if="!tasks.length" class="market-empty">暂无任务记录。</p>
        </div>
      </section>
    </div>

    <div v-if="confirmInstallModal && previewPlan" class="modal-backdrop market-preview-backdrop">
      <section class="market-preview-modal confirmInstallModal" role="dialog" aria-modal="true" aria-label="安装预览">
        <header>
          <div><h3>确认执行预览</h3><p>{{ previewPlan.appName }} · {{ actionLabels[previewPlan.action] }} · {{ targetSelector?.name }}</p></div>
          <button type="button" aria-label="关闭预览" @click="confirmInstallModal = false"><AppIcon name="x" :size="16" /></button>
        </header>
        <div class="market-preview-grid">
          <article><span>容器</span><strong v-for="container in previewPlan.summary.containers" :key="container">{{ container }}</strong></article>
          <article><span>镜像</span><strong v-for="image in previewPlan.summary.images" :key="image">{{ image }}</strong></article>
          <article><span>端口</span><strong v-for="port in previewPlan.summary.ports" :key="port">{{ port }}</strong></article>
          <article><span>目录</span><strong v-for="directory in previewPlan.summary.directories" :key="directory">{{ directory }}</strong></article>
        </div>
        <section class="market-preview-warning"><strong>风险提示</strong><p v-for="warning in previewPlan.warnings" :key="warning">{{ warning }}</p></section>
        <footer>
          <button type="button" @click="confirmInstallModal = false">取消</button>
          <button class="primary" type="button" :disabled="isSubmitting" @click="confirmPreviewTask">确认执行</button>
        </footer>
      </section>
    </div>
  </section>
</template>
