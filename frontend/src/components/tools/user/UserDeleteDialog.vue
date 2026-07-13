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
      <h2>删除用户</h2>
      <p>确定删除账户“{{ user.username }}”吗？</p>
      <div class="user-form-actions">
        <button type="button" @click="$emit('close')">取消</button>
        <button class="danger" type="button" @click="$emit('confirm')">删除</button>
      </div>
    </article>
  </div>
</template>
