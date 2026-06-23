<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import { useAppContext } from '../../appContext';
import { navGroups } from '../../navigation';
import { errorMessage } from '../../utils/errors';
import AppIcon from '../common/AppIcon.vue';

interface SystemRole {
  id: number;
  name: string;
  permissionIds: number[];
}

interface SystemPermission {
  id: number;
  codename: string;
  label: string;
  featureKey: string;
  isFeature: boolean;
}

type RoleDialogMode = 'create' | 'edit' | 'view' | 'permissions';

interface RoleForm {
  name: string;
  permissionIds: number[];
}

const { activeTool } = useAppContext();

const roles = ref<SystemRole[]>([]);
const permissions = ref<SystemPermission[]>([]);
const searchDraft = ref('');
const search = ref('');
const page = ref(1);
const pageSize = ref(10);
const isLoading = ref(false);
const message = ref('');
const messageTone = ref<'error' | 'success'>('error');
const columnsOpen = ref(false);
const dialog = ref<{ mode: RoleDialogMode; role: SystemRole | null } | null>(null);
const deleteTarget = ref<SystemRole | null>(null);
const form = ref<RoleForm>(emptyRoleForm());

const filteredRoles = computed(() => {
  const query = search.value.trim().toLowerCase();
  if (!query) return roles.value;
  return roles.value.filter((role) => [role.name, roleCode(role)].some((value) => value.toLowerCase().includes(query)));
});

const featurePermissions = computed(() => permissions.value.filter((permission) => permission.isFeature && permission.featureKey));
const permissionByFeatureKey = computed(() => new Map(featurePermissions.value.map((permission) => [permission.featureKey, permission])));
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRoles.value.length / pageSize.value)));
const pagedRoles = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredRoles.value.slice(start, start + pageSize.value);
});

onMounted(loadRoles);

watch([search, pageSize], () => {
  page.value = 1;
});

watch(totalPages, (next) => {
  if (page.value > next) page.value = next;
});

async function loadRoles() {
  isLoading.value = true;
  clearMessage();
  try {
    const [roleData, permissionData] = await Promise.all([
      apiGet<SystemRole[]>('/api/system/roles/'),
      apiGet<SystemPermission[]>('/api/system/permissions/'),
    ]);
    roles.value = roleData;
    permissions.value = permissionData;
  } catch (error) {
    roles.value = [];
    permissions.value = [];
    setError(errorMessage(error));
  } finally {
    isLoading.value = false;
  }
}

function runSearch() {
  search.value = searchDraft.value.trim();
}

function resetSearch() {
  searchDraft.value = '';
  search.value = '';
}

function openCreateDialog() {
  clearMessage();
  form.value = emptyRoleForm();
  dialog.value = { mode: 'create', role: null };
}

function openViewDialog(role: SystemRole) {
  form.value = { name: role.name, permissionIds: roleFeaturePermissionIds(role) };
  dialog.value = { mode: 'view', role };
}

function openEditDialog(role: SystemRole) {
  clearMessage();
  form.value = { name: role.name, permissionIds: roleFeaturePermissionIds(role) };
  dialog.value = { mode: 'edit', role };
}

function openPermissionDialog(role: SystemRole) {
  clearMessage();
  form.value = { name: role.name, permissionIds: roleFeaturePermissionIds(role) };
  dialog.value = { mode: 'permissions', role };
}

async function saveRole() {
  const currentDialog = dialog.value;
  if (!currentDialog || currentDialog.mode === 'view') return;
  clearMessage();
  const payload = {
    name: form.value.name.trim(),
    permissionIds: form.value.permissionIds,
  };
  if (!payload.name) {
    setError('请输入角色名称');
    return;
  }

  try {
    const saved =
      currentDialog.mode === 'create'
        ? await apiPost<SystemRole>('/api/system/roles/', payload)
        : await apiPut<SystemRole>(`/api/system/roles/${currentDialog.role?.id}/`, payload);
    replaceRole(saved);
    dialog.value = null;
    setSuccess(currentDialog.mode === 'permissions' ? '权限已保存' : '角色已保存');
  } catch (error) {
    setError(errorMessage(error));
  }
}

async function deleteRole() {
  if (!deleteTarget.value) return;
  clearMessage();
  try {
    const roleId = deleteTarget.value.id;
    await apiDelete(`/api/system/roles/${roleId}/`);
    roles.value = roles.value.filter((role) => role.id !== roleId);
    deleteTarget.value = null;
    setSuccess('角色已删除');
  } catch (error) {
    setError(errorMessage(error));
  }
}

function isFeatureChecked(featureKey: string) {
  const permission = permissionByFeatureKey.value.get(featureKey);
  return Boolean(permission && form.value.permissionIds.includes(permission.id));
}

