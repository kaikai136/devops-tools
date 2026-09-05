<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { apiGet } from '../../api';
import { useAppContext } from '@app/context';
import { errorMessage } from '@shared/utils/errors';
import AppIcon from '@shared/components/AppIcon.vue';

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
}

const columnOptions: readonly ColumnOption[] = [
  { key: 'createdAt', label: '时间' },
  { key: 'username', label: '操作人' },
  { key: 'module', label: '模块' },
  { key: 'action', label: '操作' },
  { key: 'target', label: '对象' },
  { key: 'ipAddress', label: 'IP' },
  { key: 'detail', label: '详情' },
  { key: 'userAgent', label: 'User Agent' },
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
const visibleColumnCount = computed(() => Object.values(visibleColumns.value).filter(Boolean).length);
const allColumnsVisible = computed(() => columnOptions.every((column) => visibleColumns.value[column.key]));
const someColumnsVisible = computed(() => visibleColumnCount.value > 0);

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

function setPageSize(nextPageSize: number) {
  pageSize.value = nextPageSize;
}

function isColumnVisible(key: ColumnKey) {
  return visibleColumns.value[key];
}

function toggleColumn(key: ColumnKey, eventOrChecked: Event | boolean | string | number) {
  const checked = typeof eventOrChecked === 'boolean' ? eventOrChecked : Boolean(eventOrChecked);
  if (!checked && visibleColumnCount.value <= 1) return;
  visibleColumns.value = { ...visibleColumns.value, [key]: checked };
}

function toggleAllColumns(eventOrChecked: Event | boolean | string | number) {
  const checked = typeof eventOrChecked === 'boolean' ? eventOrChecked : Boolean(eventOrChecked);
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
        <NativeForm inline label-position="left">
          <NativeFormItem label="操作人">
            <NativeInput v-model="username" placeholder="请输入" clearable />
          </NativeFormItem>
          <NativeFormItem label="模块">
            <NativeInput v-model="moduleName" placeholder="请输入" clearable />
          </NativeFormItem>
          <NativeFormItem label="操作">
            <NativeInput v-model="actionName" placeholder="请输入" clearable />
          </NativeFormItem>
          <NativeFormItem label="关键字">
            <NativeInput v-model="keyword" placeholder="请输入" clearable />
          </NativeFormItem>
          <NativeFormItem label="IP">
            <NativeInput v-model="operationIp" placeholder="请输入" clearable />
          </NativeFormItem>
        </NativeForm>
      </article>

      <article class="login-log-list-panel">
        <div class="login-log-toolbar">
          <h2>操作记录</h2>
          <div class="login-log-actions">
            <span v-if="canUseAnyPageAction('operationLogs', ['filter', 'refresh', 'columns'])" class="login-log-toolbar-divider"></span>
            <NativeTooltip v-if="canUsePageAction('operationLogs', 'refresh')" content="刷新" placement="top">
              <NativeButton circle @click="loadLogs"><AppIcon name="refresh" :size="18" /></NativeButton>
            </NativeTooltip>
            <NativePopover
              v-if="canUsePageAction('operationLogs', 'columns')"
              v-model:visible="columnsOpen"
              placement="bottom-end"
              trigger="click"
              width="220"
              popper-class="login-log-column-menu"
              @click.stop
            >
              <template #reference>
                <NativeButton circle @click.stop><AppIcon name="settings" :size="18" /></NativeButton>
              </template>
              <div class="login-log-column-menu-head">
                <NativeCheckbox
                  :model-value="allColumnsVisible"
                  :indeterminate="someColumnsVisible && !allColumnsVisible"
                  @change="toggleAllColumns"
                >
                  列显示
                </NativeCheckbox>
                <NativeButton size="small" text type="primary" @click="resetColumns">重置</NativeButton>
              </div>
              <div class="login-log-column-options">
                <NativeCheckbox
                  v-for="column in columnOptions"
                  :key="column.key"
                  :model-value="isColumnVisible(column.key)"
                  :disabled="visibleColumnCount <= 1 && isColumnVisible(column.key)"
                  @change="toggleColumn(column.key, $event)"
                >
                  {{ column.label }}
                </NativeCheckbox>
              </div>
            </NativePopover>
            <NativeTooltip :content="fullscreen ? '退出全屏' : '全屏'" placement="top">
              <NativeButton circle @click="fullscreen = !fullscreen">
                <AppIcon :name="fullscreen ? 'minimize' : 'maximize'" :size="18" />
              </NativeButton>
            </NativeTooltip>
          </div>
        </div>

        <p v-if="message" class="login-log-message">{{ message }}</p>

        <div class="login-log-table-wrap">
          <NativeTable :data="logs" row-key="id" class="login-log-table" v-loading="isLoading" empty-text="暂无操作记录">
            <NativeTableColumn v-if="isColumnVisible('createdAt')" label="时间" min-width="170">
              <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
            </NativeTableColumn>
            <NativeTableColumn v-if="isColumnVisible('username')" prop="username" label="操作人" min-width="120" show-overflow-tooltip />
            <NativeTableColumn v-if="isColumnVisible('module')" prop="module" label="模块" min-width="120" show-overflow-tooltip />
            <NativeTableColumn v-if="isColumnVisible('action')" label="操作" min-width="120">
              <template #default="{ row }">
                <NativeTag type="success" size="small" effect="dark">{{ row.action || '-' }}</NativeTag>
              </template>
            </NativeTableColumn>
            <NativeTableColumn v-if="isColumnVisible('target')" prop="target" label="对象" min-width="180" show-overflow-tooltip />
            <NativeTableColumn v-if="isColumnVisible('ipAddress')" label="IP" min-width="140">
              <template #default="{ row }">{{ row.ipAddress || '-' }}</template>
            </NativeTableColumn>
            <NativeTableColumn v-if="isColumnVisible('detail')" prop="detail" label="详情" min-width="260" show-overflow-tooltip />
            <NativeTableColumn v-if="isColumnVisible('userAgent')" prop="userAgent" label="User Agent" min-width="300" show-overflow-tooltip />
          </NativeTable>
        </div>

        <div class="host-pagination" aria-label="操作记录分页">
          <div class="host-pagination-summary">
            <span>共 {{ total }} 条</span>
            <span>{{ pageStart }}-{{ pageEnd }}</span>
          </div>
          <NativePagination
            background
            layout="prev, pager, next, sizes"
            :current-page="page"
            :page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            @current-change="setPage"
            @size-change="setPageSize"
          />
        </div>
      </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>
