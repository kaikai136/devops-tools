<script setup lang="ts">
import { computed } from 'vue';

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
  <NativeDialog :model-value="props.open" class="host-form-modal" :title="props.mode === 'selected' ? '更新所选' : '移动主机'" width="520px" @close="emit('close')">
    <form @submit.prevent="emit('submit')">
      <h2>{{ props.mode === 'selected' ? '更新所选' : '移动主机' }}</h2>
      <p v-if="props.mode === 'selected'" class="host-move-hint">仅支持更换主机分组，已选择 {{ props.selectedCount }} 台主机。</p>
      <label v-if="props.mode === 'single'">
        <span>选择主机</span>
        <NativeSelect v-model="hostId">
          <NativeOption v-for="host in props.hosts" :key="host.id" :value="host.id" :label="`${host.name} · ${host.privateIp}`" />
        </NativeSelect>
      </label>
      <label>
        <span>目标分组</span>
        <NativeSelect v-model="targetGroup">
          <NativeOption disabled :value="null" :label="props.root.label" />
          <NativeOption v-for="group in props.groups" :key="group.key" :value="group.key" :label="`${'　'.repeat(group.level)}${group.label}`" />
        </NativeSelect>
      </label>
      <div class="host-form-actions">
        <NativeButton @click="emit('close')">取消</NativeButton>
        <NativeButton class="primary" native-type="submit" type="primary">{{ props.mode === 'selected' ? '更新' : '移动' }}</NativeButton>
      </div>
    </form>
  </NativeDialog>
</template>
