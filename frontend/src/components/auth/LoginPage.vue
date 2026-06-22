<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';

import type { LoginPayload } from '../../types';
import AppIcon from '../common/AppIcon.vue';

const props = defineProps<{
  login: (payload: LoginPayload) => Promise<void>;
}>();

const account = ref('');
const password = ref('');
const remember = ref(false);
const isSubmitting = ref(false);
const errorMessage = ref('');
const leftPanel = ref<HTMLElement | null>(null);
const catSvg = ref<SVGSVGElement | null>(null);
const usernameInput = ref<HTMLInputElement | null>(null);
const passwordInput = ref<HTMLInputElement | null>(null);
let cleanupCatAnimation: (() => void) | undefined;

const canSubmit = computed(() => account.value.trim() && password.value && !isSubmitting.value);

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
    await props.login(payload);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试';
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(() => {
  const panel = leftPanel.value;
  const svg = catSvg.value;
  const userInput = usernameInput.value;
  const passInput = passwordInput.value;
  if (!panel || !svg || !userInput || !passInput) return;

  const pupilNodes = Array.from(svg.querySelectorAll<SVGGElement>('.cat-pupil'));
  const headGroup = svg.querySelector<SVGGElement>('.cat-head-group');
  const neckGroup = svg.querySelector<SVGGElement>('.cat-neck-group');
  const whiskersGroup = svg.querySelector<SVGGElement>('.cat-whiskers-group');
  if (!pupilNodes.length || !headGroup || !neckGroup) return;

  const pupils = pupilNodes.map((node) => ({
    node,
    cx: Number(node.dataset.eyeX),
    cy: Number(node.dataset.eyeY),
    x: 0,
    y: 0,
    targetX: 0,
    targetY: 0,
  }));

  const pose = {
    headX: 0,
    headY: 0,
    headRot: 0,
    neckX: 0,
    neckY: 0,
    neckRot: 0,
    neckScale: 1,
    whiskerX: 0,
    whiskerRot: 0,
    targetHeadX: 0,
    targetHeadY: 0,
    targetHeadRot: 0,
    targetNeckX: 0,
    targetNeckY: 0,
    targetNeckRot: 0,
    targetNeckScale: 1,
    targetWhiskerX: 0,
    targetWhiskerRot: 0,
  };

  const maxMoveNormal = 7.5;
  const maxMovePeek = 8.5;
  const influenceRange = 145;
  let pointerInside = false;
  let lastFrameTime = performance.now();
  let lastPointer: { x: number; y: number; time: number } | null = null;
  let pointerSpeed = 0;
  let usernameFocused = false;
  let frameId = 0;

  function clamp(value: number, min: number, max: number) {
    return Math.max(min, Math.min(max, value));
  }

  function clientToSvgPoint(clientX: number, clientY: number) {
    const matrix = svg.getScreenCTM();
    if (!matrix) return null;

    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    return point.matrixTransform(matrix.inverse());
  }

  function pointEyesAt(clientX: number, clientY: number, maxMove: number) {
    const target = clientToSvgPoint(clientX, clientY);
    if (!target) return;

    pupils.forEach((eye) => {
      const dx = target.x - eye.cx;
      const dy = target.y - eye.cy;
      const distance = Math.hypot(dx, dy) || 1;
      const strength = clamp(distance / influenceRange, 0, 1);
      eye.targetX = (dx / distance) * maxMove * strength;
      eye.targetY = (dy / distance) * maxMove * strength;
    });
  }

  function updatePointerSpeed(clientX: number, clientY: number) {
    const now = performance.now();
    if (!lastPointer) {
      lastPointer = { x: clientX, y: clientY, time: now };
      pointerSpeed = 0;
      return;
    }

    const dx = clientX - lastPointer.x;
    const dy = clientY - lastPointer.y;
    const dt = Math.max(now - lastPointer.time, 8);
    pointerSpeed = (Math.hypot(dx, dy) / dt) * 1000;
    lastPointer = { x: clientX, y: clientY, time: now };
  }

  function updateFromLeftPanelPointer(event: PointerEvent) {
    updatePointerSpeed(event.clientX, event.clientY);
    pointEyesAt(event.clientX, event.clientY, maxMoveNormal);
  }

  function updatePeekToUsername() {
    const rect = userInput.getBoundingClientRect();
    pointEyesAt(rect.left + rect.width * 0.24, rect.top + rect.height * 0.5, maxMovePeek);
  }

  function updatePoseTargets() {
    if (usernameFocused) {
      pose.targetHeadX = 28;
      pose.targetHeadY = -12;
      pose.targetHeadRot = 6.5;
      pose.targetNeckX = 24;
      pose.targetNeckY = -1;
      pose.targetNeckRot = -20;
      pose.targetNeckScale = 1.82;
      pose.targetWhiskerX = 10;
      pose.targetWhiskerRot = 5;
      updatePeekToUsername();
      return;
    }

    pose.targetHeadX = 0;
    pose.targetHeadY = 0;
    pose.targetHeadRot = 0;
    pose.targetNeckX = 0;
    pose.targetNeckY = 0;
    pose.targetNeckRot = 0;
    pose.targetNeckScale = 1;
    pose.targetWhiskerX = 0;
    pose.targetWhiskerRot = 0;

    if (!pointerInside) {
      pupils.forEach((eye) => {
        eye.targetX = 0;
        eye.targetY = 0;
      });
    }
  }

  function applyTransforms() {
    headGroup.setAttribute('transform', `translate(${pose.headX.toFixed(2)} ${pose.headY.toFixed(2)}) rotate(${pose.headRot.toFixed(2)} 210 188)`);
    neckGroup.setAttribute(
      'transform',
      `translate(${pose.neckX.toFixed(2)} ${pose.neckY.toFixed(2)}) rotate(${pose.neckRot.toFixed(2)} 210 196) translate(210 196) scale(1 ${pose.neckScale.toFixed(3)}) translate(-210 -196)`
    );
    whiskersGroup?.setAttribute('transform', `translate(${pose.whiskerX.toFixed(2)} 0) rotate(${pose.whiskerRot.toFixed(2)} 210 214)`);
    pupils.forEach((eye) => {
      eye.node.setAttribute('transform', `translate(${eye.x.toFixed(2)} ${eye.y.toFixed(2)})`);
    });
  }

  function animate(now: number) {
    const delta = Math.min(now - lastFrameTime, 34);
    lastFrameTime = now;
    updatePoseTargets();

    const speedEase = clamp(pointerSpeed / 2600, 0, 0.36);
    const eyesBaseEase = usernameFocused ? 0.26 : pointerInside ? 0.3 + speedEase : 0.12;
    const bodyBaseEase = usernameFocused ? 0.22 : 0.14;
    const eyesEase = 1 - Math.pow(1 - eyesBaseEase, delta / 16.67);
    const bodyEase = 1 - Math.pow(1 - bodyBaseEase, delta / 16.67);

    pupils.forEach((eye) => {
      eye.x += (eye.targetX - eye.x) * eyesEase;
      eye.y += (eye.targetY - eye.y) * eyesEase;
    });

    pose.headX += (pose.targetHeadX - pose.headX) * bodyEase;
    pose.headY += (pose.targetHeadY - pose.headY) * bodyEase;
    pose.headRot += (pose.targetHeadRot - pose.headRot) * bodyEase;
    pose.neckX += (pose.targetNeckX - pose.neckX) * bodyEase;
    pose.neckY += (pose.targetNeckY - pose.neckY) * bodyEase;
    pose.neckRot += (pose.targetNeckRot - pose.neckRot) * bodyEase;
    pose.neckScale += (pose.targetNeckScale - pose.neckScale) * bodyEase;
    pose.whiskerX += (pose.targetWhiskerX - pose.whiskerX) * bodyEase;
    pose.whiskerRot += (pose.targetWhiskerRot - pose.whiskerRot) * bodyEase;

    applyTransforms();
    pointerSpeed *= 0.86;
    frameId = requestAnimationFrame(animate);
  }

  const handlePointerEnter = (event: PointerEvent) => {
    pointerInside = true;
    if (!usernameFocused) updateFromLeftPanelPointer(event);
  };
  const handlePointerMove = (event: PointerEvent) => {
    pointerInside = true;
    if (!usernameFocused) updateFromLeftPanelPointer(event);
  };
  const handlePointerLeave = () => {
    pointerInside = false;
    lastPointer = null;
    pointerSpeed = 0;
  };
  const handleUsernameFocus = () => {
    usernameFocused = true;
  };
  const handleUsernameBlur = () => {
    usernameFocused = false;
  };
  const handlePasswordFocus = () => {
    usernameFocused = false;
  };

  panel.addEventListener('pointerenter', handlePointerEnter);
  panel.addEventListener('pointermove', handlePointerMove);
  panel.addEventListener('pointerleave', handlePointerLeave);
  userInput.addEventListener('focus', handleUsernameFocus);
  userInput.addEventListener('blur', handleUsernameBlur);
  userInput.addEventListener('pointerdown', handleUsernameFocus);
  passInput.addEventListener('focus', handlePasswordFocus);
  frameId = requestAnimationFrame(animate);

  cleanupCatAnimation = () => {
    cancelAnimationFrame(frameId);
    panel.removeEventListener('pointerenter', handlePointerEnter);
    panel.removeEventListener('pointermove', handlePointerMove);
    panel.removeEventListener('pointerleave', handlePointerLeave);
    userInput.removeEventListener('focus', handleUsernameFocus);
    userInput.removeEventListener('blur', handleUsernameBlur);
    userInput.removeEventListener('pointerdown', handleUsernameFocus);
    passInput.removeEventListener('focus', handlePasswordFocus);
  };
});

