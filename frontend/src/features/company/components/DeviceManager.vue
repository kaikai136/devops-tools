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
const selectedIds = ref<Set<number>>(new Set());
const statusFilter = ref<'' | CompanyDeviceStatus>('');
const categoryFilter = ref('');
const search = ref('');
const page = ref(1);
const pageSize = 10;
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
const totalPages = computed(() => Math.max(1, Math.ceil(filteredDevices.value.length / pageSize)));
const pagedDevices = computed(() => filteredDevices.value.slice((page.value - 1) * pageSize, page.value * pageSize));
const visibleDeviceIds = computed(() => pagedDevices.value.map((device) => device.id));
const allVisibleSelected = computed(() => visibleDeviceIds.value.length > 0 && visibleDeviceIds.value.every((id) => selectedIds.value.has(id)));
const selectedDeviceCount = computed(() => selectedIds.value.size);

watch([filteredDevices], () => {
  if (page.value > totalPages.value) page.value = totalPages.value;
});

watch([statusFilter, categoryFilter, search], () => {
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
    closeDeviceDialog();
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
      const next = new Set(selectedIds.value);
      next.delete(device.id);
      selectedIds.value = next;
      showToast('删除成功', `设备「${device.name}」已删除。`);
    } catch (error) {
      showToast('删除失败', error instanceof Error ? error.message : '设备删除失败');
    }
  });
}

function confirmDeleteSelectedDevices() {
  const selectedDevices = devices.value.filter((device) => selectedIds.value.has(device.id));
  if (!selectedDevices.length) return;
  requestConfirm('批量删除设备', `确定删除选中的 ${selectedDevices.length} 台设备？`, '删除', async () => {
    try {
      for (const device of selectedDevices) {
        await deleteCompanyDevice(device.id);
      }
      const deletedIds = new Set(selectedDevices.map((device) => device.id));
      devices.value = devices.value.filter((device) => !deletedIds.has(device.id));
      selectedIds.value = new Set();
      showToast('删除成功', `已删除 ${selectedDevices.length} 台设备。`);
    } catch (error) {
      showToast('删除失败', error instanceof Error ? error.message : '部分设备删除失败');
    }
  });
}

function exportDevices() {
  const selectedDevices = filteredDevices.value.filter((device) => selectedIds.value.has(device.id));
  const exportRows = selectedDevices.length ? selectedDevices : filteredDevices.value;
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

function toggleAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const next = new Set(selectedIds.value);
  visibleDeviceIds.value.forEach((deviceId) => {
    if (checked) next.add(deviceId);
    else next.delete(deviceId);
  });
  selectedIds.value = next;
}

function toggleDevice(deviceId: number, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const next = new Set(selectedIds.value);
  if (checked) next.add(deviceId);
  else next.delete(deviceId);
  selectedIds.value = next;
}

function resetFilters() {
  statusFilter.value = '';
  categoryFilter.value = '';
  search.value = '';
  page.value = 1;
}
</script>

