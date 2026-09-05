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
  <section class="device-manager-page">
    <article class="device-list-panel">
      <div class="device-list-toolbar">
        <div v-if="canUsePageAction('companyDevices', 'filter')" class="device-toolbar-filters">
          <NativeSelect v-model="statusFilter" class="device-toolbar-select" aria-label="资产状态" placeholder="资产状态" clearable>
            <NativeOption value="" label="资产状态" />
            <NativeOption value="using" label="使用中" />
            <NativeOption value="idle" label="闲置" />
            <NativeOption value="repair" label="维修" />
            <NativeOption value="scrapped" label="报废" />
          </NativeSelect>
          <NativeSelect v-model="categoryFilter" class="device-toolbar-select" aria-label="资产类别" placeholder="资产类别" clearable>
            <NativeOption value="" label="资产类别" />
            <NativeOption value="固定资产" label="固定资产" />
            <NativeOption value="耗材" label="耗材" />
          </NativeSelect>
          <NativeInput v-model="search" placeholder="输入名称等信息" class="device-toolbar-search" aria-label="输入名称等信息" clearable />
          <NativeButton type="danger" @click="resetFilters">重置</NativeButton>
        </div>
        <div class="device-toolbar-actions">
          <NativeButton
            v-if="canUsePageAction('companyDevices', 'delete')"
            type="danger"
            :disabled="!selectedDevices.length"
            @click="confirmDeleteSelectedDevices"
          >
            <AppIcon name="trash" :size="15" />删除
          </NativeButton>
          <NativeButton
            v-if="canUsePageAction('companyDevices', 'create')"
            type="primary"
            @click="openCreateDeviceDialog"
          >
            <AppIcon name="plus" :size="15" />添加
          </NativeButton>
          <NativeButton
            v-if="canUsePageAction('companyDevices', 'export')"
            type="primary"
            @click="exportDevices"
          >
            <AppIcon name="download" :size="15" />导出Excel
          </NativeButton>
        </div>
      </div>

      <div v-if="isLoading" class="device-loading">
        <AppIcon name="refresh" :size="16" />加载中...
      </div>
      <div v-else-if="loadError" class="device-load-error">
        <span>{{ loadError }}</span>
        <NativeButton type="primary" @click="loadDevices">重试</NativeButton>
      </div>
      <div v-else class="device-table-wrap">
        <NativeTable
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
          <NativeTableColumn type="selection" width="40" reserve-selection />
          <NativeTableColumn type="index" label="序号" width="70" :index="(index) => (page - 1) * pageSize + index + 1" />
          <NativeTableColumn prop="name" label="资产名称" min-width="140" />
          <NativeTableColumn prop="category" label="资产类别" min-width="100">
            <template #default="{ row }">
              <span class="device-category-badge" :class="categoryClass(row.category)">{{ row.category }}</span>
            </template>
          </NativeTableColumn>
          <NativeTableColumn prop="code" label="资产编码" min-width="120">
            <template #default="{ row }">{{ row.code || '-' }}</template>
          </NativeTableColumn>
          <NativeTableColumn prop="spec" label="规格说明" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">{{ row.spec || '-' }}</template>
          </NativeTableColumn>
          <NativeTableColumn prop="status" label="资产状态" min-width="100">
            <template #default="{ row }">
              <NativeTag :type="statusTagType(row.status)" size="small" effect="dark">{{ statusText(row.status) }}</NativeTag>
            </template>
          </NativeTableColumn>
          <NativeTableColumn prop="user" label="使用人员" min-width="100">
            <template #default="{ row }">{{ row.user || '-' }}</template>
          </NativeTableColumn>
          <NativeTableColumn prop="brand" label="品牌名称" min-width="100">
            <template #default="{ row }">{{ row.brand || '-' }}</template>
          </NativeTableColumn>
          <NativeTableColumn prop="purchaseTime" label="采购时间" min-width="120">
            <template #default="{ row }">{{ row.purchaseTime || '-' }}</template>
          </NativeTableColumn>
          <NativeTableColumn prop="remark" label="备注" min-width="120">
            <template #default="{ row }">{{ row.remark || '-' }}</template>
          </NativeTableColumn>
          <NativeTableColumn label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <div class="device-row-actions">
                <NativeButton
                  v-if="canUsePageAction('companyDevices', 'edit')"
                  type="primary"
                  size="small"
                  link
                  @click="openEditDeviceDialog(row)"
                >
                  编辑
                </NativeButton>
                <NativeButton
                  v-if="canUsePageAction('companyDevices', 'delete')"
                  type="danger"
                  size="small"
                  link
                  @click="confirmDeleteDevice(row)"
                >
                  删除
                </NativeButton>
              </div>
            </template>
          </NativeTableColumn>
        </NativeTable>
      </div>

      <div class="device-pagination">
        <div class="device-pagination-left">
          <div class="device-pagination-summary">
            <span>共 {{ filteredDevices.length }} 条</span>
            <span>{{ pageStart }}-{{ pageEnd }}</span>
          </div>
          <NativePagination
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
        <div class="device-category-summary">
          <span class="device-summary-pill">固定资产 {{ fixedAssetCount }}</span>
          <span class="device-summary-pill">耗材 {{ consumableCount }}</span>
        </div>
      </div>
    </article>

    <NativeDialog
      :model-value="deviceDialog !== null"
      :title="deviceDialog?.mode === 'edit' ? '编辑设备' : '添加设备'"
      width="640px"
      :close-on-click-modal="false"
      @update:model-value="(visible) => { if (!visible && !isSaving) finishDeviceDialog(); }"
    >
      <NativeForm :model="deviceForm" label-position="top" class="device-form-modal">
        <p v-if="dialogError" class="device-form-error">{{ dialogError }}</p>
        <NativeFormItem label="资产名称" :error="formErrors.name">
          <NativeInput v-model="deviceForm.name" autofocus />
        </NativeFormItem>
        <NativeFormItem label="资产类别" :error="formErrors.category">
          <NativeSelect v-model="deviceForm.category">
            <NativeOption value="固定资产" label="固定资产" />
            <NativeOption value="耗材" label="耗材" />
          </NativeSelect>
        </NativeFormItem>
        <NativeFormItem label="资产编码">
          <NativeInput v-model="deviceForm.code" />
        </NativeFormItem>
        <NativeFormItem label="规格说明">
          <NativeInput v-model="deviceForm.spec" />
        </NativeFormItem>
        <NativeFormItem label="资产状态">
          <NativeSelect v-model="deviceForm.status">
            <NativeOption value="using" label="使用中" />
            <NativeOption value="idle" label="闲置" />
            <NativeOption value="repair" label="维修" />
            <NativeOption value="scrapped" label="报废" />
          </NativeSelect>
        </NativeFormItem>
        <NativeFormItem label="使用人员">
          <NativeInput v-model="deviceForm.user" />
        </NativeFormItem>
        <NativeFormItem label="品牌名称">
          <NativeInput v-model="deviceForm.brand" />
        </NativeFormItem>
        <NativeFormItem label="采购时间">
          <NativeDatePicker v-model="deviceForm.purchaseTime" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
        </NativeFormItem>
        <NativeFormItem label="备注" class="device-form-wide">
          <NativeInput v-model="deviceForm.remark" type="textarea" :rows="3" />
        </NativeFormItem>
      </NativeForm>
      <template #footer>
        <NativeButton :disabled="isSaving" @click="closeDeviceDialog">取消</NativeButton>
        <NativeButton type="primary" :disabled="isSaving" @click="saveDeviceDialog">{{ isSaving ? '保存中...' : '保存' }}</NativeButton>
      </template>
    </NativeDialog>
  </section>
</template>
