import { computed, ref } from 'vue';

import type { LoginPayload } from '../../types';

export function useLoginForm(login: (payload: LoginPayload) => Promise<void>) {
  const account = ref('');
  const password = ref('');
  const remember = ref(false);
  const sliderToken = ref('');
  const sliderResetKey = ref(0);
  const isSubmitting = ref(false);
  const errorMessage = ref('');

  const canSubmit = computed(() => Boolean(account.value.trim() && password.value && sliderToken.value && !isSubmitting.value));

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
      await login(payload);
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试';
      sliderToken.value = '';
      sliderResetKey.value += 1;
    } finally {
      isSubmitting.value = false;
    }
  }

  return {
    account,
    password,
    remember,
    sliderToken,
    sliderResetKey,
    isSubmitting,
    errorMessage,
    canSubmit,
    submitLogin,
  };
}
