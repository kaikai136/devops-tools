<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { useAppContext } from '@app/context';
import AppIcon from '@shared/components/AppIcon.vue';
import {
  createCompanyDevice,
  deleteCompanyDevice,
  listCompanyDevices,
  updateCompanyDevice,
} from '../api/devices';
import type { CompanyDevice, CompanyDevicePayload, CompanyDeviceStatus } from '../types';
import { buildCompanyDeviceXlsxWorkbook, companyDeviceStatusText } from '../utils/export';

interface DeviceDialogState {
  mode: 'create' | 'edit';
  deviceId: number | null;
}

type DeviceFormErrors = Partial<Record<keyof CompanyDevicePayload, string>>;

const { canUsePageAction, requestConfirm, showToast } = useAppContext();
const devices = ref<CompanyDevice[]>([]);
const selectedDevices = ref<CompanyDevice[]>([]);
const statusFilter = ref<'' | CompanyDeviceStatus>('');
const categoryFilter = ref('');
const search = ref('');
const page = ref(1);
const pageSize = ref(10);
const isLoading = ref(false);
const isSaving = ref(false);
const loadError = ref('');
const dialogError = ref('');
const deviceDialog = ref<DeviceDialogState | null>(null);
const deviceForm = ref<CompanyDevicePayload>(createDeviceDraft());
const formErrors = ref<DeviceFormErrors>({});

const filteredDevices = computed(() => {
  const query = search.value.trim().toLowerCase();
  return devices.value.filter((device) => {
    const matchesStatus = !statusFilter.value || device.status === statusFilter.value;
    const matchesCategory = !categoryFilter.value || device.category === categoryFilter.value;
    const values = [
      device.name,
      device.category,
      device.code,
      device.spec,
      device.user,
      device.brand,
      device.purchaseTime ?? '',
      device.remark,
    ];
    const matchesQuery = !query || values.some((value) => value.toLowerCase().includes(query));
    return matchesStatus && matchesCategory && matchesQuery;
  });
});
const totalPages = computed(() => Math.max(1, Math.ceil(filteredDevices.value.length / pageSize.value)));
const pagedDevices = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredDevices.value.slice(start, start + pageSize.value);
});
const pageStart = computed(() => (filteredDevices.value.length ? (page.value - 1) * pageSize.value + 1 : 0));
const pageEnd = computed(() => Math.min(page.value * pageSize.value, filteredDevices.value.length));
const fixedAssetCount = computed(() => filteredDevices.value.filter((device) => device.category === '固定资产').length);
const consumableCount = computed(() => filteredDevices.value.filter((device) => device.category === '耗材').length);

watch([filteredDevices, pageSize], () => {
  if (page.value > totalPages.value) page.value = totalPages.value;
});

watch([statusFilter, categoryFilter, search, pageSize], () => {
  page.value = 1;
});

onMounted(() => {
  void loadDevices();
});

function createDeviceDraft(device?: CompanyDevice | null): CompanyDevicePayload {
  return {
    name: device?.name ?? '',
    category: device?.category ?? '固定资产',
    code: device?.code ?? '',
    spec: device?.spec ?? '',
    status: device?.status ?? 'using',
    user: device?.user ?? '',
    brand: device?.brand ?? '',
    purchaseTime: device?.purchaseTime ?? null,
    remark: device?.remark ?? '',
  };
}

function devicePayload(form: CompanyDevicePayload): CompanyDevicePayload {
  return {
    name: form.name.trim(),
    category: form.category.trim() || '固定资产',
    code: form.code.trim(),
    spec: form.spec.trim(),
    status: form.status,
    user: form.user.trim(),
    brand: form.brand.trim(),
    purchaseTime: form.purchaseTime || null,
    remark: form.remark.trim(),
  };
}

function validateDeviceForm() {
  const errors: DeviceFormErrors = {};
  if (!deviceForm.value.name.trim()) errors.name = '请输入资产名称';
  if (!deviceForm.value.category.trim()) errors.category = '请输入资产类别';
  formErrors.value = errors;
  return Object.keys(errors).length === 0;
}

async function loadDevices() {
  isLoading.value = true;
  loadError.value = '';
  try {
    devices.value = await listCompanyDevices();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '设备列表加载失败';
  } finally {
    isLoading.value = false;
  }
}

function openCreateDeviceDialog() {
  deviceDialog.value = { mode: 'create', deviceId: null };
  deviceForm.value = createDeviceDraft();
  formErrors.value = {};
  dialogError.value = '';
}

