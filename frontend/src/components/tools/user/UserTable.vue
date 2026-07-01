<script setup lang="ts">
import { formatDateTime } from '../../../utils/datetime';
import AppIcon from '../../common/AppIcon.vue';
import type { SystemUser, UserColumnKey } from '../../../composables/features/useUserManager';

defineProps<{
  users: SystemUser[];
  filteredCount: number;
  isLoading: boolean;
  page: number;
  pageSize: number;
  totalPages: number;
  tableStyle: Record<string, string>;
  isColumnVisible: (key: UserColumnKey) => boolean;
  roleNames: (user: SystemUser) => string;
  loginStateText: (user: SystemUser) => string;
  twoFactorStatusClass: (user: SystemUser) => string;
  canUsePageAction: (pageKey: string, actionKey: string) => boolean;
}>();

const emit = defineEmits<{
  toggleStatus: [user: SystemUser];
  enableTwoFactor: [user: SystemUser];
  disableTwoFactor: [user: SystemUser];
  resetTwoFactor: [user: SystemUser];
  edit: [user: SystemUser];
  resetPassword: [user: SystemUser];
  delete: [user: SystemUser];
  updatePage: [page: number];
  updatePageSize: [pageSize: number];
}>();

const pageSizeOptions = [10, 20, 50];

function updatePageSize(event: Event) {
  emit('updatePageSize', Number((event.target as HTMLSelectElement).value));
}

function toggleTwoFactor(user: SystemUser) {
  if (user.twoFactorStatus === 'disabled' || !user.twoFactorStatus) {
    emit('enableTwoFactor', user);
    return;
  }
  emit('disableTwoFactor', user);
}

function twoFactorSwitchText(user: SystemUser) {
  return user.twoFactorStatus === 'enabled' ? '开启' : '关闭';
}

function canToggleTwoFactor(user: SystemUser) {
  return user.twoFactorStatus === 'enabled' ? canUsePageAction('users', '2fa_disable') : canUsePageAction('users', '2fa_enable');
}

function hasTwoFactorActions(user: SystemUser) {
  if (user.twoFactorStatus === 'required') return false;
  return canToggleTwoFactor(user) || canUsePageAction('users', '2fa_reset');
}

function hasRowActions() {
  return (
    canUsePageAction('users', 'toggle_status') ||
    canUsePageAction('users', 'edit') ||
    canUsePageAction('users', 'reset_password') ||
    canUsePageAction('users', 'delete')
  );
}
</script>

<template>
  <div class="user-table" :style="tableStyle">
    <div class="user-table-row head">
      <span v-if="isColumnVisible('username')">登录名</span>
      <span v-if="isColumnVisible('name')">姓名</span>
      <span v-if="isColumnVisible('roles')">角色</span>
      <span v-if="isColumnVisible('status')">状态</span>
      <span v-if="isColumnVisible('lastLogin')">最近登录</span>
      <span v-if="isColumnVisible('twoFactor')">2FA</span>
      <span v-if="isColumnVisible('actions')">操作</span>
    </div>
    <div v-for="user in users" :key="user.id" class="user-table-row">
      <strong v-if="isColumnVisible('username')" class="user-login-name">
        {{ user.username }}
        <em v-if="user.isBuiltinAdmin" class="user-builtin-badge">内置</em>
      </strong>
      <span v-if="isColumnVisible('name')" class="user-real-name">{{ user.firstName || '-' }}</span>
      <span v-if="isColumnVisible('roles')" class="user-role-cell">{{ roleNames(user) || '-' }}</span>
      <span v-if="isColumnVisible('status')" class="user-status" :class="{ disabled: !user.isActive }">
        <i></i>{{ loginStateText(user) === '可登录' ? '正常' : loginStateText(user) }}
      </span>
      <span v-if="isColumnVisible('lastLogin')" class="user-date-cell">{{ formatDateTime(user.lastLogin) }}</span>
      <div v-if="isColumnVisible('twoFactor')" class="user-2fa-cell">
        <span v-if="user.twoFactorStatus === 'required'" class="user-2fa-pending">待验证</span>
        <template v-else-if="hasTwoFactorActions(user)">
          <button
            v-if="canToggleTwoFactor(user)"
            class="user-2fa-switch"
            :class="twoFactorStatusClass(user)"
            type="button"
            :title="user.twoFactorStatus === 'enabled' ? '点击关闭 2FA' : '点击开启 2FA'"
            :disabled="user.isBuiltinAdmin"
            @click="toggleTwoFactor(user)"
          >
            <span>{{ twoFactorSwitchText(user) }}</span>
            <i></i>
          </button>
          <button
            v-if="canUsePageAction('users', '2fa_reset')"
            class="user-2fa-reset"
            type="button"
            title="重置绑定"
            aria-label="重置 2FA 绑定"
            :disabled="user.isBuiltinAdmin"
            @click="$emit('resetTwoFactor', user)"
          >
            重置
          </button>
        </template>
        <span v-else class="permission-placeholder">-</span>
      </div>
      <div v-if="isColumnVisible('actions')" class="user-row-actions">
        <button v-if="canUsePageAction('users', 'toggle_status')" type="button" :disabled="user.isBuiltinAdmin" @click="$emit('toggleStatus', user)">{{ user.isActive ? '禁用' : '启用' }}</button>
        <button v-if="canUsePageAction('users', 'edit')" type="button" :disabled="user.isBuiltinAdmin" @click="$emit('edit', user)">编辑</button>
        <button v-if="canUsePageAction('users', 'reset_password')" type="button" :disabled="user.isBuiltinAdmin" @click="$emit('resetPassword', user)">重置密码</button>
        <button v-if="canUsePageAction('users', 'delete')" class="danger" type="button" :disabled="user.isBuiltinAdmin" @click="$emit('delete', user)">删除</button>
        <span v-if="!hasRowActions()" class="permission-placeholder">-</span>
      </div>
    </div>
    <div v-if="!users.length" class="user-empty">{{ isLoading ? '加载中...' : '暂无匹配账户' }}</div>
  </div>

  <div class="user-pagination">
    <span>共 {{ filteredCount }} 条</span>
    <button type="button" :disabled="page <= 1" @click="$emit('updatePage', page - 1)"><AppIcon name="chevronRight" :size="15" /></button>
    <strong>{{ page }}</strong>
    <button type="button" :disabled="page >= totalPages" @click="$emit('updatePage', page + 1)"><AppIcon name="chevronRight" :size="15" /></button>
    <select :value="pageSize" @change="updatePageSize">
      <option v-for="option in pageSizeOptions" :key="option" :value="option">{{ option }} 条/页</option>
    </select>
  </div>
</template>