function setFeatureChecked(featureKey: string, checked: boolean) {
  const permission = permissionByFeatureKey.value.get(featureKey);
  if (!permission) return;
  const next = new Set(form.value.permissionIds);
  if (checked) {
    next.add(permission.id);
  } else {
    next.delete(permission.id);
  }
  form.value.permissionIds = [...next].sort((a, b) => a - b);
}

function toggleFeature(featureKey: string, event: Event) {
  setFeatureChecked(featureKey, (event.target as HTMLInputElement).checked);
}

function groupFeatureKeys(groupKey: string) {
  return navGroups.find((group) => group.key === groupKey)?.items.map((item) => item.key) ?? [];
}

function isGroupChecked(groupKey: string) {
  const keys = groupFeatureKeys(groupKey);
  return keys.length > 0 && keys.every((key) => isFeatureChecked(key));
}

function isGroupPartial(groupKey: string) {
  const keys = groupFeatureKeys(groupKey);
  const checkedCount = keys.filter((key) => isFeatureChecked(key)).length;
  return checkedCount > 0 && checkedCount < keys.length;
}

function toggleGroup(groupKey: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  groupFeatureKeys(groupKey).forEach((featureKey) => setFeatureChecked(featureKey, checked));
}

function setPage(nextPage: number) {
  page.value = Math.min(Math.max(1, nextPage), totalPages.value);
}

function roleCode(role: SystemRole) {
  if (/管理员|admin/i.test(role.name)) return 'admin';
  if (/普通|用户|user/i.test(role.name)) return 'user';
  const normalized = role.name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
  return normalized || `role-${role.id}`;
}

function permissionText(role: SystemRole) {
  return `${roleFeaturePermissionIds(role).length} 项功能`;
}

function roleFeaturePermissionIds(role: SystemRole) {
  const featureIds = new Set(featurePermissions.value.map((permission) => permission.id));
  return role.permissionIds.filter((permissionId) => featureIds.has(permissionId));
}

function dialogTitle() {
  if (!dialog.value) return '';
  const titles: Record<RoleDialogMode, string> = {
    create: '新增角色',
    edit: '编辑角色',
    view: '查看角色',
    permissions: '权限管理',
  };
  return titles[dialog.value.mode];
}

function closeDialog() {
  dialog.value = null;
}

function clearMessage() {
  message.value = '';
  messageTone.value = 'error';
}

function setError(value: string) {
  messageTone.value = 'error';
  message.value = value;
}

function setSuccess(value: string) {
  messageTone.value = 'success';
  message.value = value;
}

function replaceRole(role: SystemRole) {
  const index = roles.value.findIndex((item) => item.id === role.id);
  if (index >= 0) {
    roles.value.splice(index, 1, role);
  } else {
    roles.value.push(role);
  }
}

function emptyRoleForm(): RoleForm {
  return {
    name: '',
    permissionIds: [],
  };
}
</script>

