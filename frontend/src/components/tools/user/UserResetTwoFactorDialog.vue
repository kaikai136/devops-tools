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
    title="重置 2FA"
    width="460px"
    class="user-form-dialog"
    :close-on-click-modal="false"
    @update:model-value="(visible) => { if (!visible) $emit('close'); }"
  >
    <p>确定重置账户“{{ user.username }}”的 2FA 吗？旧验证码会失效，用户下次登录需要重新扫码绑定。</p>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="danger" @click="$emit('confirm')">重置</el-button>
    </template>
  </el-dialog>
</template>
