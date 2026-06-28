<script setup lang="ts">
import { useAppContext } from '../../appContext';
import { useUserManager, userColumnOptions } from '../../composables/features/useUserManager';
import AppIcon from '../common/AppIcon.vue';
import UserAccountDialog from './user/UserAccountDialog.vue';
import UserDeleteDialog from './user/UserDeleteDialog.vue';
import UserResetPasswordDialog from './user/UserResetPasswordDialog.vue';
import UserTable from './user/UserTable.vue';

const { activeTool, setActiveTool, canUsePageAction } = useAppContext();

const {
  roles,
  search,
  statusFilter,
  isLoading,
  message,
  messageTone,
  page,
  pageSize,
  dialog,
  resetPasswordUser,
  deleteTarget,
  form,
  formErrors,
  resetPassword,
  showPassword,
  columnsOpen,
  fullscreen,
  tableStyle,
  filteredUsers,
  pagedUsers,
  totalPages,
  passwordRules,
  resetPasswordRules,
  passwordMismatch,
  passwordStrength,
  resetPasswordStrength,
  passwordStrengthText,
  resetPasswordStrengthText,
  passwordStrengthClass,
  resetPasswordStrengthClass,
  passwordHint,
  resetPasswordHint,
  primaryRoleId,
  dialogTitle,
  dialogSubmitText,
  loadUsers,
  refreshUsers,
  openCreateDialog,
  openEditDialog,
  saveUser,
  toggleUserStatus,
  openResetPassword,
  saveResetPassword,
  openDeleteUser,
  deleteUser,
  closeAccountDialog,
  closeResetPasswordDialog,
  closeDeleteDialog,
  roleNames,
  loginStateText,
  openRoleManager,
  openMfaHelp,
  setPage,
  setPageSize,
  isColumnVisible,
  isOnlyVisibleColumn,
  updateColumnVisibility,
} = useUserManager({ setActiveTool });
</script>

<template>
  <section v-if="activeTool === 'users'" class="user-manager-page" :class="{ fullscreen }" @click="columnsOpen = false">
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
          <button class="user-primary-button" type="button" :disabled="!canUsePageAction('users', 'create')" @click="openCreateDialog"><AppIcon name="plus" :size="15" />新建</button>
          <div class="user-status-tabs" role="tablist" aria-label="账户状态">
            <button :class="{ active: statusFilter === 'all' }" type="button" @click="statusFilter = 'all'">全部</button>
            <button :class="{ active: statusFilter === 'active' }" type="button" @click="statusFilter = 'active'">正常</button>
            <button :class="{ active: statusFilter === 'disabled' }" type="button" @click="statusFilter = 'disabled'">禁用</button>
          </div>
          <span class="user-toolbar-divider"></span>
          <button class="user-icon-button" type="button" title="刷新" aria-label="刷新" @click="refreshUsers"><AppIcon name="refresh" :size="18" /></button>
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

      <UserTable
        :users="pagedUsers"
        :filtered-count="filteredUsers.length"
        :is-loading="isLoading"
        :page="page"
        :page-size="pageSize"
        :total-pages="totalPages"
        :table-style="tableStyle"
        :is-column-visible="isColumnVisible"
        :role-names="roleNames"
        :login-state-text="loginStateText"
        :can-use-page-action="canUsePageAction"
        @toggle-status="toggleUserStatus"
        @edit="openEditDialog"
        @reset-password="openResetPassword"
        @delete="openDeleteUser"
        @update-page="setPage"
        @update-page-size="setPageSize"
      />
    </article>

    <UserAccountDialog
      v-if="dialog"
      v-model:form="form"
      v-model:primary-role-id="primaryRoleId"
      v-model:show-password="showPassword"
      :dialog="dialog"
      :roles="roles"
      :title="dialogTitle"
      :submit-text="dialogSubmitText"
      :password-rules="passwordRules"
      :password-strength="passwordStrength"
      :password-strength-class="passwordStrengthClass"
      :password-strength-text="passwordStrengthText"
      :password-hint="passwordHint"
      :password-mismatch="passwordMismatch"
      :form-errors="formErrors"
      :message="message"
      @submit="saveUser"
      @close="closeAccountDialog"
      @open-role-manager="openRoleManager"
      @open-mfa-help="openMfaHelp"
    />

    <UserResetPasswordDialog
      v-if="resetPasswordUser"
      v-model:password="resetPassword"
      :rules="resetPasswordRules"
      :strength="resetPasswordStrength"
      :strength-class="resetPasswordStrengthClass"
      :strength-text="resetPasswordStrengthText"
      :hint="resetPasswordHint"
      @submit="saveResetPassword"
      @close="closeResetPasswordDialog"
    />

    <UserDeleteDialog
      v-if="deleteTarget"
      :user="deleteTarget"
      @close="closeDeleteDialog"
      @confirm="deleteUser"
    />
  </section>
</template>
