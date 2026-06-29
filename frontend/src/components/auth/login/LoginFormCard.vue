<script setup lang="ts">
import { computed, ref } from 'vue';

import AppIcon from '../../common/AppIcon.vue';
import LoginSliderVerify from './LoginSliderVerify.vue';

const props = defineProps<{
  account: string;
  password: string;
  remember: boolean;
  sliderToken: string;
  sliderResetKey: number;
  isSubmitting: boolean;
  errorMessage: string;
  canSubmit: boolean;
}>();

const emit = defineEmits<{
  'update:account': [value: string];
  'update:password': [value: string];
  'update:remember': [value: boolean];
  'update:sliderToken': [value: string];
  submit: [];
}>();

const usernameInput = ref<HTMLInputElement | null>(null);
const passwordInput = ref<HTMLInputElement | null>(null);
const showPassword = ref(false);

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
const sliderTokenModel = computed({
  get: () => props.sliderToken,
  set: (value: string) => emit('update:sliderToken', value),
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
    <div class="login-form-glass" aria-hidden="true"></div>
    <form class="login-form" @submit.prevent="emit('submit')">
      <div class="login-form-brand">
        <img src="/ops-captain-icon.png" alt="运维船长" />
        <strong>运维船长</strong>
      </div>

      <div class="login-method-pill">
        <span></span>
        账号密码登录
      </div>

      <h2>登 录</h2>
      <p class="login-subtitle">请输入用户名 · 请输入密码</p>

      <label class="login-form-group" for="login-account">
        <div class="login-input-wrapper">
          <AppIcon name="user" :size="18" />
          <input id="login-account" ref="usernameInput" v-model="accountModel" type="text" autocomplete="username" placeholder="请输入用户名" />
        </div>
      </label>

      <label class="login-form-group" for="login-password">
        <div class="login-input-wrapper">
          <AppIcon name="lock" :size="18" />
          <input
            id="login-password"
            ref="passwordInput"
            v-model="passwordModel"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
          <button class="login-password-toggle" type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
            <AppIcon :name="showPassword ? 'eyeOff' : 'eye'" :size="16" />
          </button>
        </div>
      </label>

      <div class="login-options">
        <label class="login-remember">
          <input v-model="rememberModel" type="checkbox" />
          记住我
        </label>
      </div>

      <LoginSliderVerify v-model="sliderTokenModel" :reset-key="sliderResetKey" />

      <p v-if="errorMessage" class="login-error">{{ errorMessage }}</p>
      <button class="login-btn" type="submit" :disabled="!canSubmit">
        <span>{{ isSubmitting ? '登录中...' : '登 录' }}</span>
      </button>
    </form>
  </section>
</template>
