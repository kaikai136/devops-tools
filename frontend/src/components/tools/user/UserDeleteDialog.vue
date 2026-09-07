<script setup lang="ts">
import type { SystemUser } from '../../../composables/features/useUserManager';

defineProps<{ user: SystemUser }>();

defineEmits<{
  close: [];
  confirm: [];
}>();
</script>

<template>
  <el-dialog
    :model-value="true"
    title="删除用户"
    width="420px"
    class="user-form-dialog user-popup-dialog"
    :close-on-click-modal="false"
    @update:model-value="(visible) => { if (!visible) $emit('close'); }"
  >
    <p class="popup-body popup-danger">确定删除账户“{{ user.username }}”吗？</p>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="danger" @click="$emit('confirm')">删除</el-button>
    </template>
  </el-dialog>
</template>
