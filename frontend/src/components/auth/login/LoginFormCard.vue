<script setup lang="ts">
import { computed, ref } from 'vue';

import type { LoginTwoFactorChallenge, LoginTwoFactorSetupChallenge } from '../../../types';
import AppIcon from '../../common/AppIcon.vue';
import LoginSliderVerify from './LoginSliderVerify.vue';

const props = defineProps<{
  account: string;
  password: string;
  remember: boolean;
  sliderToken: string;
  twoFactorCode: string;
  sliderResetKey: number;
  isSubmitting: boolean;
  isVerifyingTwoFactor: boolean;
  errorMessage: string;
  twoFactorChallenge: LoginTwoFactorChallenge | null;
  twoFactorSetupChallenge: LoginTwoFactorSetupChallenge | null;
  canSubmit: boolean;
  canSubmitTwoFactor: boolean;
}>();

const emit = defineEmits<{
  'update:account': [value: string];
  'update:password': [value: string];
  'update:remember': [value: boolean];
  'update:sliderToken': [value: string];
  'update:twoFactorCode': [value: string];
  submit: [];
  submitTwoFactor: [];
  submitTwoFactorSetup: [];
  cancelTwoFactor: [];
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
const twoFactorCodeModel = computed({
  get: () => props.twoFactorCode,
  set: (value: string) => emit('update:twoFactorCode', value.replace(/\D/g, '').slice(0, 6)),
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
    <form v-if="!twoFactorChallenge && !twoFactorSetupChallenge" class="login-form" @submit.prevent="emit('submit')">
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
    <form v-else-if="twoFactorSetupChallenge" class="login-form login-2fa-form login-2fa-setup-form" @submit.prevent="emit('submitTwoFactorSetup')">
      <div class="login-form-brand">
        <img src="/ops-captain-icon.png" alt="运维船长" />
        <strong>运维船长</strong>
      </div>

      <div class="login-method-pill">
        <span></span>
        绑定双因素认证
      </div>

      <h2>绑定 2FA</h2>
      <p class="login-subtitle">{{ twoFactorSetupChallenge.displayName || twoFactorSetupChallenge.account }}，请使用认证器扫码后输入验证码</p>

      <div class="login-2fa-setup-box">
        <img :src="twoFactorSetupChallenge.qrDataUrl" alt="TOTP 二维码" />
        <div>
          <strong>手动密钥</strong>
          <code>{{ twoFactorSetupChallenge.secret }}</code>
        </div>
      </div>

      <label class="login-form-group" for="login-2fa-setup-code">
        <div class="login-input-wrapper login-2fa-input-wrapper">
          <AppIcon name="shield" :size="18" />
          <input
            id="login-2fa-setup-code"
            v-model="twoFactorCodeModel"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="6"
            placeholder="000000"
          />
        </div>
      </label>

      <p class="login-2fa-note">绑定成功后会自动进入系统，旧验证码会立即失效。</p>
      <p v-if="errorMessage" class="login-error">{{ errorMessage }}</p>
      <button class="login-btn" type="submit" :disabled="!canSubmitTwoFactor">
        <span>{{ isVerifyingTwoFactor ? '绑定中...' : '绑定并登录' }}</span>
      </button>
      <button class="login-secondary-btn" type="button" @click="emit('cancelTwoFactor')">返回账号登录</button>
    </form>
    <form v-else-if="twoFactorChallenge" class="login-form login-2fa-form" @submit.prevent="emit('submitTwoFactor')">
      <div class="login-form-brand">
        <img src="/ops-captain-icon.png" alt="运维船长" />
        <strong>运维船长</strong>
      </div>

      <div class="login-method-pill">
        <span></span>
        双因素认证
      </div>

      <h2>安全验证</h2>
      <p class="login-subtitle">{{ twoFactorChallenge.displayName || twoFactorChallenge.account }}，请输入认证器中的 6 位动态验证码</p>

      <label class="login-form-group" for="login-2fa-code">
        <div class="login-input-wrapper login-2fa-input-wrapper">
          <AppIcon name="shield" :size="18" />
          <input
            id="login-2fa-code"
            v-model="twoFactorCodeModel"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="6"
            placeholder="000000"
          />
        </div>
      </label>

      <p class="login-2fa-note">验证码会随时间刷新，如验证失败需要重新完成账号密码登录。</p>
      <p v-if="errorMessage" class="login-error">{{ errorMessage }}</p>
      <button class="login-btn" type="submit" :disabled="!canSubmitTwoFactor">
        <span>{{ isVerifyingTwoFactor ? '验证中...' : '验 证' }}</span>
      </button>
      <button class="login-secondary-btn" type="button" @click="emit('cancelTwoFactor')">返回账号登录</button>
    </form>
  </section>
</template>
