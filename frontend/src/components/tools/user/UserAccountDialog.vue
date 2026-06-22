<script setup lang="ts">
import AppIcon from '../../common/AppIcon.vue';
import type { PasswordRule, PasswordStrengthLevel } from '../../../composables/usePasswordStrength';
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
  <div class="modal-backdrop user-modal-backdrop">
    <form class="user-form-modal" @submit.prevent="$emit('submit')">
      <header class="user-form-titlebar">
        <h2>{{ title }}</h2>
        <button class="user-modal-close" type="button" aria-label="关闭" @click="$emit('close')">
          <AppIcon name="x" :size="18" />
        </button>
      </header>

      <div class="user-form-body">
        <label :class="['user-form-row', { required: dialog.mode === 'create' }]">
          <span>登录名：</span>
          <input v-model.trim="form.username" :class="{ invalid: formErrors.username }" autofocus autocomplete="username" />
        </label>
        <p v-if="formErrors.username" class="user-form-error user-form-note-indent">{{ formErrors.username }}</p>

        <label class="user-form-row required">
          <span>姓名：</span>
          <input v-model.trim="form.firstName" :class="{ invalid: formErrors.firstName }" autocomplete="name" placeholder="请输入姓名" />
        </label>
        <p v-if="formErrors.firstName" class="user-form-error user-form-note-indent">{{ formErrors.firstName }}</p>

        <label class="user-form-row required">
          <span>密码：</span>
          <div class="user-password-input" :class="{ invalid: formErrors.password }">
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
        <p v-if="formErrors.password" class="user-form-error user-form-note-indent">{{ formErrors.password }}</p>

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
            :class="{ invalid: formErrors.confirmPassword || passwordMismatch }"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="new-password"
            placeholder="请再次输入密码"
          />
        </label>

        <p v-if="formErrors.confirmPassword || passwordMismatch" class="user-form-error user-form-note-indent">
          {{ formErrors.confirmPassword || '两次输入的密码不一致。' }}
        </p>

        <div class="user-form-row">
          <span>角色：</span>
          <div class="user-role-line">
            <select v-model="primaryRoleId">
              <option value="">请选择</option>
              <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
            </select>
            <button class="user-link-button" type="button" @click="$emit('openRoleManager')">新建角色</button>
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
          <button type="button" @click="$emit('openMfaHelp')">如何获取MFA标识?</button>
        </p>

        <p v-if="!form.isActive" class="user-inline-warning user-form-note-indent">当前账号处于禁用状态，保存后不能登录。</p>
        <p v-if="message" class="user-message user-form-message">{{ message }}</p>
      </div>

      <footer class="user-form-actions">
        <button type="button" @click="$emit('close')">取消</button>
        <button class="user-primary-button" type="submit">{{ submitText }}</button>
      </footer>
    </form>
  </div>
</template>