onUnmounted(() => {
  cleanupCatAnimation?.();
});
</script>

<template>
  <main class="login-shell">
    <section class="login-container">
      <aside ref="leftPanel" class="login-left-panel">
        <div class="login-brand">
          <div class="login-brand-badge">
            <span></span>
            运维船长 · Secure Console
          </div>
          <h1>欢迎回来</h1>
          <p>登录管理平台，继续处理网络、主机和系统管理任务。小黄猫会悄悄看一眼账号输入框。</p>
        </div>

        <div class="cat-box">
          <div class="cat-shadow"></div>
          <svg ref="catSvg" class="cat-svg" viewBox="0 0 420 340" xmlns="http://www.w3.org/2000/svg" aria-label="黄色机器猫插画">
            <defs>
              <linearGradient id="bodyYellow" x1="112" y1="110" x2="302" y2="300" gradientUnits="userSpaceOnUse">
                <stop offset="0" stop-color="#ffe26a" />
                <stop offset="0.56" stop-color="#ffd049" />
                <stop offset="1" stop-color="#f2af24" />
              </linearGradient>
              <linearGradient id="earYellow" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#ffe46b" />
                <stop offset="1" stop-color="#f5b52e" />
              </linearGradient>
              <linearGradient id="eyeGlow" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#fffbdc" />
                <stop offset="1" stop-color="#fff0a4" />
              </linearGradient>
              <filter id="softShadow" x="-20%" y="-20%" width="140%" height="150%">
                <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#1f2937" flood-opacity="0.2" />
              </filter>
            </defs>

            <path d="M132 150 C172 64 250 64 292 150" fill="none" stroke="#9aa5b8" stroke-width="12" stroke-linecap="round" opacity="0.55" />
            <g class="cat-body-group">
              <path d="M115 247 C115 207 138 179 173 170 C184 150 195 143 210 143 C225 143 236 150 247 170 C282 179 305 207 305 247 C305 277 290 292 261 292 L159 292 C129 292 115 277 115 247 Z" fill="url(#bodyYellow)" stroke="#c98f1c" stroke-width="4" filter="url(#softShadow)" />
              <path d="M248 288 C265 300 290 297 301 281 C282 284 264 284 248 288 Z" fill="#efb232" opacity="0.88" />
            </g>

            <g class="cat-neck-group">
              <path d="M190 165 C196 155 204 151 210 151 C216 151 224 155 230 165 L228 208 C222 214 217 216 210 216 C203 216 198 214 192 208 Z" fill="#f8c439" stroke="#c98f1c" stroke-width="3" opacity="0.98" />
              <path d="M198 168 C203 162 207 159 210 159 C213 159 217 162 222 168 L221 203 C217 207 214 209 210 209 C206 209 203 207 199 203 Z" fill="#ffd95c" opacity="0.55" />
            </g>

            <g class="cat-head-group">
              <g transform="rotate(-39 127 112)" filter="url(#softShadow)">
                <rect x="102" y="57" width="50" height="84" rx="17" fill="url(#earYellow)" stroke="#d99a1a" stroke-width="3" />
                <rect x="116" y="80" width="25" height="42" rx="9" fill="#ff9a83" opacity="0.68" />
              </g>
              <g transform="rotate(39 291 112)" filter="url(#softShadow)">
                <rect x="266" y="57" width="50" height="84" rx="17" fill="url(#earYellow)" stroke="#d99a1a" stroke-width="3" />
                <rect x="280" y="80" width="25" height="42" rx="9" fill="#ff9a83" opacity="0.68" />
              </g>
              <path d="M129 188 C129 140 165 104 210 104 C255 104 291 140 291 188 C291 214 276 230 249 236 L171 236 C144 230 129 214 129 188 Z" fill="url(#bodyYellow)" stroke="#c98f1c" stroke-width="4" filter="url(#softShadow)" />
              <ellipse cx="210" cy="176" rx="72" ry="53" fill="#ffdc63" opacity="0.48" />
              <ellipse cx="168" cy="184" rx="34" ry="27" fill="url(#eyeGlow)" opacity="0.96" />
              <ellipse cx="252" cy="184" rx="34" ry="27" fill="url(#eyeGlow)" opacity="0.96" />
              <ellipse class="cat-eye-white" cx="183" cy="173" rx="16" ry="22" fill="#ffffff" stroke="#dfe5ef" stroke-width="2.5" />
              <ellipse class="cat-eye-white" cx="235" cy="173" rx="16" ry="22" fill="#ffffff" stroke="#dfe5ef" stroke-width="2.5" />
              <g class="cat-pupil" data-eye-x="183" data-eye-y="173">
                <circle cx="183" cy="175" r="8" fill="#1f2937" />
                <circle cx="180" cy="171" r="3.2" fill="#ffffff" />
              </g>
              <g class="cat-pupil" data-eye-x="235" data-eye-y="173">
                <circle cx="235" cy="175" r="8" fill="#1f2937" />
                <circle cx="232" cy="171" r="3.2" fill="#ffffff" />
              </g>
              <path d="M207 189 C214 187 221 187 228 189 C225 198 217 203 210 199 C205 197 204 193 207 189Z" fill="#ff6f8d" />
              <path d="M209 200 C199 210 188 209 183 202" fill="none" stroke="#76551e" stroke-width="4" stroke-linecap="round" />
              <path d="M210 200 C219 210 230 209 235 202" fill="none" stroke="#76551e" stroke-width="4" stroke-linecap="round" />
              <g class="cat-whiskers-group">
                <path d="M143 210 L104 215" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
                <path d="M145 223 L104 228" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
                <path d="M277 210 L316 215" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
                <path d="M275 223 L316 228" stroke="#b88622" stroke-width="4" stroke-linecap="round" opacity="0.75" />
              </g>
            </g>
            <path d="M138 278 C166 287 250 287 282 278" stroke="#e1a12b" stroke-width="5" stroke-linecap="round" opacity="0.38" />
          </svg>
        </div>
      </aside>

      <section class="login-right-panel">
        <form class="login-card" @submit.prevent="submitLogin">
          <h2>账号登录</h2>
          <p class="login-subtitle">请输入账号信息，安全进入管理平台。</p>

          <label class="login-form-group" for="login-account">
            <span>用户名</span>
            <div class="login-input-wrapper">
              <AppIcon name="user" :size="18" />
              <input id="login-account" ref="usernameInput" v-model="account" type="text" autocomplete="username" placeholder="请输入用户名" />
            </div>
          </label>

          <label class="login-form-group" for="login-password">
            <span>密码</span>
            <div class="login-input-wrapper">
              <AppIcon name="lock" :size="18" />
              <input id="login-password" ref="passwordInput" v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
            </div>
          </label>

          <div class="login-options">
            <label class="login-remember">
              <input v-model="remember" type="checkbox" />
              记住我
            </label>
          </div>

          <p v-if="errorMessage" class="login-error">{{ errorMessage }}</p>
          <button class="login-btn" type="submit" :disabled="!canSubmit">
            <span>{{ isSubmitting ? '登录中...' : '登录' }}</span>
          </button>
        </form>
      </section>
    </section>
  </main>
</template>
