<script setup lang="ts">
import { ref } from 'vue';

import LoginBrandIntro from './LoginBrandIntro.vue';
import LoginCatIllustration from './LoginCatIllustration.vue';

const leftPanel = ref<HTMLElement | null>(null);
const catIllustration = ref<InstanceType<typeof LoginCatIllustration> | null>(null);

function getPanelElement() {
  return leftPanel.value;
}

function getSvgElement() {
  return catIllustration.value?.getSvgElement() ?? null;
}

defineExpose({ getPanelElement, getSvgElement });
</script>

<template>
  <aside ref="leftPanel" class="login-left-panel">
    <LoginBrandIntro />
    <LoginCatIllustration ref="catIllustration" />
  </aside>
</template>
