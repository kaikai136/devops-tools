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
  isBuiltinAdmin?: boolean;
  canLogin?: boolean;
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
  confirmPassword: string;
  mfaFlag: string;
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

const { activeTool, setActiveTool } = useAppContext();

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
const showPassword = ref(false);
const columnsOpen = ref(false);
const fullscreen = ref(false);
const columnVisibility = ref<UserColumnVisibility>(createColumnVisibility(true));
const messageTone = ref<'error' | 'success'>('error');

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

const passwordRules = computed(() => getPasswordRules(form.value.password));
const resetPasswordRules = computed(() => getPasswordRules(resetPassword.value));
const isPasswordStrong = computed(() => passwordRules.value.every((rule) => rule.valid));
const isResetPasswordStrong = computed(() => resetPasswordRules.value.every((rule) => rule.valid));
const passwordMismatch = computed(() => Boolean(form.value.confirmPassword) && form.value.password !== form.value.confirmPassword);
const passwordStrength = computed(() => passwordRules.value.filter((rule) => rule.valid).length);
const passwordStrengthText = computed(() => {
  if (!form.value.password) return '';
  if (passwordStrength.value <= 1) return '弱';
  if (passwordStrength.value <= 3) return '中';
  return '强';
});
const passwordStrengthClass = computed(() => {
  if (!form.value.password) return 'empty';
  if (passwordStrength.value <= 1) return 'weak';
  if (passwordStrength.value <= 3) return 'medium';
  return 'strong';
});
const passwordHint = computed(() => {
  if (!form.value.password) return '请输入至少8位，包含数字、小写和大写字母的密码。';
  const missing = passwordRules.value.filter((rule) => !rule.valid).map((rule) => rule.message);
  return missing.length ? missing.join('，') : '密码强度符合要求。';
});
const primaryRoleId = computed({
  get: () => (form.value.roleIds[0] ? String(form.value.roleIds[0]) : ''),
  set: (value: string) => {
    form.value.roleIds = value ? [Number(value)] : [];
  },
});
const dialogTitle = computed(() => (dialog.value?.mode === 'edit' ? '编辑账户' : '新建账户'));
const dialogSubmitText = computed(() => (dialog.value?.mode === 'edit' ? '保存' : '确定'));

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
  messageTone.value = 'error';
  try {
    users.value = await apiGet<SystemUser[]>('/api/system/users/');
    try {
      roles.value = await apiGet<SystemRole[]>('/api/system/roles/');
    } catch (error) {
      roles.value = [];
      messageTone.value = 'error';
      message.value = `用户已加载，角色信息加载失败：${(error as Error).message}`;
    }
  } catch (error) {
    users.value = [];
    roles.value = [];
    messageTone.value = 'error';
    message.value = (error as Error).message;
  } finally {
    isLoading.value = false;
  }
}

function openCreateDialog() {
  message.value = '';
  messageTone.value = 'error';
  showPassword.value = false;
  form.value = emptyUserForm();
  dialog.value = { mode: 'create', userId: null };
}

function openEditDialog(user: SystemUser) {
  if (user.isBuiltinAdmin) {
    messageTone.value = 'error';
    message.value = '内置管理员信息固定，不允许编辑';
    return;
  }
  message.value = '';
  messageTone.value = 'error';
  showPassword.value = false;
  form.value = {
    username: user.username,
    email: user.email,
    firstName: user.firstName,
    password: '',
    confirmPassword: '',
    mfaFlag: '',
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
    messageTone.value = 'error';
    message.value = '请输入登录名';
    return;
  }
  if (!payload.firstName) {
    messageTone.value = 'error';
    message.value = '请输入姓名';
    return;
  }
  if (dialog.value?.mode === 'create' && !payload.password) {
    messageTone.value = 'error';
    message.value = '请输入初始密码';
    return;
  }
  if (dialog.value?.mode === 'create' && !isPasswordStrong.value) {
    messageTone.value = 'error';
    message.value = '密码至少 8 位，并包含数字、小写字母和大写字母';
    return;
  }
  if (dialog.value?.mode === 'edit' && payload.password && !isPasswordStrong.value) {
    messageTone.value = 'error';
    message.value = '密码至少 8 位，并包含数字、小写字母和大写字母';
    return;
  }
  if (payload.password && form.value.password !== form.value.confirmPassword) {
    messageTone.value = 'error';
    message.value = '两次输入的密码不一致';
    return;
  }

  try {
    const saved =
      dialog.value?.mode === 'edit' && dialog.value.userId
        ? await apiPut<SystemUser>(`/api/system/users/${dialog.value.userId}/`, payload)
        : await apiPost<SystemUser>('/api/system/users/', payload);
    replaceUser(saved);
    dialog.value = null;
    messageTone.value = 'success';
    message.value = saved.canLogin ? `账号 ${saved.username} 已创建，可使用初始密码登录。` : `账号 ${saved.username} 已保存，启用后即可登录。`;
  } catch (error) {
    messageTone.value = 'error';
    message.value = (error as Error).message;
  }
}

