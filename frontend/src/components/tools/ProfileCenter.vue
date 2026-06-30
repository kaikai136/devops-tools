<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { apiGet, apiPost, apiPut } from '../../api';
import { useAppContext } from '../../appContext';
import { passwordsMismatch, usePasswordStrength } from '../../composables/usePasswordStrength';
import type { ProfilePayload, TwoFactorSetupPayload } from '../../types';
import { formatDateTime } from '../../utils/datetime';
import { errorMessage } from '../../utils/errors';
import AppIcon from '../common/AppIcon.vue';

const DEFAULT_AVATAR = '/ops-captain-icon.png';

const { activeTool, currentUser, updateCurrentUser, showToast, logout, copyText } = useAppContext();

const isLoading = ref(false);
const isSavingProfile = ref(false);
const isUploadingAvatar = ref(false);
const isChangingPassword = ref(false);
const isPreparingTwoFactor = ref(false);
const isConfirmingTwoFactor = ref(false);
const isDisablingTwoFactor = ref(false);
const message = ref('');
const avatarInput = ref<HTMLInputElement | null>(null);
const setupPayload = ref<TwoFactorSetupPayload | null>(null);
const twoFactorCode = ref('');
const disableCode = ref('');
const disablePassword = ref('');
const profileForm = ref({ username: '', first_name: '', email: '' });
const passwordForm = ref({ currentPassword: '', newPassword: '', confirmPassword: '' });

const passwordStrength = usePasswordStrength(computed(() => passwordForm.value.newPassword));
const profileAvatar = computed(() => currentUser.value?.avatarUrl || DEFAULT_AVATAR);
const displayName = computed(() => currentUser.value?.displayName || currentUser.value?.first_name || currentUser.value?.username || '未命名用户');
const accountLabel = computed(() => currentUser.value?.username || currentUser.value?.email || '当前账户');
const roleTags = computed(() => {
  const user = currentUser.value;
  if (!user) return ['普通用户'];
  const tags = [];
  if (user.is_superuser) tags.push('超级管理员');
  if (user.is_staff) tags.push('系统管理员');
  if (!tags.length) tags.push('普通用户');
  tags.push(user.is_active ? '已启用' : '已停用');
  return tags;
});
const passwordMismatch = computed(() => passwordsMismatch(passwordForm.value.newPassword, passwordForm.value.confirmPassword));
const canSubmitPassword = computed(() => Boolean(passwordForm.value.currentPassword && passwordStrength.isStrong.value && passwordForm.value.confirmPassword && !passwordMismatch.value));
const twoFactorEnabled = computed(() => Boolean(currentUser.value?.twoFactorEnabled));

onMounted(loadProfile);

async function loadProfile() {
  if (activeTool.value !== 'profile') return;
  isLoading.value = true;
  message.value = '';
  try {
    const payload = await apiGet<ProfilePayload>('/api/profile/');
    syncUser(payload);
    fillProfileForm(payload);
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isLoading.value = false;
  }
}

function fillProfileForm(payload: ProfilePayload) {
  profileForm.value = {
    username: payload.user.username,
    first_name: payload.user.first_name || payload.user.displayName || '',
    email: payload.user.email || '',
  };
}

function syncUser(payload: ProfilePayload | { user: ProfilePayload['user'] }) {
  updateCurrentUser(payload.user);
}

function triggerAvatarUpload() {
  avatarInput.value?.click();
}

async function uploadAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;

  isUploadingAvatar.value = true;
  message.value = '';
  try {
    const body = new FormData();
    body.append('avatar', file);
    const response = await fetch('/api/profile/avatar/', { method: 'POST', body, credentials: 'include' });
    const payload = await readProfileResponse(response);
    syncUser(payload);
    showToast('头像已更新', '新的头像已经保存。');
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isUploadingAvatar.value = false;
    if (avatarInput.value) avatarInput.value.value = '';
  }
}

async function saveProfile() {
  isSavingProfile.value = true;
  message.value = '';
  try {
    const payload = await apiPut<ProfilePayload>('/api/profile/', profileForm.value);
    syncUser(payload);
    fillProfileForm(payload);
    showToast('资料已保存', '个人资料已同步更新。');
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isSavingProfile.value = false;
  }
}

