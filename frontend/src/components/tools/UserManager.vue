<script setup lang="ts">
import { useAppContext } from '@app/context';
import { useUserManager, userColumnOptions } from '../../composables/features/useUserManager';
import AppIcon from '@shared/components/AppIcon.vue';
import UserAccountDialog from './user/UserAccountDialog.vue';
import UserDeleteDialog from './user/UserDeleteDialog.vue';
import UserResetPasswordDialog from './user/UserResetPasswordDialog.vue';
import UserResetTwoFactorDialog from './user/UserResetTwoFactorDialog.vue';
import UserTable from './user/UserTable.vue';

const { activeTool, setActiveTool, canAccessPage, canUsePageAction } = useAppContext();

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
  resetTwoFactorTarget,
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
  allColumnsVisible,
  someColumnsVisible,
  dialogTitle,
  dialogSubmitText,
  refreshUsers,
  openCreateDialog,
  openEditDialog,
  saveUser,
  toggleUserStatus,
  openResetPassword,
  saveResetPassword,
  enableUserTwoFactor,
  disableUserTwoFactor,
  openResetTwoFactor,
  resetUserTwoFactor,
  toggleUserSessionAudit,
  openDeleteUser,
  deleteUser,
  closeAccountDialog,
  closeResetPasswordDialog,
  closeResetTwoFactorDialog,
  closeDeleteDialog,
  roleNames,
  loginStateText,
  twoFactorStatusClass,
  sessionAuditEnabled,
  openRoleManager,
  openMfaHelp,
  setPage,
  setPageSize,
  isColumnVisible,
  isOnlyVisibleColumn,
  updateColumnVisibility,
  toggleAllColumns,
  resetColumns,
} = useUserManager({ setActiveTool });
</script>

<template>
  <section v-if="activeTool === 'users'" class="user-manager-page" :class="{ fullscreen }" @click="columnsOpen = false">
    <template v-if="canAccessPage('users')">
      <article class="user-filter-panel">
        <NativeForm inline label-position="left">
          <NativeFormItem label="账户名称">
            <NativeInput v-model="search" placeholder="请输入" clearable />
          </NativeFormItem>
        </NativeForm>
      </article>

      <article class="user-list-panel">
        <div class="user-list-toolbar">
          <h2>账户列表</h2>
          <div class="user-toolbar-actions">
            <NativeButton v-if="canUsePageAction('users', 'create')" type="primary" @click="openCreateDialog">
              <AppIcon name="plus" :size="15" />
              <span>新建</span>
            </NativeButton>
            <NativeRadioGroup v-model="statusFilter" class="user-status-tabs">
              <NativeRadioButton label="all">全部</NativeRadioButton>
              <NativeRadioButton label="active">正常</NativeRadioButton>
              <NativeRadioButton label="disabled">禁用</NativeRadioButton>
            </NativeRadioGroup>
            <span class="user-toolbar-divider"></span>
            <NativeTooltip content="刷新" placement="top">
              <NativeButton circle @click="refreshUsers">
                <AppIcon name="refresh" :size="18" />
              </NativeButton>
            </NativeTooltip>
            <NativePopover
              v-model:visible="columnsOpen"
              placement="bottom-end"
              trigger="click"
              width="220"
              popper-class="user-column-menu"
              @click.stop
            >
              <template #reference>
                <NativeButton circle @click.stop>
                  <AppIcon name="settings" :size="18" />
                </NativeButton>
              </template>
              <div class="user-column-menu-head">
                <NativeCheckbox
                  :model-value="allColumnsVisible"
                  :indeterminate="someColumnsVisible && !allColumnsVisible"
                  @change="toggleAllColumns"
                >
                  列显示
                </NativeCheckbox>
                <NativeButton size="small" text type="primary" @click="resetColumns">重置</NativeButton>
              </div>
              <div class="user-column-options">
                <NativeCheckbox
                  v-for="column in userColumnOptions"
                  :key="column.key"
                  :model-value="isColumnVisible(column.key)"
                  :disabled="isOnlyVisibleColumn(column.key)"
                  @change="updateColumnVisibility(column.key, $event)"
                >
                  {{ column.label }}
                </NativeCheckbox>
              </div>
            </NativePopover>
            <NativeTooltip :content="fullscreen ? '退出全屏' : '全屏'" placement="top">
              <NativeButton circle @click="fullscreen = !fullscreen">
                <AppIcon :name="fullscreen ? 'minimize' : 'maximize'" :size="18" />
              </NativeButton>
            </NativeTooltip>
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
          :two-factor-status-class="twoFactorStatusClass"
          :session-audit-enabled="sessionAuditEnabled"
          :can-use-page-action="canUsePageAction"
          @toggle-status="toggleUserStatus"
          @enable-two-factor="enableUserTwoFactor"
          @disable-two-factor="disableUserTwoFactor"
          @reset-two-factor="openResetTwoFactor"
          @toggle-session-audit="toggleUserSessionAudit"
          @edit="openEditDialog"
          @reset-password="openResetPassword"
          @delete="openDeleteUser"
          @update-page="setPage"
          @update-page-size="setPageSize"
        />
      </article>
    </template>
    <div v-else class="permission-empty">暂无用户管理权限</div>

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

    <UserResetTwoFactorDialog
      v-if="resetTwoFactorTarget"
      :user="resetTwoFactorTarget"
      @close="closeResetTwoFactorDialog"
      @confirm="resetUserTwoFactor"
    />

    <UserDeleteDialog
      v-if="deleteTarget"
      :user="deleteTarget"
      @close="closeDeleteDialog"
      @confirm="deleteUser"
    />
  </section>
</template>
