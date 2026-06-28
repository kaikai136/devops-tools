<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import { useAppContext } from '../../appContext';
import type { HostCredential } from '../../types';
import AppIcon from '../common/AppIcon.vue';

interface CredentialForm {
  name: string;
  username: string;
  password: string;
  port: number;
  privateKeyName: string;
  privateKey: string;
  remark: string;
}

const { activeTool, canUsePageAction } = useAppContext();

const credentials = ref<HostCredential[]>([]);
const search = ref('');
const isLoading = ref(false);
const message = ref('');
const dialog = ref<{ mode: 'create' | 'edit'; credentialId: number | null } | null>(null);
const confirmDelete = ref<HostCredential | null>(null);
const form = ref<CredentialForm>(emptyForm());

const filteredCredentials = computed(() => {
  const query = search.value.trim().toLowerCase();
  return credentials.value.filter((item) =>
    !query || [item.name, item.username, item.remark].filter(Boolean).some((value) => String(value).toLowerCase().includes(query)),
  );
});

const stats = computed(() => ({
  total: credentials.value.length,
  withPassword: credentials.value.filter((item) => item.password).length,
  withKey: credentials.value.filter((item) => item.privateKey).length,
}));

onMounted(loadCredentials);

async function loadCredentials() {
  isLoading.value = true;
  message.value = '';
  try {
    credentials.value = await apiGet<HostCredential[]>('/api/host-management/accounts/');
  } catch (error) {
    message.value = (error as Error).message;
  } finally {
    isLoading.value = false;
  }
}

function openCreateDialog() {
  form.value = emptyForm();
  dialog.value = { mode: 'create', credentialId: null };
}

function openEditDialog(credential: HostCredential) {
  form.value = {
    name: credential.name,
    username: credential.username,
    password: credential.password,
    port: credential.port,
    privateKeyName: credential.privateKeyName,
    privateKey: credential.privateKey,
    remark: credential.remark,
  };
  dialog.value = { mode: 'edit', credentialId: credential.id };
}

async function saveCredential() {
  message.value = '';
  const payload = {
    name: form.value.name.trim(),
    username: form.value.username.trim(),
    password: form.value.password.trim(),
    port: form.value.port || 22,
    privateKeyName: form.value.privateKeyName.trim(),
    privateKey: form.value.privateKey.trim(),
    remark: form.value.remark.trim(),
  };

  if (!payload.name || !payload.username) {
    message.value = '请输入账号名称和用户';
    return;
  }

  try {
    const saved =
      dialog.value?.mode === 'edit' && dialog.value.credentialId
        ? await apiPut<HostCredential>(`/api/host-management/accounts/${dialog.value.credentialId}/`, payload)
        : await apiPost<HostCredential>('/api/host-management/accounts/', payload);
    replaceCredential(saved);
    dialog.value = null;
  } catch (error) {
    message.value = (error as Error).message;
  }
}

async function uploadPrivateKey(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  form.value.privateKeyName = file.name;
  form.value.privateKey = await file.text();
  input.value = '';
}

async function deleteCredential() {
  if (!confirmDelete.value) return;
  message.value = '';
  try {
    const targetId = confirmDelete.value.id;
    await apiDelete(`/api/host-management/accounts/${targetId}/`);
    credentials.value = credentials.value.filter((item) => item.id !== targetId);
    confirmDelete.value = null;
  } catch (error) {
    message.value = (error as Error).message;
  }
}

function replaceCredential(credential: HostCredential) {
  const index = credentials.value.findIndex((item) => item.id === credential.id);
  if (index >= 0) {
    credentials.value.splice(index, 1, credential);
  } else {
    credentials.value.push(credential);
  }
}

function emptyForm(): CredentialForm {
  return {
    name: '',
    username: '',
    password: '',
    port: 22,
    privateKeyName: '',
    privateKey: '',
    remark: '',
  };
}
</script>

