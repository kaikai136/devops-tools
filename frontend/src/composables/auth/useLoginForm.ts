import { computed, ref } from 'vue';

import type { LoginPayload, LoginResult, LoginTwoFactorChallenge, LoginTwoFactorSetupChallenge } from '../../types';

export function useLoginForm(
  login: (payload: LoginPayload) => Promise<LoginResult>,
  verifyTwoFactorLogin: (code: string) => Promise<unknown>,
  verifyTwoFactorSetupLogin: (code: string) => Promise<unknown>,
) {
  const account = ref('');
  const password = ref('');
  const remember = ref(false);
  const sliderToken = ref('');
  const sliderResetKey = ref(0);
  const isSubmitting = ref(false);
  const isVerifyingTwoFactor = ref(false);
  const errorMessage = ref('');
  const twoFactorCode = ref('');
  const twoFactorChallenge = ref<LoginTwoFactorChallenge | null>(null);
  const twoFactorSetupChallenge = ref<LoginTwoFactorSetupChallenge | null>(null);

  const canSubmit = computed(() => Boolean(account.value.trim() && password.value && sliderToken.value && !isSubmitting.value));
  const canSubmitTwoFactor = computed(() => /^\d{6}$/.test(twoFactorCode.value.trim()) && !isVerifyingTwoFactor.value);

  async function submitLogin() {
    errorMessage.value = '';
    const payload = {
      account: account.value.trim(),
      password: password.value,
      remember: remember.value,
      sliderToken: sliderToken.value,
    };

    if (!payload.account || !payload.password) {
      errorMessage.value = '请输入账号和密码';
      return;
    }
    if (!payload.sliderToken) {
      errorMessage.value = '请先完成滑块验证';
      return;
    }

    isSubmitting.value = true;
    try {
      const result = await login(payload);
      if ('twoFactorRequired' in result) {
        twoFactorChallenge.value = result;
        twoFactorSetupChallenge.value = null;
        twoFactorCode.value = '';
      } else if ('twoFactorSetupRequired' in result) {
        twoFactorSetupChallenge.value = result;
        twoFactorChallenge.value = null;
        twoFactorCode.value = '';
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试';
      sliderToken.value = '';
      sliderResetKey.value += 1;
    } finally {
      isSubmitting.value = false;
    }
  }

  async function submitTwoFactor() {
    errorMessage.value = '';
    const code = twoFactorCode.value.trim();
    if (!/^\d{6}$/.test(code)) {
      errorMessage.value = '请输入 6 位动态验证码';
      return;
    }

    isVerifyingTwoFactor.value = true;
    try {
      await verifyTwoFactorLogin(code);
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '验证码验证失败，请重新登录';
      twoFactorChallenge.value = null;
      twoFactorCode.value = '';
      password.value = '';
      sliderToken.value = '';
      sliderResetKey.value += 1;
    } finally {
      isVerifyingTwoFactor.value = false;
    }
  }

  async function submitTwoFactorSetup() {
    errorMessage.value = '';
    const code = twoFactorCode.value.trim();
    if (!/^\d{6}$/.test(code)) {
      errorMessage.value = '请输入 6 位动态验证码';
      return;
    }

    isVerifyingTwoFactor.value = true;
    try {
      await verifyTwoFactorSetupLogin(code);
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '绑定失败，请确认验证码后重试';
      twoFactorCode.value = '';
    } finally {
      isVerifyingTwoFactor.value = false;
    }
  }

  function cancelTwoFactor() {
    twoFactorChallenge.value = null;
    twoFactorSetupChallenge.value = null;
    twoFactorCode.value = '';
    password.value = '';
    sliderToken.value = '';
    sliderResetKey.value += 1;
    errorMessage.value = '';
  }

  return {
    account,
    password,
    remember,
    sliderToken,
    sliderResetKey,
    isSubmitting,
    isVerifyingTwoFactor,
    errorMessage,
    twoFactorCode,
    twoFactorChallenge,
    twoFactorSetupChallenge,
    canSubmit,
    canSubmitTwoFactor,
    submitLogin,
    submitTwoFactor,
    submitTwoFactorSetup,
    cancelTwoFactor,
  };
}
