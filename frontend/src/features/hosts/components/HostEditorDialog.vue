<script setup lang="ts">
import { computed } from 'vue';

import AppIcon from '@shared/components/AppIcon.vue';
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
  close: [];
  submit: [];
  'update-form-field': [field: keyof ManagedHostForm, value: ManagedHostForm[keyof ManagedHostForm]];
  'apply-credential': [event: Event];
  'upload-private-key': [event: Event];
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
</script>

<template>
  <div v-if="props.dialog" class="modal-backdrop" @click.self="emit('close')">
    <form class="host-form-modal host-edit-modal host-horizontal-modal" @submit.prevent="emit('submit')">
      <button class="modal-close" type="button" @click="emit('close')"><AppIcon name="x" :size="16" /></button>
      <h2>{{ props.dialog.mode === 'edit' ? '编辑主机' : '新增主机' }}</h2>
      <label class="host-horizontal-field required">
        <span>主机分组：</span>
        <select v-model.number="group" :class="{ invalid: props.errors.group }">
          <option disabled :value="null">{{ props.root.label }}</option>
          <option v-for="hostGroup in props.groups" :key="hostGroup.key" :value="hostGroup.key">{{ `${'　'.repeat(hostGroup.level)}${hostGroup.label}` }}</option>
        </select>
        <p v-if="props.errors.group" class="host-field-error">{{ props.errors.group }}</p>
      </label>
      <label class="host-horizontal-field required">
        <span>节点：</span>
        <input v-model="name" :class="{ invalid: props.errors.name }" autofocus />
        <p v-if="props.errors.name" class="host-field-error">{{ props.errors.name }}</p>
      </label>
      <label class="host-horizontal-field required">
        <span>主机 IP：</span>
        <input v-model="privateIp" :class="{ invalid: props.errors.privateIp }" />
        <p v-if="props.errors.privateIp" class="host-field-error">{{ props.errors.privateIp }}</p>
      </label>
      <label class="host-horizontal-field required">
        <span>平台类型：</span>
        <select v-model="os" :class="{ invalid: props.errors.os }">
          <option disabled value="">请选择平台类型</option>
          <option value="centos">linux</option>
          <option value="windows">windows</option>
        </select>
        <p v-if="props.errors.os" class="host-field-error">{{ props.errors.os }}</p>
      </label>
      <label class="host-horizontal-field">
        <span>端口：</span>
        <input v-model.number="port" min="1" max="65535" type="number" :class="{ invalid: props.errors.port }" />
        <p v-if="props.errors.port" class="host-field-error">{{ props.errors.port }}</p>
      </label>
      <label class="host-horizontal-field">
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
        <input v-model="loginUser" />
      </label>
      <label class="host-horizontal-field">
        <span>密码：</span>
        <input v-model="loginPassword" type="password" autocomplete="new-password" />
      </label>
      <div class="host-horizontal-field">
        <span>独立密钥：</span>
        <div class="host-key-upload">
          <label class="host-key-button">
            <input type="file" @change="emit('upload-private-key', $event)" />
            点击上传
          </label>
          <em>{{ props.form.privateKeyName || '默认使用全局密钥，如果上传了独立密钥（私钥）则优先使用该密钥。' }}</em>
        </div>
      </div>
      <label class="host-horizontal-field">
        <span>备注信息：</span>
        <textarea v-model="remark" rows="3"></textarea>
      </label>
      <div class="host-form-actions">
        <button type="button" @click="emit('close')">取消</button>
        <button class="primary" type="submit">保存</button>
      </div>
    </form>
  </div>
</template>
