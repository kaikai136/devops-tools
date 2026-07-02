<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { apiGet } from '../../api';
import { useAppContext } from '../../appContext';
import { errorMessage } from '../../utils/errors';
import AppIcon from '../common/AppIcon.vue';

type ColumnKey = 'createdAt' | 'username' | 'module' | 'action' | 'target' | 'ipAddress' | 'detail' | 'userAgent';

interface OperationLog {
  id: number;
  username: string;
  module: string;
  action: string;
  target: string;
  detail: string;
  ipAddress: string | null;
  userAgent: string;
  createdAt: string;
}

interface OperationLogPage {
  results: OperationLog[];
  total: number;
  page: number;
  pageSize: number;
}

interface ColumnOption {
  key: ColumnKey;
  label: string;
  width: string;
}

const columnOptions: readonly ColumnOption[] = [
  { key: 'createdAt', label: '时间', width: 'minmax(170px, 1fr)' },
  { key: 'username', label: '操作人', width: 'minmax(100px, 0.7fr)' },
  { key: 'module', label: '模块', width: 'minmax(110px, 0.7fr)' },
  { key: 'action', label: '操作', width: 'minmax(120px, 0.8fr)' },
  { key: 'target', label: '对象', width: 'minmax(180px, 1.1fr)' },
  { key: 'ipAddress', label: 'IP', width: 'minmax(140px, 0.8fr)' },
  { key: 'detail', label: '详情', width: 'minmax(320px, 1.8fr)' },
  { key: 'userAgent', label: 'User Agent', width: 'minmax(360px, 2fr)' },
];

const { activeTool, canUsePageAction, canUseAnyPageAction } = useAppContext();

const logs = ref<OperationLog[]>([]);
const username = ref('');
const moduleName = ref('');
const actionName = ref('');
const keyword = ref('');
const operationIp = ref('');
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const isLoading = ref(false);
const message = ref('');
const columnsOpen = ref(false);
const fullscreen = ref(false);
const visibleColumns = ref<Record<ColumnKey, boolean>>({
  createdAt: true,
  username: true,
  module: true,
  action: true,
  target: true,
  ipAddress: true,
  detail: true,
  userAgent: false,
});

let filterTimer: number | undefined;

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
const pageStart = computed(() => (total.value ? (page.value - 1) * pageSize.value + 1 : 0));
const pageEnd = computed(() => Math.min(page.value * pageSize.value, total.value));
const pageNumbers = computed(() => {
  const from = Math.max(1, page.value - 2);
  const to = Math.min(totalPages.value, page.value + 2);
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
});
const visibleColumnCount = computed(() => Object.values(visibleColumns.value).filter(Boolean).length);
const allColumnsVisible = computed(() => columnOptions.every((column) => visibleColumns.value[column.key]));
const someColumnsVisible = computed(() => visibleColumnCount.value > 0);
const tableStyle = computed(() => ({
  '--login-log-columns': columnOptions
    .filter((column) => visibleColumns.value[column.key])
    .map((column) => column.width)
    .join(' '),
}));

onMounted(loadLogs);

watch([username, moduleName, actionName, keyword, operationIp], () => {
  window.clearTimeout(filterTimer);
  filterTimer = window.setTimeout(() => {
    page.value = 1;
    loadLogs();
  }, 300);
});

watch(pageSize, () => {
  page.value = 1;
  loadLogs();
});

onUnmounted(() => {
  window.clearTimeout(filterTimer);
});

async function loadLogs() {
  isLoading.value = true;
  message.value = '';
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      pageSize: String(pageSize.value),
    });
    const account = username.value.trim();
    const moduleFilter = moduleName.value.trim();
    const actionFilter = actionName.value.trim();
    const keywordFilter = keyword.value.trim();
    const ip = operationIp.value.trim();
    if (account) params.set('username', account);
    if (moduleFilter) params.set('module', moduleFilter);
    if (actionFilter) params.set('action', actionFilter);
    if (keywordFilter) params.set('keyword', keywordFilter);
    if (ip) params.set('ip', ip);

    const data = await apiGet<OperationLogPage>(`/api/system/operation-logs/?${params.toString()}`);
    logs.value = data.results;
    total.value = data.total;
    if (data.page !== page.value) page.value = data.page;
    if (page.value > totalPages.value) setPage(totalPages.value);
  } catch (error) {
    logs.value = [];
    total.value = 0;
    message.value = errorMessage(error);
  } finally {
    isLoading.value = false;
  }
}

