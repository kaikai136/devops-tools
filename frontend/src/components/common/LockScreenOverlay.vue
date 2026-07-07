<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { errorMessage } from '../../utils/errors';
import AppIcon from './AppIcon.vue';
import UserAvatar from './UserAvatar.vue';

interface WaterfallColumn {
  id: number;
  left: number;
  width: number;
  delay: number;
  duration: number;
}

const props = defineProps<{
  locked: boolean;
  avatarUrl: string;
  username?: string;
  displayName: string;
  firstName?: string;
  account: string;
  unlockSession: (password: string) => Promise<unknown>;
  logout: () => Promise<void>;
}>();

const visible = ref(false);
const covering = ref(false);
const contentVisible = ref(false);
const exiting = ref(false);
const shaking = ref(false);
const password = ref('');
const message = ref('');
const progress = ref(0);
const isDragging = ref(false);
const isSubmitting = ref(false);
const columns = ref<WaterfallColumn[]>([]);
const sliderTrack = ref<HTMLElement | null>(null);
const passwordInput = ref<HTMLInputElement | null>(null);
let revealTimer: number | undefined;
let hideTimer: number | undefined;

const sliderStyle = computed(() => ({ '--unlock-progress': `${progress.value * 100}%` }));
const canSubmit = computed(() => Boolean(password.value.trim()) && !isSubmitting.value);

watch(
  () => props.locked,
  (locked) => {
    window.clearTimeout(revealTimer);
    window.clearTimeout(hideTimer);
    if (locked) {
      showOverlay();
      return;
    }
    hideOverlay();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  removeDragListeners();
  window.clearTimeout(revealTimer);
  window.clearTimeout(hideTimer);
});

function showOverlay() {
  generateColumns();
  visible.value = true;
  exiting.value = false;
  contentVisible.value = false;
  password.value = '';
  message.value = '';
  progress.value = 0;
  nextTick(() => {
    covering.value = true;
    revealTimer = window.setTimeout(() => {
      contentVisible.value = true;
      nextTick(() => passwordInput.value?.focus());
    }, 900);
  });
}

function hideOverlay() {
  if (!visible.value) return;
  contentVisible.value = false;
  covering.value = false;
  exiting.value = true;
  removeDragListeners();
  hideTimer = window.setTimeout(() => {
    visible.value = false;
    exiting.value = false;
    progress.value = 0;
    password.value = '';
    message.value = '';
  }, 520);
}

function generateColumns() {
  const width = typeof window === 'undefined' ? 1440 : window.innerWidth;
  const targetWidth = width < 720 ? 42 : 58;
  const count = Math.max(12, Math.ceil(width / targetWidth));
  columns.value = Array.from({ length: count }, (_, index) => ({
    id: index,
    left: (index / count) * 100,
    width: 100 / count + 0.4,
    delay: index * 28 + (index % 4) * 24,
    duration: 520 + (index % 5) * 46,
  }));
}

function beginDrag(event: PointerEvent) {
  if (isSubmitting.value) return;
  message.value = '';
  isDragging.value = true;
  updateProgress(event);
  window.addEventListener('pointermove', updateProgress);
  window.addEventListener('pointerup', finishDrag);
  window.addEventListener('pointercancel', cancelDrag);
}

function updateProgress(event: PointerEvent) {
  const track = sliderTrack.value;
  if (!track) return;
  const rect = track.getBoundingClientRect();
  const next = (event.clientX - rect.left) / rect.width;
  progress.value = Math.min(1, Math.max(0, next));
}

async function finishDrag() {
  removeDragListeners();
  isDragging.value = false;
  if (progress.value < 0.9) {
    progress.value = 0;
    return;
  }
  progress.value = 1;
  await submitUnlock();
}

function cancelDrag() {
  removeDragListeners();
  isDragging.value = false;
  progress.value = 0;
}

function removeDragListeners() {
  window.removeEventListener('pointermove', updateProgress);
  window.removeEventListener('pointerup', finishDrag);
  window.removeEventListener('pointercancel', cancelDrag);
}

async function submitUnlock() {
  if (!canSubmit.value) {
    failUnlock('请输入锁屏密码');
    return;
  }
  isSubmitting.value = true;
  message.value = '';
  try {
    await props.unlockSession(password.value);
  } catch (error) {
    failUnlock(errorMessage(error));
  } finally {
    isSubmitting.value = false;
  }
}

function failUnlock(text: string) {
  message.value = text;
  progress.value = 0;
  shaking.value = true;
  nextTick(() => passwordInput.value?.focus());
  window.setTimeout(() => {
    shaking.value = false;
  }, 360);
}

function submitFromKeyboard() {
  failUnlock(password.value.trim() ? '请滑动解锁' : '请输入锁屏密码');
}
</script>

<template>
  <Teleport to="body">
    <section
      v-if="visible"
      class="lock-screen-overlay"
      :class="{ covering, exiting, 'content-visible': contentVisible, shaking }"
      aria-modal="true"
      role="dialog"
      aria-label="锁定屏幕"
    >
      <div class="lock-screen-waterfall" aria-hidden="true">
        <i
          v-for="column in columns"
          :key="column.id"
          :style="{
            left: `${column.left}%`,
            width: `${column.width}%`,
            transitionDelay: `${column.delay}ms`,
            transitionDuration: `${column.duration}ms`,
          }"
        ></i>
      </div>

      <div class="lock-screen-blur" aria-hidden="true"></div>

      <form class="lock-screen-panel" @submit.prevent="submitFromKeyboard">
        <UserAvatar
          class="lock-screen-avatar"
          :src="avatarUrl"
          :username="username"
          :display-name="displayName"
          :first-name="firstName"
          size="xl"
        />
        <h2>{{ displayName }}</h2>
        <p>{{ account }}</p>

        <div
          ref="sliderTrack"
          class="lock-screen-slider"
          :class="{ dragging: isDragging, complete: progress >= 0.9 }"
          :style="sliderStyle"
          @pointerdown.prevent="beginDrag"
        >
          <span class="lock-screen-slider-fill"></span>
          <button class="lock-screen-slider-handle" type="button" tabindex="-1" aria-hidden="true">
            <AppIcon name="moveRight" :size="21" />
          </button>
          <strong>{{ isSubmitting ? '正在解锁' : '滑动解锁' }}</strong>
        </div>

        <input
          ref="passwordInput"
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="请输入锁屏密码..."
          :disabled="isSubmitting"
        />
        <span v-if="message" class="lock-screen-message">{{ message }}</span>

        <button class="lock-screen-hidden-submit" type="submit">解锁</button>
        <button class="lock-screen-logout" type="button" :disabled="isSubmitting" @click="logout">
          忘记密码？返回登录
        </button>
      </form>
    </section>
  </Teleport>
</template>