function openEditDeviceDialog(device: CompanyDevice) {
  deviceDialog.value = { mode: 'edit', deviceId: device.id };
  deviceForm.value = createDeviceDraft(device);
  formErrors.value = {};
  dialogError.value = '';
}

function closeDeviceDialog() {
  if (isSaving.value) return;
  finishDeviceDialog();
}

function finishDeviceDialog() {
  deviceDialog.value = null;
  dialogError.value = '';
}

async function saveDeviceDialog() {
  if (!deviceDialog.value || isSaving.value || !validateDeviceForm()) return;
  isSaving.value = true;
  dialogError.value = '';
  try {
    const payload = devicePayload(deviceForm.value);
    const saved = deviceDialog.value.mode === 'edit' && deviceDialog.value.deviceId
      ? await updateCompanyDevice(deviceDialog.value.deviceId, payload)
      : await createCompanyDevice(payload);
    devices.value = deviceDialog.value.mode === 'edit'
      ? devices.value.map((device) => (device.id === saved.id ? saved : device))
      : [saved, ...devices.value];
    showToast('保存成功', `设备「${saved.name}」已保存。`);
    finishDeviceDialog();
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '设备保存失败';
  } finally {
    isSaving.value = false;
  }
}

function confirmDeleteDevice(device: CompanyDevice) {
  requestConfirm('删除设备', `确定删除设备「${device.name}」？`, '删除', async () => {
    try {
      await deleteCompanyDevice(device.id);
      devices.value = devices.value.filter((item) => item.id !== device.id);
      selectedDevices.value = selectedDevices.value.filter((item) => item.id !== device.id);
      showToast('删除成功', `设备「${device.name}」已删除。`);
    } catch (error) {
      showToast('删除失败', error instanceof Error ? error.message : '设备删除失败');
    }
  });
}

function confirmDeleteSelectedDevices() {
  const selected = selectedDevices.value;
  if (!selected.length) return;
  requestConfirm('批量删除设备', `确定删除选中的 ${selected.length} 台设备？`, '删除', async () => {
    try {
      for (const device of selected) {
        await deleteCompanyDevice(device.id);
      }
      const deletedIds = new Set(selected.map((device) => device.id));
      devices.value = devices.value.filter((device) => !deletedIds.has(device.id));
      selectedDevices.value = [];
      showToast('删除成功', `已删除 ${selected.length} 台设备。`);
    } catch (error) {
      showToast('删除失败', error instanceof Error ? error.message : '部分设备删除失败');
    }
  });
}

function exportDevices() {
  const selected = selectedDevices.value;
  const exportRows = selected.length ? selected : filteredDevices.value;
  if (!exportRows.length) {
    showToast('导出失败', '当前没有可导出的设备。');
    return;
  }
  try {
    const date = new Date().toISOString().slice(0, 10);
    downloadFile(
      buildCompanyDeviceXlsxWorkbook(exportRows),
      `company-devices-${date}.xlsx`,
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    );
    showToast('导出成功', `已导出 ${exportRows.length} 台设备。`);
  } catch (error) {
    showToast('导出失败', error instanceof Error ? error.message : '设备导出失败');
  }
}

