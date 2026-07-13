<script setup lang="ts">
import { computed } from 'vue';

import type { HostCredential } from '@features/hosts/types';

const props = defineProps<{
  credentials: HostCredential[];
  modelValue: number | null;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: number | null];
  change: [event: Event];
}>();

const selectedCredential = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});
</script>

<template>
  <select v-model.number="selectedCredential" @change="emit('change', $event)">
    <option :value="null">手动输入</option>
    <option v-for="credential in props.credentials" :key="credential.id" :value="credential.id">
      {{ credential.name }}（{{ credential.username }}）
    </option>
  </select>
</template>
