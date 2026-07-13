<script setup lang="ts">
import { computed } from 'vue';

import AppIcon from '@shared/components/AppIcon.vue';
import type { ManagedHost } from '@features/hosts/types';
import type { HostMoveForm } from '@features/hosts/composables/useHostEditor';
import type { HostGroupRoot } from '@features/hosts/composables/useHostGroups';
import type { FlatHostGroup } from '@features/hosts/utils/groups';

const props = defineProps<{
  open: boolean;
  mode: 'single' | 'selected';
  form: HostMoveForm;
  hosts: ManagedHost[];
  root: HostGroupRoot;
  groups: FlatHostGroup[];
  selectedCount: number;
}>();

const emit = defineEmits<{
  close: [];
  submit: [];
  'update-form-field': [field: keyof HostMoveForm, value: number | null];
}>();

const hostId = computed({
  get: () => props.form.hostId,
  set: (value) => emit('update-form-field', 'hostId', value),
});
const targetGroup = computed({
  get: () => props.form.targetGroup,
  set: (value) => emit('update-form-field', 'targetGroup', value),
});
</script>

<template>
  <div v-if="props.open" class="modal-backdrop" @click.self="emit('close')">
    <form class="host-form-modal" @submit.prevent="emit('submit')">
      <button class="modal-close" type="button" @click="emit('close')"><AppIcon name="x" :size="16" /></button>
      <h2>{{ props.mode === 'selected' ? '更新所选' : '移动主机' }}</h2>
      <p v-if="props.mode === 'selected'" class="host-move-hint">仅支持更换主机分组，已选择 {{ props.selectedCount }} 台主机。</p>
      <label v-if="props.mode === 'single'">
        <span>选择主机</span>
        <select v-model.number="hostId">
          <option v-for="host in props.hosts" :key="host.id" :value="host.id">{{ host.name }} · {{ host.privateIp }}</option>
        </select>
      </label>
      <label>
        <span>目标分组</span>
        <select v-model.number="targetGroup">
          <option disabled :value="null">{{ props.root.label }}</option>
          <option v-for="group in props.groups" :key="group.key" :value="group.key">{{ `${'　'.repeat(group.level)}${group.label}` }}</option>
        </select>
      </label>
      <div class="host-form-actions">
        <button type="button" @click="emit('close')">取消</button>
        <button class="primary" type="submit">{{ props.mode === 'selected' ? '更新' : '移动' }}</button>
      </div>
    </form>
  </div>
</template>
