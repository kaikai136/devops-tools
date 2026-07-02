<script setup lang="ts">
import { computed } from 'vue';

import { formatDateTime } from '../../../utils/datetime';
import AppIcon from '../../common/AppIcon.vue';
import type { SystemUser, UserColumnKey } from '../../../composables/features/useUserManager';

const props = defineProps<{
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
const pageStart = computed(() => (props.filteredCount ? (props.page - 1) * props.pageSize + 1 : 0));
const pageEnd = computed(() => Math.min(props.page * props.pageSize, props.filteredCount));
const pageNumbers = computed(() => {
  const from = Math.max(1, props.page - 2);
  const to = Math.min(props.totalPages, props.page + 2);
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
});

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
  return user.twoFactorStatus === 'enabled' ? props.canUsePageAction('users', '2fa_disable') : props.canUsePageAction('users', '2fa_enable');
}

function hasTwoFactorActions(user: SystemUser) {
  if (user.twoFactorStatus === 'required') return false;
  return canToggleTwoFactor(user) || props.canUsePageAction('users', '2fa_reset');
}

function hasRowActions() {
  return (
    props.canUsePageAction('users', 'toggle_status') ||
    props.canUsePageAction('users', 'edit') ||
    props.canUsePageAction('users', 'reset_password') ||
    props.canUsePageAction('users', 'delete')
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

  <div class="host-pagination" aria-label="用户列表分页">
    <div class="host-pagination-summary">
      <span>共 {{ filteredCount }} 条</span>
      <span>{{ pageStart }}-{{ pageEnd }}</span>
    </div>
    <div class="host-pagination-controls">
      <button class="prev" type="button" :disabled="page <= 1" aria-label="上一页" @click="$emit('updatePage', page - 1)">
        <AppIcon name="chevronRight" :size="14" />
      </button>
      <button
        v-for="pageNumber in pageNumbers"
        :key="pageNumber"
        type="button"
        :class="{ active: pageNumber === page }"
        @click="$emit('updatePage', pageNumber)"
      >
        {{ pageNumber }}
      </button>
      <button type="button" :disabled="page >= totalPages" aria-label="下一页" @click="$emit('updatePage', page + 1)">
        <AppIcon name="chevronRight" :size="14" />
      </button>
      <select :value="pageSize" aria-label="每页条数" @change="updatePageSize">
        <option v-for="option in pageSizeOptions" :key="option" :value="option">{{ option }} 条/页</option>
      </select>
    </div>
  </div>
</template>
