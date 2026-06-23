<script setup lang="ts">
import { computed, ref } from 'vue';

import AppIcon from '../../common/AppIcon.vue';

const props = defineProps<{
  account: string;
  password: string;
  remember: boolean;
  isSubmitting: boolean;
  errorMessage: string;
  canSubmit: boolean;
}>();

const emit = defineEmits<{
  'update:account': [value: string];
  'update:password': [value: string];
  'update:remember': [value: boolean];
  submit: [];
}>();

const usernameInput = ref<HTMLInputElement | null>(null);
const passwordInput = ref<HTMLInputElement | null>(null);

const accountModel = computed({
  get: () => props.account,
  set: (value: string) => emit('update:account', value),
});
const passwordModel = computed({
  get: () => props.password,
  set: (value: string) => emit('update:password', value),
});
const rememberModel = computed({
  get: () => props.remember,
  set: (value: boolean) => emit('update:remember', value),
});

function getUsernameInputElement() {
  return usernameInput.value;
}

function getPasswordInputElement() {
  return passwordInput.value;
}

defineExpose({ getUsernameInputElement, getPasswordInputElement });
</script>

<template>
  <section class="login-right-panel">
    <form class="login-card" @submit.prevent="emit('submit')">
      <h2>账号登录</h2>
      <p class="login-subtitle">请输入账号信息，安全进入管理平台。</p>

      <label class="login-form-group" for="login-account">
        <span>用户名</span>
        <div class="login-input-wrapper">
          <AppIcon name="user" :size="18" />
          <input id="login-account" ref="usernameInput" v-model="accountModel" type="text" autocomplete="username" placeholder="请输入用户名" />
        </div>
      </label>

      <label class="login-form-group" for="login-password">
        <span>密码</span>
        <div class="login-input-wrapper">
          <AppIcon name="lock" :size="18" />
          <input id="login-password" ref="passwordInput" v-model="passwordModel" type="password" autocomplete="current-password" placeholder="请输入密码" />
        </div>
      </label>

      <div class="login-options">
        <label class="login-remember">
          <input v-model="rememberModel" type="checkbox" />
          记住我
        </label>
      </div>

      <p v-if="errorMessage" class="login-error">{{ errorMessage }}</p>
      <button class="login-btn" type="submit" :disabled="!canSubmit">
        <span>{{ isSubmitting ? '登录中...' : '登录' }}</span>
      </button>
    </form>
  </section>
</template>
