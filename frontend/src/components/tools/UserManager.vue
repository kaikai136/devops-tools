<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import { useAppContext } from '../../appContext';
import AppIcon from '../common/AppIcon.vue';

interface SystemUser {
  id: number;
  username: string;
  email: string;
  firstName: string;
  isActive: boolean;
  isStaff: boolean;
  isSuperuser: boolean;
  lastLogin: string | null;
  dateJoined: string | null;
  roleIds: number[];
}

interface SystemRole {
  id: number;
  name: string;
  permissionIds: number[];
}

interface UserForm {
  username: string;
  email: string;
  firstName: string;
  password: string;
  isActive: boolean;
  isStaff: boolean;
  roleIds: number[];
}

type UserStatusFilter = 'all' | 'active' | 'disabled';
type UserColumnKey = 'username' | 'name' | 'roles' | 'status' | 'lastLogin' | 'actions';
type UserColumnVisibility = Record<UserColumnKey, boolean>;

const userColumnOptions: Array<{ key: UserColumnKey; label: string; width: string }> = [
  { key: 'username', label: '登录名', width: 'minmax(120px, 1fr)' },
  { key: 'name', label: '姓名', width: 'minmax(120px, 1fr)' },
  { key: 'roles', label: '角色', width: 'minmax(120px, 1fr)' },
  { key: 'status', label: '状态', width: 'minmax(96px, 0.75fr)' },
  { key: 'lastLogin', label: '最近登录', width: 'minmax(170px, 1.35fr)' },
  { key: 'actions', label: '操作', width: 'minmax(220px, 1.55fr)' },
];

const { activeTool } = useAppContext();

const users = ref<SystemUser[]>([]);
const roles = ref<SystemRole[]>([]);
const search = ref('');
const statusFilter = ref<UserStatusFilter>('all');
const isLoading = ref(false);
const message = ref('');
const page = ref(1);
const pageSize = ref(10);
const dialog = ref<{ mode: 'create' | 'edit'; userId: number | null } | null>(null);
const resetPasswordUser = ref<SystemUser | null>(null);
const deleteTarget = ref<SystemUser | null>(null);
const form = ref<UserForm>(emptyUserForm());
const resetPassword = ref('');
const columnsOpen = ref(false);
const fullscreen = ref(false);
const columnVisibility = ref<UserColumnVisibility>(createColumnVisibility(true));

const visibleColumns = computed(() => userColumnOptions.filter((column) => columnVisibility.value[column.key]));
const tableStyle = computed(() => ({
  '--user-table-columns': visibleColumns.value.map((column) => column.width).join(' ') || 'minmax(180px, 1fr)',
}));

const filteredUsers = computed(() => {
  const query = search.value.trim().toLowerCase();
  return users.value.filter((user) => {
    const statusMatched =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'active' && user.isActive) ||
      (statusFilter.value === 'disabled' && !user.isActive);
    const searchMatched =
      !query ||
      [user.username, user.firstName, user.email, roleNames(user)]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    return statusMatched && searchMatched;
  });
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / pageSize.value)));
const pagedUsers = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredUsers.value.slice(start, start + pageSize.value);
});

const statusCounts = computed(() => ({
  total: users.value.length,
  active: users.value.filter((user) => user.isActive).length,
  disabled: users.value.filter((user) => !user.isActive).length,
}));

onMounted(loadUsers);

watch([search, statusFilter, pageSize], () => {
  page.value = 1;
});

watch(totalPages, (next) => {
  if (page.value > next) page.value = next;
});

async function loadUsers() {
  isLoading.value = true;
  message.value = '';
  try {
    const [nextUsers, nextRoles] = await Promise.all([
      apiGet<SystemUser[]>('/api/system/users/'),
      apiGet<SystemRole[]>('/api/system/roles/'),
    ]);
    users.value = nextUsers;
    roles.value = nextRoles;
  } catch (error) {
    message.value = (error as Error).message;
  } finally {
    isLoading.value = false;
  }
}

