<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { getSliderChallenge, verifySliderChallenge, type SliderChallenge } from '../../../services/auth';
import AppIcon from '@shared/components/AppIcon.vue';

const HANDLE_SIZE = 40;

const props = defineProps<{
  modelValue: string;
  resetKey: number;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const track = ref<HTMLElement | null>(null);
const trackClientWidth = ref(320);
const challenge = ref<SliderChallenge | null>(null);
const knobX = ref(0);
const dragStartX = ref(0);
const dragStartKnobX = ref(0);
const dragStartedAt = ref(0);
const isDragging = ref(false);
const isLoading = ref(false);
const isVerifying = ref(false);
const isVerified = ref(false);
const message = ref('按住滑块拖动');

const maxTravel = computed(() => Math.max(trackClientWidth.value - HANDLE_SIZE, 1));
const targetPosition = computed(() => {
  if (!challenge.value) return 0;
  return (challenge.value.targetX / challenge.value.trackWidth) * maxTravel.value;
});
const fillWidth = computed(() => `${Math.min(knobX.value + HANDLE_SIZE / 2, trackClientWidth.value)}px`);
const knobStyle = computed(() => ({ transform: `translateX(${knobX.value}px)` }));
const targetStyle = computed(() => ({ left: `${targetPosition.value + HANDLE_SIZE / 2}px` }));
const statusText = computed(() => {
  if (isVerified.value) return '验证通过';
  if (isVerifying.value) return '校验中...';
  if (isLoading.value) return '生成验证中...';
  if (challenge.value && message.value === '按住滑块拖动') return '拖动滑块到目标位置';
  return message.value;
});

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function measureTrack() {
  if (!track.value) return;
  trackClientWidth.value = track.value.clientWidth || 320;
}

function resetVisual(nextMessage = '按住滑块拖动') {
  emit('update:modelValue', '');
  isVerified.value = false;
  isDragging.value = false;
  knobX.value = 0;
  message.value = nextMessage;
}

async function loadChallenge(nextMessage = '按住滑块拖动') {
  resetVisual(nextMessage);
  isLoading.value = true;
  try {
    challenge.value = await getSliderChallenge();
  } catch (error) {
    challenge.value = null;
    message.value = error instanceof Error ? error.message : '滑块验证加载失败';
  } finally {
    isLoading.value = false;
  }
}

function startDrag(event: PointerEvent) {
  if (!challenge.value || isLoading.value || isVerifying.value || isVerified.value) return;
  measureTrack();
  event.preventDefault();
  isDragging.value = true;
  dragStartX.value = event.clientX;
  dragStartKnobX.value = knobX.value;
  dragStartedAt.value = performance.now();
  message.value = '对齐目标位置后释放';
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function moveDrag(event: PointerEvent) {
  if (!isDragging.value) return;
  const delta = event.clientX - dragStartX.value;
  knobX.value = clamp(dragStartKnobX.value + delta, 0, maxTravel.value);
}

async function endDrag(event: PointerEvent) {
  if (!isDragging.value) return;
  isDragging.value = false;
  (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId);
  await verifyDrag();
}

async function verifyDrag() {
  if (!challenge.value) return;
  const offsetX = Math.round((knobX.value / maxTravel.value) * challenge.value.trackWidth);
  const elapsedMs = Math.round(performance.now() - dragStartedAt.value);
  isVerifying.value = true;
  try {
    const result = await verifySliderChallenge({
      challengeId: challenge.value.challengeId,
      offsetX,
      elapsedMs,
    });
    emit('update:modelValue', result.sliderToken);
    isVerified.value = true;
    knobX.value = targetPosition.value;
    message.value = '验证通过';
  } catch (error) {
    const nextMessage = error instanceof Error ? `${error.message}，请拖到目标位置` : '滑块验证失败，请拖到目标位置';
    await loadChallenge(nextMessage);
  } finally {
    isVerifying.value = false;
  }
}

watch(
  () => props.resetKey,
  () => {
    void loadChallenge('请重新完成滑块验证');
  }
);

onMounted(() => {
  measureTrack();
  window.addEventListener('resize', measureTrack);
  void loadChallenge();
});

onUnmounted(() => {
  window.removeEventListener('resize', measureTrack);
});
</script>

<template>
  <div class="login-slider" :class="{ dragging: isDragging, verified: isVerified, loading: isLoading || isVerifying }">
    <div ref="track" class="login-slider-track">
      <span v-if="challenge && !isVerified" class="login-slider-target" :style="targetStyle"></span>
      <span class="login-slider-fill" :style="{ width: fillWidth }"></span>
      <span class="login-slider-text">{{ statusText }}</span>
      <button
        class="login-slider-handle"
        type="button"
        :style="knobStyle"
        :disabled="isLoading || isVerifying || isVerified || !challenge"
        aria-label="滑块验证"
        @pointerdown="startDrag"
        @pointermove="moveDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
      >
        <AppIcon :name="isVerified ? 'check' : 'chevronRight'" :size="18" />
      </button>
    </div>
  </div>
</template>
