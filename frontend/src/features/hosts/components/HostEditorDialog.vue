<script setup lang="ts">
import { computed, ref } from 'vue';

import type { HostCredential } from '@features/hosts/types';
import type { HostFormErrors, ManagedHostForm } from '@features/hosts/composables/useHostEditor';
import type { HostGroupRoot } from '@features/hosts/composables/useHostGroups';
import type { FlatHostGroup } from '@features/hosts/utils/groups';
import CredentialSelector from './CredentialSelector.vue';

const props = defineProps<{
  dialog: { mode: 'create' | 'edit'; hostId: number | null } | null;
  form: ManagedHostForm;
  errors: HostFormErrors;
  root: HostGroupRoot;
  groups: FlatHostGroup[];
  credentials: HostCredential[];
}>();

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'submit'): void;
  <Key extends keyof ManagedHostForm>(
    event: 'update-form-field',
    field: Key,
    value: ManagedHostForm[Key],
  ): void;
  (event: 'apply-credential', payload: number | null): void;
  (event: 'upload-private-key', payload: Event): void;
}>();

function fieldModel<Key extends keyof ManagedHostForm>(field: Key) {
  return computed({
    get: () => props.form[field],
    set: (value: ManagedHostForm[Key]) => emit('update-form-field', field, value),
  });
}

const group = fieldModel('group');
const name = fieldModel('name');
const privateIp = fieldModel('privateIp');
const os = fieldModel('os');
const port = fieldModel('port');
const loginUser = fieldModel('loginUser');
const loginPassword = fieldModel('loginPassword');
const remark = fieldModel('remark');
const privateKeyInput = ref<HTMLInputElement | null>(null);

function triggerPrivateKeyUpload() {
  privateKeyInput.value?.click();
}
</script>

<template>
  <NativeDialog
    v-if="props.dialog"
    class="host-editor-dialog"
    :model-value="Boolean(props.dialog)"
    :title="props.dialog.mode === 'edit' ? '编辑主机' : '新增主机'"
    width="760px"
    @close="emit('close')"
  >
    <form id="host-editor-form" class="host-form-modal host-editor-form" @submit.prevent="emit('submit')">
      <label class="host-horizontal-field required host-editor-span-2">
        <span>主机分组：</span>
        <NativeSelect v-model="group" :class="{ invalid: props.errors.group }">
          <NativeOption disabled :value="null" :label="props.root.label" />
          <NativeOption
            v-for="hostGroup in props.groups"
            :key="hostGroup.key"
            :value="hostGroup.key"
            :label="`${'　'.repeat(hostGroup.level)}${hostGroup.label}`"
          />
        </NativeSelect>
        <p v-if="props.errors.group" class="host-field-error">{{ props.errors.group }}</p>
      </label>
      <label class="host-horizontal-field required">
        <span>节点：</span>
        <NativeInput v-model="name" :class="{ invalid: props.errors.name }" autofocus />
        <p v-if="props.errors.name" class="host-field-error">{{ props.errors.name }}</p>
      </label>
      <label class="host-horizontal-field required">
        <span>主机 IP：</span>
        <NativeInput v-model="privateIp" :class="{ invalid: props.errors.privateIp }" />
        <p v-if="props.errors.privateIp" class="host-field-error">{{ props.errors.privateIp }}</p>
      </label>
      <label class="host-horizontal-field required">
        <span>平台类型：</span>
        <NativeSelect v-model="os" :class="{ invalid: props.errors.os }">
          <NativeOption disabled value="" label="请选择平台类型" />
          <NativeOption value="centos" label="linux" />
          <NativeOption value="windows" label="windows" />
        </NativeSelect>
        <p v-if="props.errors.os" class="host-field-error">{{ props.errors.os }}</p>
      </label>
      <label class="host-horizontal-field">
        <span>端口：</span>
        <NativeNumberInput v-model="port" :min="1" :max="65535" :class="{ invalid: props.errors.port }" />
        <p v-if="props.errors.port" class="host-field-error">{{ props.errors.port }}</p>
      </label>
      <label class="host-horizontal-field host-editor-span-2">
        <span>账号：</span>
        <CredentialSelector
          :model-value="props.form.credential"
          :credentials="props.credentials"
          @update:model-value="emit('update-form-field', 'credential', $event)"
          @change="emit('apply-credential', $event)"
        />
      </label>
      <label class="host-horizontal-field">
        <span>用户：</span>
        <NativeInput v-model="loginUser" />
      </label>
      <label class="host-horizontal-field">
        <span>密码：</span>
        <NativeInput v-model="loginPassword" type="password" autocomplete="new-password" show-password />
      </label>
      <div class="host-horizontal-field host-editor-span-2">
        <span>独立密钥：</span>
        <div class="host-key-upload">
          <input ref="privateKeyInput" hidden type="file" @change="emit('upload-private-key', $event)" />
          <NativeButton class="host-key-button" native-type="button" @click="triggerPrivateKeyUpload">点击上传</NativeButton>
          <em>{{ props.form.privateKeyName || '默认使用全局密钥，如果上传了独立密钥（私钥）则优先使用该密钥。' }}</em>
        </div>
      </div>
      <label class="host-horizontal-field host-editor-span-2">
        <span>备注信息：</span>
        <NativeInput v-model="remark" type="textarea" :rows="3" />
      </label>
    </form>

    <template #footer>
      <div class="host-form-actions host-editor-actions">
        <NativeButton @click="emit('close')">取消</NativeButton>
        <NativeButton form="host-editor-form" class="primary" native-type="submit" type="primary">保存</NativeButton>
      </div>
    </template>
  </NativeDialog>
</template>