function setPage(nextPage: number) {
  const normalized = Math.min(Math.max(1, nextPage), totalPages.value);
  if (normalized === page.value) return;
  page.value = normalized;
  loadLogs();
}

function setPageSize(event: Event) {
  pageSize.value = Number((event.target as HTMLSelectElement).value);
}

function isColumnVisible(key: ColumnKey) {
  return visibleColumns.value[key];
}

function toggleColumn(key: ColumnKey, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  if (!checked && visibleColumnCount.value <= 1) return;
  visibleColumns.value = { ...visibleColumns.value, [key]: checked };
}

function toggleAllColumns(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  if (!checked) return;
  visibleColumns.value = columnOptions.reduce(
    (columns, column) => ({ ...columns, [column.key]: true }),
    {} as Record<ColumnKey, boolean>,
  );
}

function resetColumns() {
  visibleColumns.value = columnOptions.reduce(
    (columns, column) => ({ ...columns, [column.key]: column.key !== 'userAgent' }),
    {} as Record<ColumnKey, boolean>,
  );
}

function formatTime(value: string) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.replace('T', ' ').slice(0, 19);
  const pad = (number: number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
</script>

<template>
  <section v-if="activeTool === 'operationLogs'" class="login-log-page operation-log-page" :class="{ fullscreen }" @click="columnsOpen = false">
    <template v-if="canUseAnyPageAction('operationLogs', ['refresh', 'filter', 'columns'])">
      <article v-if="canUsePageAction('operationLogs', 'filter')" class="login-log-filter-panel">
        <label>
          <span>操作人：</span>
          <input v-model="username" placeholder="请输入" />
        </label>
        <label>
          <span>模块：</span>
          <input v-model="moduleName" placeholder="请输入" />
        </label>
        <label>
          <span>操作：</span>
          <input v-model="actionName" placeholder="请输入" />
        </label>
        <label>
          <span>关键字：</span>
          <input v-model="keyword" placeholder="请输入" />
        </label>
        <label>
          <span>IP：</span>
          <input v-model="operationIp" placeholder="请输入" />
        </label>
      </article>

      <article class="login-log-list-panel">
        <div class="login-log-toolbar">
          <h2>操作记录</h2>
          <div class="login-log-actions">
            <span v-if="canUseAnyPageAction('operationLogs', ['filter', 'refresh', 'columns'])" class="login-log-toolbar-divider"></span>
            <button v-if="canUsePageAction('operationLogs', 'refresh')" class="login-log-icon-button" type="button" title="刷新" aria-label="刷新" @click="loadLogs">
              <AppIcon name="refresh" :size="18" />
            </button>
            <div v-if="canUsePageAction('operationLogs', 'columns')" class="login-log-column-settings" @click.stop>
              <button class="login-log-icon-button" type="button" title="列设置" aria-label="列设置" @click="columnsOpen = !columnsOpen">
                <AppIcon name="settings" :size="18" />
              </button>
              <div v-if="columnsOpen" class="login-log-column-menu">
                <div class="login-log-column-menu-head">
                  <label class="login-log-column-all">
                    <input
                      type="checkbox"
                      :checked="allColumnsVisible"
                      :indeterminate.prop="someColumnsVisible && !allColumnsVisible"
                      @change="toggleAllColumns"
                    />
                    <span>列显示</span>
                  </label>
                  <button type="button" class="login-log-column-reset" @click="resetColumns">重置</button>
                </div>
                <div class="login-log-column-options">
                  <label v-for="column in columnOptions" :key="column.key" class="login-log-column-option">
                    <input
                      type="checkbox"
                      :checked="isColumnVisible(column.key)"
                      :disabled="visibleColumnCount <= 1 && isColumnVisible(column.key)"
                      @change="toggleColumn(column.key, $event)"
                    />
                    <span>{{ column.label }}</span>
                  </label>
                </div>
              </div>
            </div>
            <button class="login-log-icon-button" type="button" :title="fullscreen ? '退出全屏' : '全屏'" :aria-label="fullscreen ? '退出全屏' : '全屏'" @click="fullscreen = !fullscreen">
              <AppIcon :name="fullscreen ? 'minimize' : 'maximize'" :size="18" />
            </button>
          </div>
        </div>

        <p v-if="message" class="login-log-message">{{ message }}</p>

        <div class="login-log-table-wrap">
          <div class="login-log-table" :style="tableStyle">
            <div class="login-log-row head">
              <span v-if="isColumnVisible('createdAt')">时间</span>
              <span v-if="isColumnVisible('username')">操作人</span>
              <span v-if="isColumnVisible('module')">模块</span>
              <span v-if="isColumnVisible('action')">操作</span>
              <span v-if="isColumnVisible('target')">对象</span>
              <span v-if="isColumnVisible('ipAddress')">IP</span>
              <span v-if="isColumnVisible('detail')">详情</span>
              <span v-if="isColumnVisible('userAgent')">User Agent</span>
            </div>

            <div v-for="log in logs" :key="log.id" class="login-log-row">
              <span v-if="isColumnVisible('createdAt')" :title="formatTime(log.createdAt)">{{ formatTime(log.createdAt) }}</span>
              <strong v-if="isColumnVisible('username')" :title="log.username || ''">{{ log.username || '-' }}</strong>
              <span v-if="isColumnVisible('module')" :title="log.module || ''">{{ log.module || '-' }}</span>
              <span v-if="isColumnVisible('action')" class="login-log-status success" :title="log.action || ''">{{ log.action || '-' }}</span>
              <span v-if="isColumnVisible('target')" class="login-log-tip" :title="log.target || ''">{{ log.target || '-' }}</span>
              <span v-if="isColumnVisible('ipAddress')" :title="log.ipAddress || ''">{{ log.ipAddress || '-' }}</span>
              <span v-if="isColumnVisible('detail')" class="login-log-tip" :title="log.detail || ''">{{ log.detail || '-' }}</span>
              <span v-if="isColumnVisible('userAgent')" class="login-log-user-agent" :title="log.userAgent || ''">{{ log.userAgent || '-' }}</span>
            </div>

            <div v-if="!isLoading && !logs.length" class="login-log-empty">暂无操作记录</div>
            <div v-if="isLoading" class="login-log-empty">加载中...</div>
          </div>
        </div>

        <div class="host-pagination" aria-label="操作记录分页">
          <div class="host-pagination-summary">
            <span>共 {{ total }} 条</span>
            <span>{{ pageStart }}-{{ pageEnd }}</span>
          </div>
          <div class="host-pagination-controls">
            <button class="prev" type="button" :disabled="page <= 1" aria-label="上一页" @click="setPage(page - 1)">
              <AppIcon name="chevronRight" :size="14" />
            </button>
            <button
              v-for="pageNumber in pageNumbers"
              :key="pageNumber"
              type="button"
              :class="{ active: pageNumber === page }"
              @click="setPage(pageNumber)"
            >
              {{ pageNumber }}
            </button>
            <button type="button" :disabled="page >= totalPages" aria-label="下一页" @click="setPage(page + 1)">
              <AppIcon name="chevronRight" :size="14" />
            </button>
            <select :value="pageSize" aria-label="每页条数" @change="setPageSize">
              <option :value="10">10 条/页</option>
              <option :value="20">20 条/页</option>
              <option :value="50">50 条/页</option>
            </select>
          </div>
        </div>
      </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>