<template>
  <section class="device-manager-page">
    <article class="device-list-panel">
      <div class="device-list-toolbar">
        <h2><AppIcon name="hardDrive" :size="18" />资产列表</h2>
        <div class="device-toolbar-actions">
          <button
            v-if="canUsePageAction('companyDevices', 'delete')"
            class="device-button danger"
            type="button"
            :disabled="!selectedIds.size"
            @click="confirmDeleteSelectedDevices"
          >
            <AppIcon name="trash" :size="15" />删除
          </button>
          <button
            v-if="canUsePageAction('companyDevices', 'create')"
            class="device-button primary"
            type="button"
            @click="openCreateDeviceDialog"
          >
            <AppIcon name="plus" :size="15" />添加
          </button>
          <button
            v-if="canUsePageAction('companyDevices', 'export')"
            class="device-button primary"
            type="button"
            @click="exportDevices"
          >
            <AppIcon name="download" :size="15" />导出Excel
          </button>
          <template v-if="canUsePageAction('companyDevices', 'filter')">
            <select v-model="statusFilter" aria-label="资产状态">
              <option value="">资产状态</option>
              <option value="using">使用中</option>
              <option value="idle">闲置</option>
              <option value="repair">维修中</option>
            </select>
            <select v-model="categoryFilter" aria-label="资产类别">
              <option value="">资产类别</option>
              <option value="固定资产">固定资产</option>
              <option value="耗材">耗材</option>
            </select>
            <input v-model="search" type="search" placeholder="输入名称等信息" aria-label="输入名称等信息" />
            <button class="device-button primary" type="button" @click="page = 1">查询</button>
            <button class="device-button danger" type="button" @click="resetFilters">重置</button>
          </template>
        </div>
      </div>

      <div v-if="isLoading" class="device-loading">
        <AppIcon name="refresh" :size="16" />加载中...
      </div>
      <div v-else-if="loadError" class="device-load-error">
        <span>{{ loadError }}</span>
        <button class="device-button primary" type="button" @click="loadDevices">重试</button>
      </div>
      <div v-else class="device-table-wrap">
        <table class="device-table">
          <thead>
            <tr>
              <th class="device-select-col">
                <input type="checkbox" :checked="allVisibleSelected" @change="toggleAll" />
              </th>
              <th>序号</th>
              <th>资产名称</th>
              <th>资产类别</th>
              <th>资产编码</th>
              <th>规格说明</th>
              <th>资产状态</th>
              <th>使用人员</th>
              <th>品牌名称</th>
              <th>采购时间</th>
              <th>备注</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(device, index) in pagedDevices" :key="device.id">
              <td class="device-select-col">
                <input type="checkbox" :checked="selectedIds.has(device.id)" @change="toggleDevice(device.id, $event)" />
              </td>
              <td>{{ (page - 1) * pageSize + index + 1 }}</td>
              <td>{{ device.name }}</td>
              <td><span class="device-category-badge">{{ device.category }}</span></td>
              <td>{{ device.code || '-' }}</td>
              <td class="device-spec-cell">{{ device.spec || '-' }}</td>
              <td><span class="device-status-badge" :class="device.status">{{ statusText(device.status) }}</span></td>
              <td>{{ device.user || '-' }}</td>
              <td>{{ device.brand || '-' }}</td>
              <td>{{ device.purchaseTime || '-' }}</td>
              <td>{{ device.remark || '-' }}</td>
              <td>
                <div class="device-row-actions">
                  <button
                    v-if="canUsePageAction('companyDevices', 'edit')"
                    class="device-button primary"
                    type="button"
                    @click="openEditDeviceDialog(device)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="canUsePageAction('companyDevices', 'delete')"
                    class="device-button danger"
                    type="button"
                    @click="confirmDeleteDevice(device)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!pagedDevices.length">
              <td class="device-empty" colspan="12">暂无资产数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="device-pagination">
        <span>共{{ totalPages }}页 {{ filteredDevices.length }}条，已选 {{ selectedDeviceCount }} 条</span>
        <div>
          <button type="button" :disabled="page <= 1" @click="page -= 1">«</button>
          <button class="active" type="button">{{ page }}</button>
          <button type="button" :disabled="page >= totalPages" @click="page += 1">»</button>
        </div>
      </div>
    </article>

    <div v-if="deviceDialog" class="modal-backdrop">
      <form class="device-form-modal" @submit.prevent="saveDeviceDialog">
        <button class="modal-close" type="button" :disabled="isSaving" @click="closeDeviceDialog"><AppIcon name="x" :size="16" /></button>
        <h2>{{ deviceDialog.mode === 'edit' ? '编辑设备' : '添加设备' }}</h2>
        <p v-if="dialogError" class="device-form-error">{{ dialogError }}</p>
        <label :class="{ invalid: formErrors.name }">
          <span>资产名称</span>
          <input v-model="deviceForm.name" autofocus />
          <em v-if="formErrors.name">{{ formErrors.name }}</em>
        </label>
        <label :class="{ invalid: formErrors.category }">
          <span>资产类别</span>
          <input v-model="deviceForm.category" list="device-category-options" />
          <em v-if="formErrors.category">{{ formErrors.category }}</em>
        </label>
        <datalist id="device-category-options">
          <option value="固定资产"></option>
          <option value="耗材"></option>
        </datalist>
        <label><span>资产编码</span><input v-model="deviceForm.code" /></label>
        <label><span>规格说明</span><input v-model="deviceForm.spec" /></label>
        <label>
          <span>资产状态</span>
          <select v-model="deviceForm.status">
            <option value="using">使用中</option>
            <option value="idle">闲置</option>
            <option value="repair">维修中</option>
          </select>
        </label>
        <label><span>使用人员</span><input v-model="deviceForm.user" /></label>
        <label><span>品牌名称</span><input v-model="deviceForm.brand" /></label>
        <label><span>采购时间</span><input v-model="deviceForm.purchaseTime" type="date" /></label>
        <label class="device-form-wide"><span>备注</span><textarea v-model="deviceForm.remark" rows="3"></textarea></label>
        <div class="device-form-actions">
          <button type="button" :disabled="isSaving" @click="closeDeviceDialog">取消</button>
          <button class="primary" type="submit" :disabled="isSaving">{{ isSaving ? '保存中...' : '保存' }}</button>
        </div>
      </form>
    </div>
  </section>
</template>
