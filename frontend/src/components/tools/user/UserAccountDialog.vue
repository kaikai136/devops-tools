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
  <NativeDialog
    :model-value="true"
    :title="title"
    width="640px"
    class="user-form-dialog"
    :close-on-click-modal="false"
    @update:model-value="(visible) => { if (!visible) $emit('close'); }"
  >
    <NativeForm :model="form" label-position="top" class="user-form-modal" @submit.prevent="$emit('submit')">
      <NativeFormItem label="登录名" :required="dialog.mode === 'create'" :error="formErrors.username">
        <NativeInput v-model.trim="form.username" autofocus autocomplete="username" />
      </NativeFormItem>

      <NativeFormItem label="姓名" required :error="formErrors.firstName">
        <NativeInput v-model.trim="form.firstName" autocomplete="name" placeholder="请输入姓名" />
      </NativeFormItem>

      <NativeFormItem label="密码" :required="dialog.mode === 'create'" :error="formErrors.password">
        <NativeInput
          v-model="form.password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          :placeholder="dialog.mode === 'edit' ? '留空则不修改' : ''"
        >
          <template #append>
            <NativeButton :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <AppIcon :name="showPassword ? 'eyeOff' : 'eye'" :size="16" />
            </NativeButton>
          </template>
        </NativeInput>
      </NativeFormItem>

      <div class="user-password-meter" :class="passwordStrengthClass">
        <div class="user-password-meter-head">
          <span>{{ passwordHint }}</span>
          <strong v-if="passwordStrengthText">{{ passwordStrengthText }}</strong>
        </div>
        <div class="user-password-meter-track" aria-hidden="true">
          <i v-for="(rule, index) in passwordRules" :key="rule.key" :class="{ active: index < passwordStrength }"></i>
        </div>
      </div>

      <NativeFormItem v-if="dialog.mode === 'create' || form.password" label="确认密码" required :error="formErrors.confirmPassword || (passwordMismatch ? '两次输入的密码不一致。' : '')">
        <NativeInput
          v-model="form.confirmPassword"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          placeholder="请再次输入密码"
        />
      </NativeFormItem>

      <NativeFormItem label="角色">
        <div class="user-role-line">
          <NativeSelect v-model="primaryRoleId" placeholder="请选择" clearable>
            <NativeOption v-for="role in roles" :key="role.id" :value="String(role.id)" :label="role.name" />
          </NativeSelect>
          <NativeButton text type="primary" @click="$emit('openRoleManager')">新建角色</NativeButton>
        </div>
      </NativeFormItem>
      <p class="user-form-note">权限最大化原则，组合多个角色权限。</p>

      <NativeFormItem label="MFA 标识">
        <NativeSelect v-model="form.mfaFlag" placeholder="请选择绑定推送标识" clearable />
      </NativeFormItem>
      <p class="user-form-note">
        如果启用 MFA（两步验证）则该项为必填。
        <NativeButton text type="primary" @click="$emit('openMfaHelp')">如何获取 MFA 标识?</NativeButton>
      </p>

      <NativeFormItem label="账户状态">
        <NativeSwitch v-model="form.isActive" inline-prompt active-text="启用" inactive-text="禁用" />
      </NativeFormItem>
      <p v-if="!form.isActive" class="user-inline-warning">当前账户处于禁用状态，保存后不能登录。</p>
      <p v-if="message" class="user-message user-form-message">{{ message }}</p>
    </NativeForm>

    <template #footer>
      <NativeButton @click="$emit('close')">取消</NativeButton>
      <NativeButton type="primary" @click="$emit('submit')">{{ submitText }}</NativeButton>
    </template>
  </NativeDialog>
</template>
