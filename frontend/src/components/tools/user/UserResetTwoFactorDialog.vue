<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';
import type { SystemUser } from '../../../composables/features/useUserManager';

defineProps<{ user: SystemUser }>();

defineEmits<{
  close: [];
  confirm: [];
}>();
</script>

<template>
  <div class="modal-backdrop user-modal-backdrop">
    <article class="user-form-modal compact">
      <button class="modal-close" type="button" aria-label="关闭" @click="$emit('close')"><AppIcon name="x" :size="16" /></button>
      <h2>重置 2FA</h2>
      <p>确定重置账户“{{ user.username }}”的 2FA 吗？旧验证码会失效，用户下次登录需要重新扫码绑定。</p>
      <div class="user-form-actions">
        <button type="button" @click="$emit('close')">取消</button>
        <button class="danger" type="button" @click="$emit('confirm')">重置</button>
      </div>
    </article>
  </div>
</template>
