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
}>();

const emit = defineEmits<{
  toggleStatus: [user: SystemUser];
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
</script>

<template>
  <div class="user-table" :style="tableStyle">
    <div class="user-table-row head">
      <span v-if="isColumnVisible('username')">登录名</span>
      <span v-if="isColumnVisible('name')">姓名</span>
      <span v-if="isColumnVisible('roles')">角色</span>
      <span v-if="isColumnVisible('status')">状态</span>
      <span v-if="isColumnVisible('lastLogin')">最近登录</span>
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
      <div v-if="isColumnVisible('actions')" class="user-row-actions">
        <button type="button" :disabled="user.isBuiltinAdmin" @click="$emit('toggleStatus', user)">{{ user.isActive ? '禁用' : '启用' }}</button>
        <button type="button" :disabled="user.isBuiltinAdmin" @click="$emit('edit', user)">编辑</button>
        <button type="button" :disabled="user.isBuiltinAdmin" @click="$emit('resetPassword', user)">重置密码</button>
        <button class="danger" type="button" :disabled="user.isBuiltinAdmin" @click="$emit('delete', user)">删除</button>
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