async function changePassword() {
  if (!canSubmitPassword.value) return;
  isChangingPassword.value = true;
  message.value = '';
  try {
    const payload = await apiPost<{ ok: boolean; user: ProfilePayload['user'] }>('/api/profile/password/', passwordForm.value);
    syncUser(payload);
    passwordForm.value = { currentPassword: '', newPassword: '', confirmPassword: '' };
    showToast('密码已更新', '当前登录状态已保持有效。');
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isChangingPassword.value = false;
  }
}

async function prepareTwoFactor() {
  isPreparingTwoFactor.value = true;
  message.value = '';
  try {
    setupPayload.value = await apiPost<TwoFactorSetupPayload>('/api/profile/2fa/setup/', {});
    twoFactorCode.value = '';
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isPreparingTwoFactor.value = false;
  }
}

async function confirmTwoFactor() {
  isConfirmingTwoFactor.value = true;
  message.value = '';
  try {
    const payload = await apiPost<ProfilePayload>('/api/profile/2fa/confirm/', { code: twoFactorCode.value });
    syncUser(payload);
    setupPayload.value = null;
    twoFactorCode.value = '';
    showToast('2FA 已启用', '下次登录需要输入动态验证码。');
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isConfirmingTwoFactor.value = false;
  }
}

async function disableTwoFactor() {
  isDisablingTwoFactor.value = true;
  message.value = '';
  try {
    const payload = await apiPost<ProfilePayload>('/api/profile/2fa/disable/', { password: disablePassword.value, code: disableCode.value });
    syncUser(payload);
    disablePassword.value = '';
    disableCode.value = '';
    showToast('2FA 已关闭', '登录已恢复为账号密码验证。');
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isDisablingTwoFactor.value = false;
  }
}

async function readProfileResponse(response: Response): Promise<ProfilePayload> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload && typeof payload === 'object' && 'error' in payload ? String(payload.error) : '头像上传失败');
  }
  return payload as ProfilePayload;
}
</script>