async function toggleUserStatus(user: SystemUser) {
  if (user.isBuiltinAdmin) {
    messageTone.value = 'error';
    message.value = '内置管理员必须保持启用';
    return;
  }
  message.value = '';
  messageTone.value = 'error';
  try {
    const saved = await apiPut<SystemUser>(`/api/system/users/${user.id}/`, {
      ...userPayload(user),
      isActive: !user.isActive,
    });
    replaceUser(saved);
  } catch (error) {
    messageTone.value = 'error';
    message.value = (error as Error).message;
  }
}

function openResetPassword(user: SystemUser) {
  if (user.isBuiltinAdmin) {
    messageTone.value = 'error';
    message.value = '内置管理员密码由系统固定，不允许重置';
    return;
  }
  message.value = '';
  messageTone.value = 'error';
  resetPassword.value = '';
  resetPasswordUser.value = user;
}

async function saveResetPassword() {
  if (!resetPasswordUser.value) return;
  const password = resetPassword.value.trim();
  if (!password) {
    messageTone.value = 'error';
    message.value = '请输入新密码';
    return;
  }
  if (!isResetPasswordStrong.value) {
    messageTone.value = 'error';
    message.value = '新密码至少 8 位，并包含数字、小写字母和大写字母';
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
    messageTone.value = 'error';
    message.value = (error as Error).message;
  }
}