function openCreateDialog() {
  message.value = '';
  form.value = emptyUserForm();
  dialog.value = { mode: 'create', userId: null };
}

function openEditDialog(user: SystemUser) {
  message.value = '';
  form.value = {
    username: user.username,
    email: user.email,
    firstName: user.firstName,
    password: '',
    isActive: user.isActive,
    isStaff: user.isStaff,
    roleIds: [...user.roleIds],
  };
  dialog.value = { mode: 'edit', userId: user.id };
}

async function saveUser() {
  message.value = '';
  const payload = userPayloadFromForm();
  if (!payload.username) {
    message.value = '请输入登录名';
    return;
  }
  if (dialog.value?.mode === 'create' && !payload.password) {
    message.value = '请输入初始密码';
    return;
  }

  try {
    const saved =
      dialog.value?.mode === 'edit' && dialog.value.userId
        ? await apiPut<SystemUser>(`/api/system/users/${dialog.value.userId}/`, payload)
        : await apiPost<SystemUser>('/api/system/users/', payload);
    replaceUser(saved);
    dialog.value = null;
  } catch (error) {
    message.value = (error as Error).message;
  }
}

async function toggleUserStatus(user: SystemUser) {
  message.value = '';
  try {
    const saved = await apiPut<SystemUser>(`/api/system/users/${user.id}/`, {
      ...userPayload(user),
      isActive: !user.isActive,
    });
    replaceUser(saved);
  } catch (error) {
    message.value = (error as Error).message;
  }
}

function openResetPassword(user: SystemUser) {
  message.value = '';
  resetPassword.value = '';
  resetPasswordUser.value = user;
}

async function saveResetPassword() {
  if (!resetPasswordUser.value) return;
  const password = resetPassword.value.trim();
  if (!password) {
    message.value = '请输入新密码';
    return;
  }

  try {
    const user = resetPasswordUser.value;
    const saved = await apiPut<SystemUser>(`/api/system/users/${user.id}/`, {
      ...userPayload(user),
      password,
    });
    replaceUser(saved);
    resetPasswordUser.value = null;
    resetPassword.value = '';
  } catch (error) {
    message.value = (error as Error).message;
  }
}

async function deleteUser() {
  if (!deleteTarget.value) return;
  message.value = '';
  try {
    const userId = deleteTarget.value.id;
    await apiDelete(`/api/system/users/${userId}/`);
    users.value = users.value.filter((user) => user.id !== userId);
    deleteTarget.value = null;
  } catch (error) {
    message.value = (error as Error).message;
  }
}

function replaceUser(user: SystemUser) {
  const index = users.value.findIndex((item) => item.id === user.id);
  if (index >= 0) {
    users.value.splice(index, 1, user);
  } else {
    users.value = [user, ...users.value];
  }
}

function userPayloadFromForm() {
  return {
    username: form.value.username.trim(),
    email: form.value.email.trim(),
    firstName: form.value.firstName.trim(),
    password: form.value.password.trim(),
    isActive: form.value.isActive,
    isStaff: form.value.isStaff,
    roleIds: form.value.roleIds,
  };
}

function userPayload(user: SystemUser) {
  return {
    username: user.username,
    email: user.email,
    firstName: user.firstName,
    isActive: user.isActive,
    isStaff: user.isStaff,
    roleIds: user.roleIds,
  };
}

function roleNames(user: SystemUser) {
  const names = user.roleIds
    .map((roleId) => roles.value.find((role) => role.id === roleId)?.name)
    .filter(Boolean);
  if (user.isSuperuser) names.unshift('超级管理员');
  if (user.isStaff && !names.length) names.push('管理员');
  return names.join('、');
}