<template>
  <section v-if="activeTool === 'profile'" class="profile-center-page">
    <p v-if="message" class="profile-message">{{ message }}</p>
    <p v-if="isLoading" class="profile-message info">正在加载个人资料...</p>

    <aside class="profile-overview-card">
      <div class="profile-avatar-frame">
        <img :src="profileAvatar" alt="用户头像" />
        <button type="button" :disabled="isUploadingAvatar" title="上传头像" aria-label="上传头像" @click="triggerAvatarUpload">
          <AppIcon name="upload" :size="16" />
        </button>
        <input ref="avatarInput" hidden type="file" accept="image/png,image/jpeg,image/webp" @change="uploadAvatar" />
      </div>
      <strong>{{ displayName }}</strong>
      <span>{{ accountLabel }}</span>
      <div class="profile-role-tags">
        <em v-for="tag in roleTags" :key="tag">{{ tag }}</em>
      </div>
      <dl>
        <div>
          <dt>最后登录</dt>
          <dd>{{ formatDateTime(currentUser?.last_login, '暂无记录') }}</dd>
        </div>
        <div>
          <dt>创建时间</dt>
          <dd>{{ formatDateTime(currentUser?.date_joined, '暂无记录') }}</dd>
        </div>
        <div>
          <dt>登录保护</dt>
          <dd>{{ twoFactorEnabled ? '已启用 2FA' : '未启用 2FA' }}</dd>
        </div>
      </dl>
      <button class="profile-logout-button" type="button" @click="logout">
        <AppIcon name="logout" :size="16" />
        退出登录
      </button>
    </aside>

    <div class="profile-settings-stack">
      <section class="profile-panel">
        <header>
          <div>
            <h2>基本资料</h2>
            <p>用于系统显示、登录识别和通知信息。</p>
          </div>
          <AppIcon name="user" :size="20" />
        </header>
        <form class="profile-form-grid" @submit.prevent="saveProfile">
          <label>
            <span>用户名</span>
            <input v-model.trim="profileForm.username" autocomplete="username" />
          </label>
          <label>
            <span>显示名</span>
            <input v-model.trim="profileForm.first_name" placeholder="例如：运维船长" />
          </label>
          <label>
            <span>邮箱</span>
            <input v-model.trim="profileForm.email" type="email" autocomplete="email" placeholder="name@example.com" />
          </label>
          <div class="profile-actions">
            <button class="profile-primary-button" type="submit" :disabled="isSavingProfile">
              {{ isSavingProfile ? '保存中...' : '保存资料' }}
            </button>
          </div>
        </form>
      </section>

      <section class="profile-panel">
        <header>
          <div>
            <h2>密码安全</h2>
            <p>修改密码后当前会话会继续保持登录。</p>
          </div>
          <AppIcon name="lock" :size="20" />
        </header>
        <form class="profile-form-grid" @submit.prevent="changePassword">
          <label>
            <span>当前密码</span>
            <input v-model="passwordForm.currentPassword" type="password" autocomplete="current-password" />
          </label>
          <label>
            <span>新密码</span>
            <input v-model="passwordForm.newPassword" type="password" autocomplete="new-password" />
          </label>
          <label>
            <span>确认新密码</span>
            <input v-model="passwordForm.confirmPassword" type="password" autocomplete="new-password" />
          </label>
          <div class="profile-password-meter" :class="passwordStrength.className.value">
            <div>
              <span>{{ passwordStrength.hint.value }}</span>
              <strong v-if="passwordStrength.label.value">{{ passwordStrength.label.value }}</strong>
            </div>
            <i v-for="rule in passwordStrength.rules.value" :key="rule.key" :class="{ active: rule.valid }"></i>
          </div>
          <p v-if="passwordMismatch" class="profile-inline-error">两次输入的新密码不一致。</p>
          <div class="profile-actions">
            <button class="profile-primary-button" type="submit" :disabled="!canSubmitPassword || isChangingPassword">
              {{ isChangingPassword ? '更新中...' : '更新密码' }}
            </button>
          </div>
        </form>
      </section>

      <section class="profile-panel profile-security-panel">
        <header>
          <div>
            <h2>双因素认证</h2>
            <p>启用后，账号密码验证成功后还需要输入认证器验证码。</p>
          </div>
          <span class="profile-status-pill" :class="{ enabled: twoFactorEnabled }">{{ twoFactorEnabled ? '已启用' : '未启用' }}</span>
        </header>

        <div v-if="!twoFactorEnabled" class="profile-2fa-setup">
          <button class="profile-primary-button" type="button" :disabled="isPreparingTwoFactor" @click="prepareTwoFactor">
            <AppIcon name="qr" :size="16" />
            {{ isPreparingTwoFactor ? '生成中...' : '生成认证二维码' }}
          </button>

          <div v-if="setupPayload" class="profile-qr-setup">
            <img :src="setupPayload.qrDataUrl" alt="TOTP 二维码" />
            <div>
              <strong>扫码添加到认证器</strong>
              <p>无法扫码时，手动输入密钥。</p>
              <code>{{ setupPayload.secret }}</code>
              <button type="button" @click="copyText(setupPayload.secret, '密钥已复制。')">复制密钥</button>
            </div>
          </div>

          <form v-if="setupPayload" class="profile-2fa-form" @submit.prevent="confirmTwoFactor">
            <input v-model.trim="twoFactorCode" inputmode="numeric" maxlength="6" placeholder="输入 6 位验证码" />
            <button class="profile-primary-button" type="submit" :disabled="twoFactorCode.length !== 6 || isConfirmingTwoFactor">
              {{ isConfirmingTwoFactor ? '验证中...' : '启用 2FA' }}
            </button>
          </form>
        </div>

        <form v-else class="profile-2fa-form danger-zone" @submit.prevent="disableTwoFactor">
          <input v-model="disablePassword" type="password" autocomplete="current-password" placeholder="当前密码" />
          <input v-model.trim="disableCode" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
          <button class="profile-danger-button" type="submit" :disabled="!disablePassword || disableCode.length !== 6 || isDisablingTwoFactor">
            {{ isDisablingTwoFactor ? '关闭中...' : '关闭 2FA' }}
          </button>
        </form>
      </section>
    </div>
  </section>
</template>
