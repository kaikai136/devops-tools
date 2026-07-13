<script setup lang="ts">
import { computed } from 'vue';

import AppIcon from '@shared/components/AppIcon.vue';
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
  'toggle-column': [column: HostExportColumnKey, event: Event];
  'toggle-all-columns': [event: Event];
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
  <div class="modal-backdrop" @click.self="emit('close')">
    <article class="host-transfer-modal host-export-modal">
      <button class="modal-close" type="button" @click="emit('close')"><AppIcon name="x" :size="16" /></button>
      <h2>导出实例数据</h2>
      <div class="host-export-body">
        <section class="export-section">
          <span class="export-section-title">需要导出的实例</span>
          <div class="export-scope-grid">
            <label class="export-scope-card" :class="{ active: selectedScope === 'all' }">
              <input v-model="selectedScope" type="radio" value="all" />
              <span>
                <strong>所有实例</strong>
                <em>导出当前主机列表下的所有实例</em>
              </span>
            </label>
            <label class="export-scope-card" :class="{ active: selectedScope === 'selected' }">
              <input v-model="selectedScope" type="radio" value="selected" />
              <span>
                <strong>已选中的实例 {{ props.selectedCount }}</strong>
                <em>导出当前列表中所选中的实例</em>
              </span>
            </label>
          </div>
        </section>

        <section class="export-section">
          <span class="export-section-title">需要导出的数据列</span>
          <div class="export-check-all">
            <input type="checkbox" :checked="props.allColumnsSelected" @change="emit('toggle-all-columns', $event)" />
            <span>全选</span>
          </div>
          <div class="export-column-grid">
            <label v-for="column in props.columns" :key="column.field" class="export-column-option">
              <input type="checkbox" :checked="props.selectedColumns.has(column.field)" @change="emit('toggle-column', column.field, $event)" />
              <span>{{ column.label }}</span>
            </label>
          </div>
        </section>

        <section class="export-section">
          <span class="export-section-title">导出文件格式</span>
          <div class="export-format-row">
            <label class="transfer-radio">
              <input v-model="selectedFormat" type="radio" value="excel" />
              <span>Excel</span>
            </label>
            <label class="transfer-radio">
              <input v-model="selectedFormat" type="radio" value="json" />
              <span>JSON</span>
            </label>
          </div>
        </section>
      </div>
      <div class="modal-actions">
        <button type="button" @click="emit('close')">取消</button>
        <button class="primary" type="button" @click="emit('confirm')">确定</button>
      </div>
    </article>
  </div>
</template>
