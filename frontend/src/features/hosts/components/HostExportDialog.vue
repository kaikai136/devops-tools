<script setup lang="ts">
import { computed } from 'vue';

import type {
  HostExportColumnKey,
  HostExportColumnOption,
  HostExportScope,
  HostTransferFormat,
} from '@features/hosts/types';

const props = defineProps<{
  scope: HostExportScope;
  format: HostTransferFormat;
  columns: readonly HostExportColumnOption[];
  selectedColumns: Set<HostExportColumnKey>;
  allColumnsSelected: boolean;
  selectedCount: number;
}>();

const emit = defineEmits<{
  close: [];
  confirm: [];
  'update:scope': [scope: HostExportScope];
  'update:format': [format: HostTransferFormat];
  'toggle-column': [column: HostExportColumnKey, value: boolean | string | number];
  'toggle-all-columns': [value: boolean | string | number];
}>();

const selectedScope = computed({
  get: () => props.scope,
  set: (value) => emit('update:scope', value),
});
const selectedFormat = computed({
  get: () => props.format,
  set: (value) => emit('update:format', value),
});
</script>

<template>
  <NativeDialog class="host-transfer-modal host-export-modal" :model-value="true" title="导出实例数据" width="720px" @close="emit('close')">
      <h2>导出实例数据</h2>
      <div class="host-export-body">
        <section class="export-section">
          <span class="export-section-title">需要导出的实例</span>
          <NativeRadioGroup v-model="selectedScope" class="export-scope-grid">
            <NativeRadioButton value="all" class="export-scope-card" :class="{ active: selectedScope === 'all' }">
              <span>
                <strong>所有实例</strong>
                <em>导出当前主机列表下的所有实例</em>
              </span>
            </NativeRadioButton>
            <NativeRadioButton value="selected" class="export-scope-card" :class="{ active: selectedScope === 'selected' }">
              <span>
                <strong>已选中的实例 {{ props.selectedCount }}</strong>
                <em>导出当前列表中所选中的实例</em>
              </span>
            </NativeRadioButton>
          </NativeRadioGroup>
        </section>

        <section class="export-section">
          <span class="export-section-title">需要导出的数据列</span>
          <NativeCheckbox class="export-check-all" :model-value="props.allColumnsSelected" @change="emit('toggle-all-columns', $event)">全选</NativeCheckbox>
          <div class="export-column-grid">
            <NativeCheckbox v-for="column in props.columns" :key="column.field" class="export-column-option" :model-value="props.selectedColumns.has(column.field)" @change="emit('toggle-column', column.field, $event)">
              <span>{{ column.label }}</span>
            </NativeCheckbox>
          </div>
        </section>

        <section class="export-section">
          <span class="export-section-title">导出文件格式</span>
          <NativeRadioGroup v-model="selectedFormat" class="export-format-row">
            <NativeRadioButton value="excel">Excel</NativeRadioButton>
            <NativeRadioButton value="json">JSON</NativeRadioButton>
          </NativeRadioGroup>
        </section>
      </div>
      <template #footer>
        <div class="modal-actions">
          <NativeButton @click="emit('close')">取消</NativeButton>
          <NativeButton class="primary" type="primary" @click="emit('confirm')">确定</NativeButton>
        </div>
      </template>
  </NativeDialog>
</template>
