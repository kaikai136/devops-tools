<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { useAppContext } from '@app/context';
import { createHostCredential, deleteHostCredential, updateHostCredential } from '../../services/hostManagement';
import type { HostCredential } from '../../types';
import AppIcon from '@shared/components/AppIcon.vue';

interface CredentialForm {
  name: string;
  username: string;
  password: string;
  privateKeyName: string;
  privateKey: string;
  remark: string;
}

const {
  activeTool,
  hostCredentials,
  loadHostCredentials,
  replaceHostCredential,
  removeHostCredential,
  canUsePageAction,
  canUseAnyPageAction,
} = useAppContext();

const credentials = hostCredentials;
const search = ref('');
const isLoading = ref(false);
const message = ref('');
const dialog = ref<{ mode: 'create' | 'edit'; credentialId: number | null } | null>(null);
const confirmDelete = ref<HostCredential | null>(null);
const form = ref<CredentialForm>(emptyForm());
const fullscreen = ref(false);

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
    await loadHostCredentials();
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
        ? await updateHostCredential(dialog.value.credentialId, payload)
        : await createHostCredential(payload);
    replaceHostCredential(saved);
    dialog.value = null;
  } catch (error) {
    message.value = (error as Error).message;
  }
}

async function uploadPrivateKey(uploadFile: { raw?: File }) {
  const file = uploadFile.raw;
  if (!file) return;
  form.value.privateKeyName = file.name;
  form.value.privateKey = await file.text();
}

async function deleteCredential() {
  if (!confirmDelete.value) return;
  message.value = '';
  try {
    const targetId = confirmDelete.value.id;
    await deleteHostCredential(targetId);
    removeHostCredential(targetId);
    confirmDelete.value = null;
  } catch (error) {
    message.value = (error as Error).message;
  }
}

function emptyForm(): CredentialForm {
  return {
    name: '',
    username: '',
    password: '',
    privateKeyName: '',
    privateKey: '',
    remark: '',
  };
}
</script>

<template>
  <section v-if="activeTool === 'accounts'" class="account-page" :class="{ fullscreen }">
    <template v-if="canUseAnyPageAction('accounts', ['create', 'edit', 'delete'])">
    <article class="panel account-panel">
      <div class="account-toolbar">
        <NativeInput v-model="search" placeholder="输入账号名称/用户/备注搜索" class="account-toolbar-search" clearable />
        <div class="account-toolbar-actions">
          <NativeButton v-if="canUsePageAction('accounts', 'create')" type="primary" @click="openCreateDialog"><AppIcon name="plus" :size="16" />新增账号</NativeButton>
          <NativeButton title="刷新" aria-label="刷新" @click="loadCredentials"><AppIcon name="refresh" :size="16" /></NativeButton>
          <NativeButton :title="fullscreen ? '退出全屏' : '全屏'" :aria-label="fullscreen ? '退出全屏' : '全屏'" @click="fullscreen = !fullscreen">
            <AppIcon :name="fullscreen ? 'minimize' : 'maximize'" :size="18" />
          </NativeButton>
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
        <NativeTable :data="filteredCredentials" row-key="id" class="account-table" empty-text="没有匹配的账号">
          <NativeTableColumn label="账号名称" min-width="150">
            <template #default="{ row }">
              <div class="account-name">
                <strong>{{ row.name }}</strong>
                <span>ID {{ row.id }}</span>
              </div>
            </template>
          </NativeTableColumn>
          <NativeTableColumn prop="username" label="用户" min-width="120" />
          <NativeTableColumn label="密码" min-width="100">
            <template #default="{ row }">
              <NativeTag :type="row.password ? 'success' : 'warning'" size="small" effect="dark">{{ row.password ? '已保存' : '未设置' }}</NativeTag>
            </template>
          </NativeTableColumn>
          <NativeTableColumn label="独立密钥" min-width="150">
            <template #default="{ row }">
              <NativeTag :type="row.privateKey ? 'primary' : 'info'" size="small" effect="dark">{{ row.privateKeyName || '未上传' }}</NativeTag>
            </template>
          </NativeTableColumn>
          <NativeTableColumn label="备注" min-width="170">
            <template #default="{ row }">{{ row.remark || '无备注' }}</template>
          </NativeTableColumn>
          <NativeTableColumn label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <div class="account-actions">
                <NativeButton v-if="canUsePageAction('accounts', 'edit')" type="primary" size="small" @click="openEditDialog(row)">编辑</NativeButton>
                <NativeButton v-if="canUsePageAction('accounts', 'delete')" type="danger" size="small" @click="confirmDelete = row">删除</NativeButton>
                <span v-if="!canUseAnyPageAction('accounts', ['edit', 'delete'])" class="permission-placeholder">-</span>
              </div>
            </template>
          </NativeTableColumn>
        </NativeTable>
      </div>
    </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>

    <NativeDialog
      :model-value="dialog !== null"
      :title="dialog?.mode === 'edit' ? '编辑账号' : '新增账号'"
      width="560px"
      :close-on-click-modal="false"
      @update:model-value="(visible) => { if (!visible) dialog = null; }"
    >
      <NativeForm :model="form" label-position="left" label-width="92px">
        <NativeFormItem label="账号名称" required>
          <NativeInput v-model="form.name" autofocus />
        </NativeFormItem>
        <NativeFormItem label="用户" required>
          <NativeInput v-model="form.username" />
        </NativeFormItem>
        <NativeFormItem label="密码">
          <NativeInput v-model="form.password" type="password" autocomplete="new-password" />
        </NativeFormItem>
        <NativeFormItem label="独立密钥">
          <div class="account-key-upload">
            <NativeUpload :auto-upload="false" :show-file-list="false" :on-change="uploadPrivateKey">
              <NativeButton>点击上传</NativeButton>
            </NativeUpload>
            <em>{{ form.privateKeyName || '未上传独立密钥' }}</em>
          </div>
        </NativeFormItem>
        <NativeFormItem label="备注信息">
          <NativeInput v-model="form.remark" type="textarea" :rows="3" />
        </NativeFormItem>
        <p v-if="message" class="account-message">{{ message }}</p>
      </NativeForm>
      <template #footer>
        <NativeButton @click="dialog = null">取消</NativeButton>
        <NativeButton type="primary" @click="saveCredential">保存</NativeButton>
      </template>
    </NativeDialog>

    <NativeDialog
      :model-value="confirmDelete !== null"
      title="删除账号"
      width="420px"
      :close-on-click-modal="false"
      @update:model-value="(visible) => { if (!visible) confirmDelete = null; }"
    >
      <p>确定删除账号「{{ confirmDelete?.name }}」吗？</p>
      <template #footer>
        <NativeButton @click="confirmDelete = null">取消</NativeButton>
        <NativeButton type="danger" @click="deleteCredential">确定删除</NativeButton>
      </template>
    </NativeDialog>
  </section>
</template>
