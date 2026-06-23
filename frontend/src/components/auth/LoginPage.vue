<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue';

import { useLoginCatAnimation } from '../../composables/auth/useLoginCatAnimation';
import { useLoginForm } from '../../composables/auth/useLoginForm';
import type { LoginPayload } from '../../types';
import LoginFormCard from './login/LoginFormCard.vue';
import LoginVisualPanel from './login/LoginVisualPanel.vue';

const props = defineProps<{
  login: (payload: LoginPayload) => Promise<void>;
}>();

const visualPanel = ref<InstanceType<typeof LoginVisualPanel> | null>(null);
const formCard = ref<InstanceType<typeof LoginFormCard> | null>(null);

const { account, password, remember, isSubmitting, errorMessage, canSubmit, submitLogin } = useLoginForm(props.login);

const catAnimation = useLoginCatAnimation({
  getPanel: () => visualPanel.value?.getPanelElement() ?? null,
  getSvg: () => visualPanel.value?.getSvgElement() ?? null,
  getUsernameInput: () => formCard.value?.getUsernameInputElement() ?? null,
  getPasswordInput: () => formCard.value?.getPasswordInputElement() ?? null,
});

onMounted(async () => {
  await nextTick();
  catAnimation.start();
});
</script>

<template>
  <main class="login-shell">
    <section class="login-container">
      <LoginVisualPanel ref="visualPanel" />
      <LoginFormCard
        ref="formCard"
        v-model:account="account"
        v-model:password="password"
        v-model:remember="remember"
        :is-submitting="isSubmitting"
        :error-message="errorMessage"
        :can-submit="canSubmit"
        @submit="submitLogin"
      />
    </section>
  </main>
</template>
