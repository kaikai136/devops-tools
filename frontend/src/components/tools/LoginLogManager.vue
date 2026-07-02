<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { apiGet } from '../../api';
import { useAppContext } from '../../appContext';
import { errorMessage } from '../../utils/errors';
import AppIcon from '../common/AppIcon.vue';

type LoginLogStatus = 'success' | 'failed';
type StatusFilter = 'all' | LoginLogStatus;
type ColumnKey = 'createdAt' | 'username' | 'status' | 'ipAddress' | 'userAgent' | 'message';

interface LoginLog {
  id: number;
  username: string;
  ipAddress: string | null;
  userAgent: string;
  status: LoginLogStatus;
  message: string;
  createdAt: string;
}

interface LoginLogPage {
  results: LoginLog[];
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
  { key: 'createdAt', label: '时间', width: 'minmax(170px, 1.1fr)' },
  { key: 'username', label: '账户名', width: 'minmax(100px, 0.7fr)' },
  { key: 'status', label: '状态', width: 'minmax(82px, 0.5fr)' },
  { key: 'ipAddress', label: '登录IP', width: 'minmax(150px, 0.9fr)' },
  { key: 'userAgent', label: 'User Agent', width: 'minmax(420px, 2.6fr)' },
  { key: 'message', label: '提示信息', width: 'minmax(360px, 2.3fr)' },
];

const { activeTool, canUsePageAction, canUseAnyPageAction } = useAppContext();

const logs = ref<LoginLog[]>([]);
const username = ref('');
const loginIp = ref('');
const statusFilter = ref<StatusFilter>('all');
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
  status: true,
  ipAddress: true,
  userAgent: true,
  message: true,
});

let filterTimer: number | undefined;

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
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

watch([username, loginIp], () => {
  window.clearTimeout(filterTimer);
  filterTimer = window.setTimeout(() => {
    page.value = 1;
    loadLogs();
  }, 300);
});

watch([statusFilter, pageSize], () => {
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
    const ip = loginIp.value.trim();
    if (account) params.set('username', account);
    if (ip) params.set('ip', ip);
    if (statusFilter.value !== 'all') params.set('status', statusFilter.value);

    const data = await apiGet<LoginLogPage>(`/api/system/login-logs/?${params.toString()}`);
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

function setStatusFilter(nextStatus: StatusFilter) {
  statusFilter.value = nextStatus;
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
    (columns, column) => ({ ...columns, [column.key]: true }),
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

function statusText(status: LoginLogStatus) {
  return status === 'success' ? '成功' : '失败';
}
</script>

<template>
  <section v-if="activeTool === 'loginLogs'" class="login-log-page" :class="{ fullscreen }" @click="columnsOpen = false">
    <template v-if="canUseAnyPageAction('loginLogs', ['refresh', 'filter', 'columns'])">
    <article v-if="canUsePageAction('loginLogs', 'filter')" class="login-log-filter-panel">
      <label>
        <span>账户名称：</span>
        <input v-model="username" placeholder="请输入" />
      </label>
      <label>
        <span>登录IP：</span>
        <input v-model="loginIp" placeholder="请输入" />
      </label>
    </article>

    <article class="login-log-list-panel">
      <div class="login-log-toolbar">
        <h2>登录记录</h2>
        <div class="login-log-actions">
          <div v-if="canUsePageAction('loginLogs', 'filter')" class="login-log-tabs" role="tablist" aria-label="登录状态">
            <button :class="{ active: statusFilter === 'all' }" type="button" @click="setStatusFilter('all')">全部</button>
            <button :class="{ active: statusFilter === 'success' }" type="button" @click="setStatusFilter('success')">成功</button>
            <button :class="{ active: statusFilter === 'failed' }" type="button" @click="setStatusFilter('failed')">失败</button>
          </div>
          <span v-if="canUseAnyPageAction('loginLogs', ['filter', 'refresh', 'columns'])" class="login-log-toolbar-divider"></span>
          <button v-if="canUsePageAction('loginLogs', 'refresh')" class="login-log-icon-button" type="button" title="刷新" aria-label="刷新" @click="loadLogs">
            <AppIcon name="refresh" :size="18" />
          </button>
          <div v-if="canUsePageAction('loginLogs', 'columns')" class="login-log-column-settings" @click.stop>
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
            <span v-if="isColumnVisible('username')">账户名</span>
            <span v-if="isColumnVisible('status')">状态</span>
            <span v-if="isColumnVisible('ipAddress')">登录IP</span>
            <span v-if="isColumnVisible('userAgent')">User Agent</span>
            <span v-if="isColumnVisible('message')">提示信息</span>
          </div>

          <div v-for="log in logs" :key="log.id" class="login-log-row">
            <span v-if="isColumnVisible('createdAt')" :title="formatTime(log.createdAt)">{{ formatTime(log.createdAt) }}</span>
            <strong v-if="isColumnVisible('username')" :title="log.username || ''">{{ log.username || '-' }}</strong>
            <span v-if="isColumnVisible('status')" class="login-log-status" :class="log.status" :title="statusText(log.status)">{{ statusText(log.status) }}</span>
            <span v-if="isColumnVisible('ipAddress')" :title="log.ipAddress || ''">{{ log.ipAddress || '-' }}</span>
            <span v-if="isColumnVisible('userAgent')" class="login-log-user-agent" :title="log.userAgent || ''">{{ log.userAgent || '-' }}</span>
            <span v-if="isColumnVisible('message')" class="login-log-tip" :title="log.message || ''">{{ log.message || '-' }}</span>
          </div>

          <div v-if="!isLoading && !logs.length" class="login-log-empty">暂无登录记录</div>
          <div v-if="isLoading" class="login-log-empty">加载中...</div>
        </div>
      </div>

      <div class="login-log-pagination">
        <span>共 {{ total }} 条</span>
        <button type="button" :disabled="page <= 1" aria-label="上一页" @click="setPage(page - 1)">
          <AppIcon name="chevronRight" :size="16" />
        </button>
        <strong>{{ page }}</strong>
        <button type="button" :disabled="page >= totalPages" aria-label="下一页" @click="setPage(page + 1)">
          <AppIcon name="chevronRight" :size="16" />
        </button>
        <select :value="pageSize" aria-label="每页条数" @change="setPageSize">
          <option :value="10">10 条/页</option>
          <option :value="20">20 条/页</option>
          <option :value="50">50 条/页</option>
        </select>
      </div>
    </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>
