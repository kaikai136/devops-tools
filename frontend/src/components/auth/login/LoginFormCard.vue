<script setup lang="ts">
import { computed, ref } from 'vue';
import type { InputInstance } from 'element-plus';

import { useAppContext } from '@app/context';
import type { LoginTwoFactorChallenge, LoginTwoFactorSetupChallenge } from '../../../types';
import AppIcon from '@shared/components/AppIcon.vue';
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

const usernameInput = ref<InputInstance | null>(null);
const passwordInput = ref<InputInstance | null>(null);
const { siteIdentity, loginContent, renderSystemTemplate } = useAppContext();

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
const formBadge = computed(() => renderSystemTemplate(loginContent.value.badgeTemplate));
const formTitle = computed(() => renderSystemTemplate(loginContent.value.title));
const formDescription = computed(() => renderSystemTemplate(loginContent.value.description));

function getUsernameInputElement() {
  return usernameInput.value?.input ?? null;
}

function getPasswordInputElement() {
  return passwordInput.value?.input ?? null;
}

defineExpose({ getUsernameInputElement, getPasswordInputElement });
</script>

<template>
  <section class="login-right-panel">
    <div class="login-form-glass" aria-hidden="true"></div>
    <form v-if="!twoFactorChallenge && !twoFactorSetupChallenge" class="login-form" @submit.prevent="emit('submit')">
      <div class="login-form-brand">
        <img :src="siteIdentity.iconUrl" :alt="siteIdentity.appName" />
        <strong>{{ siteIdentity.appName }}</strong>
      </div>

      <div class="login-method-pill">
        <span></span>
        {{ formBadge }}
      </div>

      <h2>{{ formTitle }}</h2>
      <p class="login-subtitle">{{ formDescription }}</p>

      <label class="login-form-group" for="login-account">
        <el-input id="login-account" ref="usernameInput" v-model="accountModel" class="login-field" autocomplete="username" placeholder="请输入用户名">
          <template #prefix>
            <AppIcon name="user" :size="18" />
          </template>
        </el-input>
      </label>

      <label class="login-form-group" for="login-password">
        <el-input
          id="login-password"
          ref="passwordInput"
          v-model="passwordModel"
          class="login-field"
          type="password"
          autocomplete="current-password"
          placeholder="请输入密码"
          show-password
        >
          <template #prefix>
            <AppIcon name="lock" :size="18" />
          </template>
        </el-input>
      </label>

      <div class="login-options">
        <el-checkbox v-model="rememberModel" class="login-remember">
          记住我
        </el-checkbox>
      </div>

      <LoginSliderVerify v-model="sliderTokenModel" :reset-key="sliderResetKey" />

      <el-alert v-if="errorMessage" class="login-error" type="error" :closable="false" :title="errorMessage" />
      <el-button class="login-btn" native-type="submit" type="primary" :disabled="!canSubmit" :loading="isSubmitting">
        <span>{{ isSubmitting ? '登录中...' : '登 录' }}</span>
      </el-button>
    </form>
    <form v-else-if="twoFactorSetupChallenge" class="login-form login-2fa-form login-2fa-setup-form" @submit.prevent="emit('submitTwoFactorSetup')">
      <div class="login-form-brand">
        <img :src="siteIdentity.iconUrl" :alt="siteIdentity.appName" />
        <strong>{{ siteIdentity.appName }}</strong>
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
        <el-input
          id="login-2fa-setup-code"
          v-model="twoFactorCodeModel"
          class="login-field login-2fa-field"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          placeholder="000000"
        >
          <template #prefix>
            <AppIcon name="shield" :size="18" />
          </template>
        </el-input>
      </label>

      <p class="login-2fa-note">绑定成功后会自动进入系统，旧验证码会立即失效。</p>
      <el-alert v-if="errorMessage" class="login-error" type="error" :closable="false" :title="errorMessage" />
      <el-button class="login-btn" native-type="submit" type="primary" :disabled="!canSubmitTwoFactor" :loading="isVerifyingTwoFactor">
        <span>{{ isVerifyingTwoFactor ? '绑定中...' : '绑定并登录' }}</span>
      </el-button>
      <el-button class="login-secondary-btn" @click="emit('cancelTwoFactor')">返回账号登录</el-button>
    </form>
    <form v-else-if="twoFactorChallenge" class="login-form login-2fa-form" @submit.prevent="emit('submitTwoFactor')">
      <div class="login-form-brand">
        <img :src="siteIdentity.iconUrl" :alt="siteIdentity.appName" />
        <strong>{{ siteIdentity.appName }}</strong>
      </div>

      <div class="login-method-pill">
        <span></span>
        双因素认证
      </div>

      <h2>安全验证</h2>
      <p class="login-subtitle">{{ twoFactorChallenge.displayName || twoFactorChallenge.account }}，请输入认证器中的 6 位动态验证码</p>

      <label class="login-form-group" for="login-2fa-code">
        <el-input
          id="login-2fa-code"
          v-model="twoFactorCodeModel"
          class="login-field login-2fa-field"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          placeholder="000000"
        >
          <template #prefix>
            <AppIcon name="shield" :size="18" />
          </template>
        </el-input>
      </label>

      <p class="login-2fa-note">验证码会随时间刷新，如验证失败需要重新完成账号密码登录。</p>
      <el-alert v-if="errorMessage" class="login-error" type="error" :closable="false" :title="errorMessage" />
      <el-button class="login-btn" native-type="submit" type="primary" :disabled="!canSubmitTwoFactor" :loading="isVerifyingTwoFactor">
        <span>{{ isVerifyingTwoFactor ? '验证中...' : '验 证' }}</span>
      </el-button>
      <el-button class="login-secondary-btn" @click="emit('cancelTwoFactor')">返回账号登录</el-button>
    </form>
  </section>
</template>
