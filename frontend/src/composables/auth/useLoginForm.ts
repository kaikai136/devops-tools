import { computed, ref } from 'vue';

import type { LoginPayload } from '../../types';

export function useLoginForm(login: (payload: LoginPayload) => Promise<void>) {
  const account = ref('');
  const password = ref('');
  const remember = ref(false);
  const isSubmitting = ref(false);
  const errorMessage = ref('');

  const canSubmit = computed(() => Boolean(account.value.trim() && password.value && !isSubmitting.value));

  async function submitLogin() {
    errorMessage.value = '';
    const payload = {
      account: account.value.trim(),
      password: password.value,
      remember: remember.value,
    };

    if (!payload.account || !payload.password) {
      errorMessage.value = '请输入账号和密码';
      return;
    }

    isSubmitting.value = true;
    try {
      await login(payload);
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试';
    } finally {
      isSubmitting.value = false;
    }
  }

  return {
    account,
    password,
    remember,
    isSubmitting,
    errorMessage,
    canSubmit,
    submitLogin,
  };
}