<template>
  <section v-if="activeTool === 'accounts'" class="account-page">
    <article class="panel account-panel">
      <div class="account-toolbar">
        <input v-model="search" placeholder="输入账号名称/用户/备注搜索" />
        <div class="account-toolbar-actions">
          <button class="primary" type="button" :disabled="!canUsePageAction('accounts', 'create')" @click="openCreateDialog"><AppIcon name="plus" :size="16" />新增账号</button>
          <button class="icon-only" type="button" title="刷新" aria-label="刷新" @click="loadCredentials"><AppIcon name="refresh" :size="16" /></button>
        </div>
      </div>

      <div class="account-stats-line">
        <span>共 {{ stats.total }} 个账号</span>
        <span>密码 {{ stats.withPassword }}</span>
        <span>密钥 {{ stats.withKey }}</span>
        <span v-if="isLoading">加载中</span>
      </div>
      <p v-if="message" class="account-message">{{ message }}</p>

      <div class="account-table">
        <div class="account-table-row head credential-row">
          <span>账号名称</span>
          <span>用户</span>
          <span>端口</span>
          <span>密码</span>
          <span>独立密钥</span>
          <span>备注</span>
          <span>操作</span>
        </div>
        <div v-for="credential in filteredCredentials" :key="credential.id" class="account-table-row credential-row">
          <div class="account-name">
            <strong>{{ credential.name }}</strong>
            <span>ID {{ credential.id }}</span>
          </div>
          <strong>{{ credential.username }}</strong>
          <span>{{ credential.port }}</span>
          <span class="account-status" :class="{ active: credential.password }">{{ credential.password ? '已保存' : '未设置' }}</span>
          <span class="account-role" :class="{ staff: credential.privateKey }">{{ credential.privateKeyName || '未上传' }}</span>
          <span class="account-date">{{ credential.remark || '无备注' }}</span>
          <div class="account-actions">
            <button type="button" :disabled="!canUsePageAction('accounts', 'edit')" @click="openEditDialog(credential)">编辑</button>
            <button class="danger" type="button" :disabled="!canUsePageAction('accounts', 'delete')" @click="confirmDelete = credential">删除</button>
          </div>
        </div>
        <div v-if="!filteredCredentials.length" class="empty-state account-empty">没有匹配的账号。</div>
      </div>
    </article>

    <div v-if="dialog" class="modal-backdrop" @click.self="dialog = null">
      <form class="account-form-modal account-horizontal-modal" @submit.prevent="saveCredential">
        <button class="modal-close" type="button" @click="dialog = null"><AppIcon name="x" :size="16" /></button>
        <h2>{{ dialog.mode === 'edit' ? '编辑账号' : '新增账号' }}</h2>
        <label class="account-horizontal-field required">
          <span>账号名称：</span>
          <input v-model="form.name" autofocus />
        </label>
        <label class="account-horizontal-field required">
          <span>用户：</span>
          <input v-model="form.username" />
        </label>
        <label class="account-horizontal-field">
          <span>端口：</span>
          <input v-model.number="form.port" min="1" max="65535" type="number" />
        </label>
        <label class="account-horizontal-field">
          <span>密码：</span>
          <input v-model="form.password" type="password" autocomplete="new-password" />
        </label>
        <div class="account-horizontal-field">
          <span>独立密钥：</span>
          <div class="account-key-upload">
            <label class="account-key-button">
              <input type="file" @change="uploadPrivateKey" />
              点击上传
            </label>
            <em>{{ form.privateKeyName || '未上传独立密钥' }}</em>
          </div>
        </div>
        <label class="account-horizontal-field">
          <span>备注信息：</span>
          <textarea v-model="form.remark" rows="3"></textarea>
        </label>
        <p v-if="message" class="account-message">{{ message }}</p>
        <div class="host-form-actions">
          <button type="button" @click="dialog = null">取消</button>
          <button class="primary" type="submit">保存</button>
        </div>
      </form>
    </div>

    <div v-if="confirmDelete" class="modal-backdrop" @click.self="confirmDelete = null">
      <article class="account-confirm-modal">
        <button class="modal-close" type="button" @click="confirmDelete = null"><AppIcon name="x" :size="16" /></button>
        <h2>删除账号</h2>
        <p>确定删除账号「{{ confirmDelete.name }}」吗？</p>
        <div class="host-form-actions">
          <button type="button" @click="confirmDelete = null">取消</button>
          <button class="danger" type="button" @click="deleteCredential">确定删除</button>
        </div>
      </article>
    </div>
  </section>
</template>
