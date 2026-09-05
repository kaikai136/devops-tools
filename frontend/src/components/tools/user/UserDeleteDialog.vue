<script setup lang="ts">
import type { SystemUser } from '../../../composables/features/useUserManager';

defineProps<{ user: SystemUser }>();

defineEmits<{
  close: [];
  confirm: [];
}>();
</script>

<template>
  <NativeDialog
    :model-value="true"
    title="删除用户"
    width="420px"
    class="user-form-dialog"
    :close-on-click-modal="false"
    @update:model-value="(visible) => { if (!visible) $emit('close'); }"
  >
    <p>确定删除账户“{{ user.username }}”吗？</p>
    <template #footer>
      <NativeButton @click="$emit('close')">取消</NativeButton>
      <NativeButton type="danger" @click="$emit('confirm')">删除</NativeButton>
    </template>
  </NativeDialog>
</template>
