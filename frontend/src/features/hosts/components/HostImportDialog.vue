<script setup lang="ts">
import { computed } from 'vue';

import AppIcon from '@shared/components/AppIcon.vue';
import type { HostTransferFormat } from '@features/hosts/types';

const props = defineProps<{
  format: HostTransferFormat;
}>();

const emit = defineEmits<{
  close: [];
  confirm: [];
  'update:format': [format: HostTransferFormat];
}>();

const selectedFormat = computed({
  get: () => props.format,
  set: (value) => emit('update:format', value),
});
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <article class="host-transfer-modal">
      <button class="modal-close" type="button" @click="emit('close')"><AppIcon name="x" :size="16" /></button>
      <h2>导入</h2>
      <div class="host-transfer-body">
        <div class="transfer-row">
          <span class="transfer-label">文件类型</span>
          <label class="transfer-radio">
            <input v-model="selectedFormat" type="radio" value="json" />
            <span>JSON</span>
          </label>
          <label class="transfer-radio">
            <input v-model="selectedFormat" type="radio" value="excel" />
            <span>Excel</span>
          </label>
        </div>
      </div>
      <div class="modal-actions">
        <button type="button" @click="emit('close')">取消</button>
        <button class="primary" type="button" @click="emit('confirm')">确定</button>
      </div>
    </article>
  </div>
</template>