<template>
  <section v-if="activeTool === 'roles'" class="role-manager-page" @click="columnsOpen = false">
    <article class="role-filter-panel">
      <label>
        <span>角色名称：</span>
        <input v-model="searchDraft" @keyup.enter="runSearch" />
      </label>
      <button class="role-search-button" type="button" @click="runSearch"><AppIcon name="search" :size="15" />搜索</button>
      <button class="role-reset-button" type="button" @click="resetSearch"><AppIcon name="reset" :size="15" />重置</button>
    </article>

    <article class="role-list-panel">
      <div class="role-list-toolbar">
        <button class="role-add-button" type="button" @click="openCreateDialog"><AppIcon name="circlePlus" :size="15" />新增</button>
        <div class="role-toolbar-actions">
          <button class="role-icon-button" type="button" title="刷新" aria-label="刷新" @click="loadRoles"><AppIcon name="refresh" :size="18" /></button>
          <button class="role-icon-button" type="button" title="列设置" aria-label="列设置" @click.stop="columnsOpen = !columnsOpen"><AppIcon name="settings" :size="18" /></button>
          <div v-if="columnsOpen" class="role-column-menu">当前表格列固定展示</div>
        </div>
      </div>

      <p v-if="message" class="role-message" :class="messageTone">{{ message }}</p>

      <div class="role-table">
        <div class="role-table-row head">
          <span>序号</span>
          <span>角色名称</span>
          <span>角色标识</span>
          <span>状态</span>
          <span>权限管理</span>
          <span>操作</span>
        </div>

        <div v-for="(role, index) in pagedRoles" :key="role.id" class="role-table-row">
          <span>{{ (page - 1) * pageSize + index + 1 }}</span>
          <strong>{{ role.name }}</strong>
          <span>{{ roleCode(role) }}</span>
          <span><em class="role-status">启用</em></span>
          <span>
            <button class="role-permission-button" type="button" :title="permissionText(role)" @click="openPermissionDialog(role)">管理</button>
          </span>
          <div class="role-row-actions">
            <button class="view" type="button" @click="openViewDialog(role)"><AppIcon name="eye" :size="13" />查看</button>
            <button class="edit" type="button" @click="openEditDialog(role)"><AppIcon name="edit" :size="13" />编辑</button>
            <button class="delete" type="button" @click="deleteTarget = role"><AppIcon name="trash" :size="13" />删除</button>
          </div>
        </div>

        <div v-if="isLoading" class="role-empty">加载中...</div>
        <div v-else-if="!pagedRoles.length" class="role-empty">暂无角色数据</div>
      </div>

      <div class="role-pagination">
        <span>共 {{ filteredRoles.length }} 条</span>
        <button type="button" :disabled="page <= 1" aria-label="上一页" @click="setPage(page - 1)"><AppIcon name="chevronRight" :size="16" /></button>
        <strong>{{ page }}</strong>
        <button type="button" :disabled="page >= totalPages" aria-label="下一页" @click="setPage(page + 1)"><AppIcon name="chevronRight" :size="16" /></button>
      </div>
    </article>

    <div v-if="dialog" class="modal-backdrop role-modal-backdrop" @click.self="closeDialog">
      <form class="role-modal" :class="{ 'role-wide-modal': dialog.mode === 'permissions' || dialog.mode === 'view' }" @submit.prevent="saveRole">
        <button class="modal-close" type="button" @click="closeDialog"><AppIcon name="x" :size="16" /></button>
        <h2>{{ dialogTitle() }}</h2>

        <label v-if="dialog.mode !== 'permissions'" class="role-form-row required">
          <span>角色名称：</span>
          <input v-model="form.name" :readonly="dialog.mode === 'view' || dialog.mode === 'permissions'" placeholder="请输入角色名称" />
        </label>

        <label v-if="dialog.mode !== 'create' && dialog.mode !== 'permissions'" class="role-form-row">
          <span>角色标识：</span>
          <input :value="dialog.role ? roleCode(dialog.role) : ''" readonly />
        </label>

        <label v-if="dialog.mode !== 'create' && dialog.mode !== 'permissions'" class="role-form-row">
          <span>状态：</span>
          <input value="启用" readonly />
        </label>

        <div v-if="dialog.mode === 'permissions' || dialog.mode === 'view'" class="role-feature-permissions">
          <div class="role-permission-tip">
            <AppIcon name="circleHelp" :size="15" />
            <span>功能权限仅影响左侧菜单功能。权限变更后，属于该角色的账号重新登录后生效。</span>
          </div>

          <div class="role-permission-tree">
            <div class="role-permission-row head">
              <span>模块</span>
              <span>页面</span>
              <span>功能</span>
            </div>

            <template v-for="group in navGroups" :key="group.key">
              <div
                v-for="(item, itemIndex) in group.items"
                :key="item.key"
                class="role-permission-row"
                :class="{ first: itemIndex === 0 }"
              >
                <label v-if="itemIndex === 0" class="role-tree-node module" :style="{ gridRow: `span ${group.items.length}` }">
                  <input
                    type="checkbox"
                    :checked="isGroupChecked(group.key)"
                    :data-partial="isGroupPartial(group.key)"
                    :disabled="dialog.mode === 'view'"
                    @change="toggleGroup(group.key, $event)"
                  />
                  <span>{{ group.label }}</span>
                </label>
                <label class="role-tree-node page">
                  <input
                    type="checkbox"
                    :checked="isFeatureChecked(item.key)"
                    :disabled="dialog.mode === 'view'"
                    @change="toggleFeature(item.key, $event)"
                  />
                  <span>{{ item.label }}</span>
                </label>
                <label class="role-tree-node feature">
                  <input
                    type="checkbox"
                    :checked="isFeatureChecked(item.key)"
                    :disabled="dialog.mode === 'view'"
                    @change="toggleFeature(item.key, $event)"
                  />
                  <span>开放{{ item.label }}</span>
                </label>
              </div>
            </template>
          </div>
        </div>

        <div class="role-form-actions">
          <button type="button" @click="closeDialog">取消</button>
          <button v-if="dialog.mode !== 'view'" class="role-primary-button" type="submit">确定</button>
        </div>
      </form>
    </div>

    <div v-if="deleteTarget" class="modal-backdrop role-modal-backdrop" @click.self="deleteTarget = null">
      <article class="role-modal role-confirm-modal">
        <button class="modal-close" type="button" @click="deleteTarget = null"><AppIcon name="x" :size="16" /></button>
        <h2>删除角色</h2>
        <p>确定删除角色“{{ deleteTarget.name }}”吗？</p>
        <div class="role-form-actions">
          <button type="button" @click="deleteTarget = null">取消</button>
          <button class="role-danger-button" type="button" @click="deleteRole">删除</button>
        </div>
      </article>
    </div>
  </section>
</template>