function downloadFile(content: BlobPart, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function statusText(status: CompanyDeviceStatus) {
  return companyDeviceStatusText(status);
}

function statusTagType(status: CompanyDeviceStatus) {
  if (status === 'idle') return 'success';
  if (status === 'repair') return 'warning';
  if (status === 'scrapped') return 'info';
  return 'primary';
}

function categoryClass(category: string) {
  return category === '耗材' ? 'consumable' : 'fixed';
}

function resetFilters() {
  statusFilter.value = '';
  categoryFilter.value = '';
  search.value = '';
  page.value = 1;
}

function setPage(nextPage: number) {
  page.value = Math.min(Math.max(1, nextPage), totalPages.value);
}

function handleSelectionChange(rows: CompanyDevice[]) {
  selectedDevices.value = rows;
}

function setPageSize(size: number) {
  pageSize.value = size;
}
</script>

<template>
  <section class="device-manager-page tw:flex tw:min-h-0 tw:min-w-0 tw:flex-1 tw:overflow-auto tw:bg-app-page tw:p-[var(--app-page-gutter)] tw:text-app-text">
    <article class="device-list-panel tw:flex tw:h-auto tw:min-h-[calc(100dvh-96px)] tw:w-full tw:min-w-0 tw:flex-col tw:overflow-hidden tw:rounded-app-md tw:border tw:border-app-border tw:bg-app-surface tw:shadow-[var(--app-shadow-md)] tw:max-[760px]:min-h-[calc(100dvh-76px)] tw:min-[1181px]:h-[calc(100dvh-104px)] tw:min-[1181px]:min-h-[560px]">
      <div class="device-list-toolbar tw:grid tw:grid-cols-1 tw:items-stretch tw:gap-4 tw:border-b tw:border-app-border-soft tw:bg-app-surface tw:p-[var(--app-panel-padding)] tw:min-[1181px]:grid-cols-[minmax(0,1fr)_auto] tw:min-[1181px]:items-center">
        <div v-if="canUsePageAction('companyDevices', 'filter')" class="device-toolbar-filters tw:flex tw:min-w-0 tw:flex-wrap tw:items-center tw:justify-start tw:gap-2.5">
          <el-select v-model="statusFilter" class="device-toolbar-select tw:w-full tw:min-w-0 tw:flex-1 tw:md:w-[136px] tw:md:flex-[0_0_136px]" aria-label="资产状态" placeholder="资产状态" clearable>
            <el-option value="" label="资产状态" />
            <el-option value="using" label="使用中" />
            <el-option value="idle" label="闲置" />
            <el-option value="repair" label="维修" />
            <el-option value="scrapped" label="报废" />
          </el-select>
          <el-select v-model="categoryFilter" class="device-toolbar-select tw:w-full tw:min-w-0 tw:flex-1 tw:md:w-[136px] tw:md:flex-[0_0_136px]" aria-label="资产类别" placeholder="资产类别" clearable>
            <el-option value="" label="资产类别" />
            <el-option value="固定资产" label="固定资产" />
            <el-option value="耗材" label="耗材" />
          </el-select>
          <el-input v-model="search" placeholder="输入名称等信息" class="device-toolbar-search tw:w-full tw:min-w-0 tw:flex-1 tw:md:w-[260px] tw:md:min-w-[220px] tw:md:flex-[0_1_260px]" aria-label="输入名称等信息" clearable />
          <el-button type="danger" @click="resetFilters">重置</el-button>
        </div>
        <div class="device-toolbar-actions tw:flex tw:flex-none tw:flex-wrap tw:items-center tw:justify-start tw:gap-2.5 tw:md:flex-nowrap tw:min-[1181px]:justify-end">
          <el-button
            v-if="canUsePageAction('companyDevices', 'delete')"
            type="danger"
            :disabled="!selectedDevices.length"
            @click="confirmDeleteSelectedDevices"
          >
            <AppIcon name="trash" :size="15" />删除
          </el-button>
          <el-button
            v-if="canUsePageAction('companyDevices', 'create')"
            type="primary"
            @click="openCreateDeviceDialog"
          >
            <AppIcon name="plus" :size="15" />添加
          </el-button>
          <el-button
            v-if="canUsePageAction('companyDevices', 'export')"
            type="primary"
            @click="exportDevices"
          >
            <AppIcon name="download" :size="15" />导出Excel
          </el-button>
        </div>
      </div>

      <div v-if="isLoading" class="device-loading tw:flex tw:min-h-[220px] tw:flex-1 tw:items-center tw:justify-center tw:gap-2.5 tw:text-app-text-muted">
        <AppIcon name="refresh" :size="16" />加载中...
      </div>
      <div v-else-if="loadError" class="device-load-error tw:flex tw:min-h-[220px] tw:flex-1 tw:items-center tw:justify-center tw:gap-2.5 tw:text-app-danger">
        <span>{{ loadError }}</span>
        <el-button type="primary" @click="loadDevices">重试</el-button>
      </div>
      <div v-else class="device-table-wrap tw:min-h-0 tw:flex-1 tw:overflow-hidden tw:bg-app-surface tw:px-2.5 tw:pt-2.5 tw:md:px-4 tw:md:pt-3.5">
        <el-table
          :data="pagedDevices"
          row-key="id"
          class="device-table"
          height="100%"
          border
          stripe
          highlight-current-row
          empty-text="暂无资产数据"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="40" reserve-selection />
          <el-table-column type="index" label="序号" width="70" :index="(index) => (page - 1) * pageSize + index + 1" />
          <el-table-column prop="name" label="资产名称" min-width="140" />
          <el-table-column prop="category" label="资产类别" min-width="100">
            <template #default="{ row }">
              <span class="device-category-badge" :class="categoryClass(row.category)">{{ row.category }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="code" label="资产编码" min-width="120">
            <template #default="{ row }">{{ row.code || '-' }}</template>
          </el-table-column>
          <el-table-column prop="spec" label="规格说明" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">{{ row.spec || '-' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="资产状态" min-width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="dark">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user" label="使用人员" min-width="100">
            <template #default="{ row }">{{ row.user || '-' }}</template>
          </el-table-column>
          <el-table-column prop="brand" label="品牌名称" min-width="100">
            <template #default="{ row }">{{ row.brand || '-' }}</template>
          </el-table-column>
          <el-table-column prop="purchaseTime" label="采购时间" min-width="120">
            <template #default="{ row }">{{ row.purchaseTime || '-' }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="120">
            <template #default="{ row }">{{ row.remark || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <div class="device-row-actions tw:inline-flex tw:items-center tw:gap-1.5">
                <el-button
                  v-if="canUsePageAction('companyDevices', 'edit')"
                  type="primary"
                  size="small"
                  link
                  @click="openEditDeviceDialog(row)"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="canUsePageAction('companyDevices', 'delete')"
                  type="danger"
                  size="small"
                  link
                  @click="confirmDeleteDevice(row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="device-pagination tw:flex tw:flex-none tw:flex-wrap tw:items-center tw:justify-between tw:gap-4 tw:border-t tw:border-app-border-soft tw:bg-app-surface-muted tw:px-4 tw:py-2.5 tw:text-sm tw:font-bold tw:text-app-text-muted">
        <div class="device-pagination-left tw:flex tw:min-w-0 tw:flex-1 tw:flex-wrap tw:items-center tw:gap-2.5">
          <div class="device-pagination-summary tw:flex tw:flex-none tw:items-center tw:gap-2.5 tw:text-app-text-secondary">
            <span>共 {{ filteredDevices.length }} 条</span>
            <span>{{ pageStart }}-{{ pageEnd }}</span>
          </div>
          <el-pagination
            :current-page="page"
            :page-size="pageSize"
            :total="filteredDevices.length"
            :page-sizes="[10, 20, 50]"
            layout="prev, pager, next, sizes"
            small
            background
            @current-change="setPage"
            @size-change="setPageSize"
          />
        </div>
        <div class="device-category-summary tw:ml-auto tw:flex tw:flex-none tw:flex-wrap tw:items-center tw:justify-end tw:gap-2.5 tw:max-[1180px]:ml-0 tw:max-[1180px]:justify-start">
          <span class="device-summary-pill">固定资产 {{ fixedAssetCount }}</span>
          <span class="device-summary-pill">耗材 {{ consumableCount }}</span>
        </div>
      </div>
    </article>

    <el-dialog
      :model-value="deviceDialog !== null"
      :title="deviceDialog?.mode === 'edit' ? '编辑设备' : '添加设备'"
      width="640px"
      :close-on-click-modal="false"
      @update:model-value="(visible) => { if (!visible && !isSaving) finishDeviceDialog(); }"
    >
      <el-form :model="deviceForm" label-position="top" class="device-form-modal popup-body popup-form-grid tw:grid tw:w-full tw:grid-cols-1 tw:gap-x-4 tw:gap-y-2 tw:md:grid-cols-2">
        <p v-if="dialogError" class="device-form-error tw:col-span-full tw:m-0 tw:text-xs tw:font-medium tw:text-app-danger">{{ dialogError }}</p>
        <el-form-item label="资产名称" :error="formErrors.name">
          <el-input v-model="deviceForm.name" autofocus />
        </el-form-item>
        <el-form-item label="资产类别" :error="formErrors.category">
          <el-select v-model="deviceForm.category">
            <el-option value="固定资产" label="固定资产" />
            <el-option value="耗材" label="耗材" />
          </el-select>
        </el-form-item>
        <el-form-item label="资产编码">
          <el-input v-model="deviceForm.code" />
        </el-form-item>
        <el-form-item label="规格说明">
          <el-input v-model="deviceForm.spec" />
        </el-form-item>
        <el-form-item label="资产状态">
          <el-select v-model="deviceForm.status">
            <el-option value="using" label="使用中" />
            <el-option value="idle" label="闲置" />
            <el-option value="repair" label="维修" />
            <el-option value="scrapped" label="报废" />
          </el-select>
        </el-form-item>
        <el-form-item label="使用人员">
          <el-input v-model="deviceForm.user" />
        </el-form-item>
        <el-form-item label="品牌名称">
          <el-input v-model="deviceForm.brand" />
        </el-form-item>
        <el-form-item label="采购时间">
          <el-date-picker v-model="deviceForm.purchaseTime" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
        </el-form-item>
        <el-form-item label="备注" class="device-form-wide tw:col-span-full">
          <el-input v-model="deviceForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="popup-actions">
          <el-button :disabled="isSaving" @click="closeDeviceDialog">取消</el-button>
          <el-button type="primary" :disabled="isSaving" @click="saveDeviceDialog">{{ isSaving ? '保存中...' : '保存' }}</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