function formatDate(value: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function isColumnVisible(key: UserColumnKey) {
  return columnVisibility.value[key];
}

function isOnlyVisibleColumn(key: UserColumnKey) {
  return columnVisibility.value[key] && visibleColumns.value.length === 1;
}

function updateColumnVisibility(key: UserColumnKey, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  if (!checked && isOnlyVisibleColumn(key)) return;
  columnVisibility.value = { ...columnVisibility.value, [key]: checked };
}

function createColumnVisibility(visible: boolean): UserColumnVisibility {
  return userColumnOptions.reduce((visibility, column) => {
    visibility[column.key] = visible;
    return visibility;
  }, {} as UserColumnVisibility);
}

function emptyUserForm(): UserForm {
  return {
    username: '',
    email: '',
    firstName: '',
    password: '',
    isActive: true,
    isStaff: false,
    roleIds: [],
  };
}
</script>

<template>
  <section v-if="activeTool === 'users'" class="user-manager-page" :class="{ fullscreen }" @click="columnsOpen = false">
    <div class="user-breadcrumb">
      <span>首页</span>
      <em>/</em>
      <span>系统管理</span>
      <em>/</em>
      <strong>用户管理</strong>
    </div>

    <article class="user-filter-panel">
      <label>
        <span>账户名称：</span>
        <input v-model="search" placeholder="请输入" />
      </label>
    </article>

    <article class="user-list-panel">
      <div class="user-list-toolbar">
        <h2>账户列表</h2>
        <div class="user-toolbar-actions">
          <button class="user-primary-button" type="button" @click="openCreateDialog"><AppIcon name="plus" :size="15" />新建</button>
          <div class="user-status-tabs" role="tablist" aria-label="账户状态">
            <button :class="{ active: statusFilter === 'all' }" type="button" @click="statusFilter = 'all'">全部</button>
            <button :class="{ active: statusFilter === 'active' }" type="button" @click="statusFilter = 'active'">正常</button>
            <button :class="{ active: statusFilter === 'disabled' }" type="button" @click="statusFilter = 'disabled'">禁用</button>
          </div>
          <span class="user-toolbar-divider"></span>
          <button class="user-icon-button" type="button" title="刷新" aria-label="刷新" @click="loadUsers"><AppIcon name="refresh" :size="18" /></button>
          <div class="user-column-settings" @click.stop>
            <button class="user-icon-button" type="button" title="列设置" aria-label="列设置" @click="columnsOpen = !columnsOpen"><AppIcon name="settings" :size="18" /></button>
            <div v-if="columnsOpen" class="user-column-menu">
              <label v-for="column in userColumnOptions" :key="column.key">
                <input
                  type="checkbox"
                  :checked="isColumnVisible(column.key)"
                  :disabled="isOnlyVisibleColumn(column.key)"
                  @change="updateColumnVisibility(column.key, $event)"
                />
                <span>{{ column.label }}</span>
              </label>
            </div>
          </div>
          <button class="user-icon-button" type="button" :title="fullscreen ? '退出全屏' : '全屏'" :aria-label="fullscreen ? '退出全屏' : '全屏'" @click="fullscreen = !fullscreen">
            <AppIcon :name="fullscreen ? 'minimize' : 'maximize'" :size="18" />
          </button>
        </div>
      </div>

      <p v-if="message" class="user-message">{{ message }}</p>

      <div class="user-table" :style="tableStyle">
        <div class="user-table-row head">
          <span v-if="isColumnVisible('username')">登录名</span>
          <span v-if="isColumnVisible('name')">姓名</span>
          <span v-if="isColumnVisible('roles')">角色</span>
          <span v-if="isColumnVisible('status')">状态</span>
          <span v-if="isColumnVisible('lastLogin')">最近登录</span>
          <span v-if="isColumnVisible('actions')">操作</span>
        </div>
        <div v-for="user in pagedUsers" :key="user.id" class="user-table-row">
          <strong v-if="isColumnVisible('username')" class="user-login-name">{{ user.username }}</strong>
          <span v-if="isColumnVisible('name')" class="user-real-name">{{ user.firstName || '-' }}</span>
          <span v-if="isColumnVisible('roles')" class="user-role-cell">{{ roleNames(user) || '-' }}</span>
          <span v-if="isColumnVisible('status')" class="user-status" :class="{ disabled: !user.isActive }">
            <i></i>{{ user.isActive ? '正常' : '禁用' }}
          </span>
          <span v-if="isColumnVisible('lastLogin')" class="user-date-cell">{{ formatDate(user.lastLogin) }}</span>
          <div v-if="isColumnVisible('actions')" class="user-row-actions">
            <button type="button" @click="toggleUserStatus(user)">{{ user.isActive ? '禁用' : '启用' }}</button>
            <button type="button" @click="openEditDialog(user)">编辑</button>
            <button type="button" @click="openResetPassword(user)">重置密码</button>
            <button class="danger" type="button" @click="deleteTarget = user">删除</button>
          </div>
        </div>
        <div v-if="!pagedUsers.length" class="user-empty">{{ isLoading ? '加载中...' : '暂无匹配账户' }}</div>
      </div>

      <div class="user-pagination">
        <span>共 {{ filteredUsers.length }} 条</span>
        <button type="button" :disabled="page <= 1" @click="page -= 1"><AppIcon name="chevronRight" :size="15" /></button>
        <strong>{{ page }}</strong>
        <button type="button" :disabled="page >= totalPages" @click="page += 1"><AppIcon name="chevronRight" :size="15" /></button>
        <select v-model.number="pageSize">
          <option :value="10">10 条/页</option>
          <option :value="20">20 条/页</option>
          <option :value="50">50 条/页</option>
        </select>
      </div>
    </article>

    <div v-if="dialog" class="modal-backdrop" @click.self="dialog = null">
      <form class="user-form-modal" @submit.prevent="saveUser">
        <button class="modal-close" type="button" @click="dialog = null"><AppIcon name="x" :size="16" /></button>
        <h2>{{ dialog.mode === 'edit' ? '编辑用户' : '新建用户' }}</h2>
        <label class="required">
          <span>登录名</span>
          <input v-model="form.username" autofocus />
        </label>
        <label>
          <span>姓名</span>
          <input v-model="form.firstName" />
        </label>
        <label>
          <span>邮箱</span>
          <input v-model="form.email" type="email" />
        </label>
        <label :class="{ required: dialog.mode === 'create' }">
          <span>{{ dialog.mode === 'create' ? '初始密码' : '新密码' }}</span>
          <input v-model="form.password" type="password" autocomplete="new-password" :placeholder="dialog.mode === 'edit' ? '留空则不修改' : ''" />
        </label>
        <label>
          <span>角色</span>
          <select v-model="form.roleIds" multiple>
            <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
          </select>
        </label>
        <div class="user-switches">
          <label>
            <input v-model="form.isActive" type="checkbox" />
            <span>正常启用</span>
          </label>
          <label>
            <input v-model="form.isStaff" type="checkbox" />
            <span>管理员</span>
          </label>
        </div>
        <p v-if="message" class="user-message">{{ message }}</p>
        <div class="user-form-actions">
          <button type="button" @click="dialog = null">取消</button>
          <button class="user-primary-button" type="submit">保存</button>
        </div>
      </form>
    </div>

    <div v-if="resetPasswordUser" class="modal-backdrop" @click.self="resetPasswordUser = null">
      <form class="user-form-modal compact" @submit.prevent="saveResetPassword">
        <button class="modal-close" type="button" @click="resetPasswordUser = null"><AppIcon name="x" :size="16" /></button>
        <h2>重置密码</h2>
        <label class="required">
          <span>新密码</span>
          <input v-model="resetPassword" autofocus type="password" autocomplete="new-password" />
        </label>
        <div class="user-form-actions">
          <button type="button" @click="resetPasswordUser = null">取消</button>
          <button class="user-primary-button" type="submit">保存</button>
        </div>
      </form>
    </div>

    <div v-if="deleteTarget" class="modal-backdrop" @click.self="deleteTarget = null">
      <article class="user-form-modal compact">
        <h2>删除用户</h2>
        <p>确定删除账户“{{ deleteTarget.username }}”吗？</p>
        <div class="user-form-actions">
          <button type="button" @click="deleteTarget = null">取消</button>
          <button class="danger" type="button" @click="deleteUser">删除</button>
        </div>
      </article>
    </div>
  </section>
</template>
