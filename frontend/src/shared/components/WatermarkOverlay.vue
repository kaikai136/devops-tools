<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{ text: string; variant?: 'default' | 'terminal' }>(), {
  variant: 'default',
});

const watermarkText = computed(() => props.text.trim());
</script>

<template>
  <div v-if="watermarkText" class="watermark-overlay" :class="`watermark-${variant}`" aria-hidden="true">
    <div v-for="index in 80" :key="index" class="watermark-overlay-item">{{ watermarkText }}</div>
  </div>
</template>
