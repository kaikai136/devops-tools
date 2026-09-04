<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';
import type { PasswordRule, PasswordStrengthLevel } from '@shared/composables/usePasswordStrength';
import type { SystemRole, UserDialogState, UserForm, UserFormErrors } from '../../../composables/features/useUserManager';

defineProps<{
  dialog: UserDialogState;
  roles: SystemRole[];
  title: string;
  submitText: string;
  passwordRules: PasswordRule[];
  passwordStrength: number;
  passwordStrengthClass: PasswordStrengthLevel;
  passwordStrengthText: string;
  passwordHint: string;
  passwordMismatch: boolean;
  formErrors: UserFormErrors;
  message: string;
}>();

const form = defineModel<UserForm>('form', { required: true });
const primaryRoleId = defineModel<string>('primaryRoleId', { required: true });
const showPassword = defineModel<boolean>('showPassword', { required: true });

defineEmits<{
  submit: [];
  close: [];
  openRoleManager: [];
  openMfaHelp: [];
}>();
</script>

<template>
  <el-dialog
    :model-value="true"
    :title="title"
    width="640px"
    class="user-form-dialog"
    :close-on-click-modal="false"
    @update:model-value="(visible) => { if (!visible) $emit('close'); }"
  >
    <el-form :model="form" label-position="top" class="user-form-modal" @submit.prevent="$emit('submit')">
      <el-form-item label="登录名" :required="dialog.mode === 'create'" :error="formErrors.username">
        <el-input v-model.trim="form.username" autofocus autocomplete="username" />
      </el-form-item>

      <el-form-item label="姓名" required :error="formErrors.firstName">
        <el-input v-model.trim="form.firstName" autocomplete="name" placeholder="请输入姓名" />
      </el-form-item>

      <el-form-item label="密码" :required="dialog.mode === 'create'" :error="formErrors.password">
        <el-input
          v-model="form.password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          :placeholder="dialog.mode === 'edit' ? '留空则不修改' : ''"
        >
          <template #append>
            <el-button :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <AppIcon :name="showPassword ? 'eyeOff' : 'eye'" :size="16" />
            </el-button>
          </template>
        </el-input>
      </el-form-item>

      <div class="user-password-meter" :class="passwordStrengthClass">
        <div class="user-password-meter-head">
          <span>{{ passwordHint }}</span>
          <strong v-if="passwordStrengthText">{{ passwordStrengthText }}</strong>
        </div>
        <div class="user-password-meter-track" aria-hidden="true">
          <i v-for="(rule, index) in passwordRules" :key="rule.key" :class="{ active: index < passwordStrength }"></i>
        </div>
      </div>

      <el-form-item v-if="dialog.mode === 'create' || form.password" label="确认密码" required :error="formErrors.confirmPassword || (passwordMismatch ? '两次输入的密码不一致。' : '')">
        <el-input
          v-model="form.confirmPassword"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          placeholder="请再次输入密码"
        />
      </el-form-item>

      <el-form-item label="角色">
        <div class="user-role-line">
          <el-select v-model="primaryRoleId" placeholder="请选择" clearable>
            <el-option v-for="role in roles" :key="role.id" :value="String(role.id)" :label="role.name" />
          </el-select>
          <el-button text type="primary" @click="$emit('openRoleManager')">新建角色</el-button>
        </div>
      </el-form-item>
      <p class="user-form-note">权限最大化原则，组合多个角色权限。</p>

      <el-form-item label="MFA 标识">
        <el-select v-model="form.mfaFlag" placeholder="请选择绑定推送标识" clearable />
      </el-form-item>
      <p class="user-form-note">
        如果启用 MFA（两步验证）则该项为必填。
        <el-button text type="primary" @click="$emit('openMfaHelp')">如何获取 MFA 标识?</el-button>
      </p>

      <el-form-item label="账户状态">
        <el-switch v-model="form.isActive" inline-prompt active-text="启用" inactive-text="禁用" />
      </el-form-item>
      <p v-if="!form.isActive" class="user-inline-warning">当前账户处于禁用状态，保存后不能登录。</p>
      <p v-if="message" class="user-message user-form-message">{{ message }}</p>
    </el-form>

    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" @click="$emit('submit')">{{ submitText }}</el-button>
    </template>
  </el-dialog>
</template>