async function deleteUser() {
  if (!deleteTarget.value) return;
  if (deleteTarget.value.isBuiltinAdmin) {
    messageTone.value = 'error';
    message.value = '内置管理员不允许删除';
    deleteTarget.value = null;
    return;
  }
  message.value = '';
  messageTone.value = 'error';
  try {
    const userId = deleteTarget.value.id;
    await apiDelete(`/api/system/users/${userId}/`);
    users.value = users.value.filter((user) => user.id !== userId);
    deleteTarget.value = null;
  } catch (error) {
    messageTone.value = 'error';
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
  if (user.isBuiltinAdmin) names.unshift('内置管理员');
  if (user.isSuperuser) names.unshift('超级管理员');
  if (user.isStaff && !names.length) names.push('管理员');
  return names.join('、');
}

function loginStateText(user: SystemUser) {
  if (user.canLogin === false) return user.isActive ? '待设置密码' : '已禁用';
  return user.isActive ? '可登录' : '已禁用';
}

function getPasswordRules(password: string) {
  return [
    { key: 'length', label: '长度', message: '密码长度至少为 8 位', valid: password.length >= 8 },
    { key: 'number', label: '数字', message: '需包含数字', valid: /\d/.test(password) },
    { key: 'lower', label: '小写', message: '需包含小写字母', valid: /[a-z]/.test(password) },
    { key: 'upper', label: '大写', message: '需包含大写字母', valid: /[A-Z]/.test(password) },
  ];
}

function openRoleManager() {
  dialog.value = null;
  setActiveTool('roles');
}

function openMfaHelp() {
  dialog.value = null;
  setActiveTool('auth');
}

function openDeleteUser(user: SystemUser) {
  message.value = '';
  if (user.isBuiltinAdmin) {
    messageTone.value = 'error';
    message.value = '内置管理员不允许删除';
    return;
  }
  deleteTarget.value = user;
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
    confirmPassword: '',
    mfaFlag: '',
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

      <p v-if="message" class="user-message" :class="messageTone">{{ message }}</p>

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
          <strong v-if="isColumnVisible('username')" class="user-login-name">
            {{ user.username }}
            <em v-if="user.isBuiltinAdmin" class="user-builtin-badge">内置</em>
          </strong>
          <span v-if="isColumnVisible('name')" class="user-real-name">{{ user.firstName || '-' }}</span>
          <span v-if="isColumnVisible('roles')" class="user-role-cell">{{ roleNames(user) || '-' }}</span>
          <span v-if="isColumnVisible('status')" class="user-status" :class="{ disabled: !user.isActive }">
            <i></i>{{ loginStateText(user) }}
          </span>
          <span v-if="isColumnVisible('lastLogin')" class="user-date-cell">{{ formatDate(user.lastLogin) }}</span>
          <div v-if="isColumnVisible('actions')" class="user-row-actions">
            <button type="button" :disabled="user.isBuiltinAdmin" @click="toggleUserStatus(user)">{{ user.isActive ? '禁用' : '启用' }}</button>
            <button type="button" :disabled="user.isBuiltinAdmin" @click="openEditDialog(user)">编辑</button>
            <button type="button" :disabled="user.isBuiltinAdmin" @click="openResetPassword(user)">重置密码</button>
            <button class="danger" type="button" :disabled="user.isBuiltinAdmin" @click="openDeleteUser(user)">删除</button>
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

    <div v-if="dialog" class="modal-backdrop user-modal-backdrop">
      <form class="user-form-modal" @submit.prevent="saveUser">
        <header class="user-form-titlebar">
          <h2>{{ dialogTitle }}</h2>
          <button class="user-modal-close" type="button" aria-label="关闭" @click="dialog = null">
            <AppIcon name="x" :size="18" />
          </button>
        </header>

        <div class="user-form-body">
          <label :class="['user-form-row', { required: dialog.mode === 'create' }]">
            <span>登录名：</span>
            <input v-model.trim="form.username" autofocus autocomplete="username" />
          </label>

          <label class="user-form-row required">
            <span>姓名：</span>
            <input v-model.trim="form.firstName" autocomplete="name" placeholder="请输入姓名" />
          </label>

          <label class="user-form-row required">
            <span>密码：</span>
            <div class="user-password-input">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                :placeholder="dialog.mode === 'edit' ? '留空则不修改' : ''"
              />
              <button type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
                <AppIcon :name="showPassword ? 'eyeOff' : 'eye'" :size="16" />
              </button>
            </div>
          </label>

          <div class="user-password-meter user-form-note-indent" :class="passwordStrengthClass">
            <div class="user-password-meter-head">
              <span>{{ passwordHint }}</span>
              <strong v-if="passwordStrengthText">{{ passwordStrengthText }}</strong>
            </div>
            <div class="user-password-meter-track" aria-hidden="true">
              <i
                v-for="(rule, index) in passwordRules"
                :key="rule.key"
                :class="{ active: index < passwordStrength }"
              ></i>
            </div>
          </div>

          <label v-if="dialog.mode === 'create' || form.password" :class="['user-form-row', { required: dialog.mode === 'create' || form.password }]">
            <span>确认密码：</span>
            <input
              v-model="form.confirmPassword"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="new-password"
              placeholder="请再次输入密码"
            />
          </label>

          <p v-if="passwordMismatch" class="user-form-error user-form-note-indent">两次输入的密码不一致。</p>

          <div class="user-form-row">
            <span>角色：</span>
            <div class="user-role-line">
              <select v-model="primaryRoleId">
                <option value="">请选择</option>
                <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
              </select>
              <button class="user-link-button" type="button" @click="openRoleManager">新建角色</button>
            </div>
          </div>
          <p class="user-form-note user-form-note-indent">权限最大化原则，组合多个角色权限。</p>

          <label class="user-form-row">
            <span>MFA标识：</span>
            <select v-model="form.mfaFlag">
              <option value="">请选择绑定推送标识</option>
            </select>
          </label>
          <p class="user-form-note user-form-note-indent">
            如果启用了MFA（两步验证）则该项为必填。
            <button type="button" @click="openMfaHelp">如何获取MFA标识?</button>
          </p>

          <p v-if="!form.isActive" class="user-inline-warning user-form-note-indent">当前账号处于禁用状态，保存后不能登录。</p>
          <p v-if="message" class="user-message user-form-message">{{ message }}</p>
        </div>

        <footer class="user-form-actions">
          <button type="button" @click="dialog = null">取消</button>
          <button class="user-primary-button" type="submit">{{ dialogSubmitText }}</button>
        </footer>
      </form>
    </div>

    <div v-if="resetPasswordUser" class="modal-backdrop user-modal-backdrop">
      <form class="user-form-modal compact" @submit.prevent="saveResetPassword">
        <button class="modal-close" type="button" @click="resetPasswordUser = null"><AppIcon name="x" :size="16" /></button>
        <h2>重置密码</h2>
        <label class="required">
          <span>新密码</span>
          <input v-model="resetPassword" autofocus type="password" autocomplete="new-password" placeholder="至少 8 位，含数字和大小写字母" />
        </label>
        <div class="user-password-rules">
          <span v-for="rule in resetPasswordRules" :key="rule.key" :class="{ passed: rule.valid }">
            <AppIcon :name="rule.valid ? 'circleCheck' : 'circleHelp'" :size="14" />
            {{ rule.label }}
          </span>
        </div>
        <div class="user-form-actions">
          <button type="button" @click="resetPasswordUser = null">取消</button>
          <button class="user-primary-button" type="submit">保存</button>
        </div>
      </form>
    </div>

    <div v-if="deleteTarget" class="modal-backdrop user-modal-backdrop">
      <article class="user-form-modal compact">
        <button class="modal-close" type="button" @click="deleteTarget = null"><AppIcon name="x" :size="16" /></button>
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
