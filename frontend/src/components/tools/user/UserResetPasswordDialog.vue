<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';
import type { PasswordRule, PasswordStrengthLevel } from '@shared/composables/usePasswordStrength';

defineProps<{
  rules: PasswordRule[];
  strength: number;
  strengthClass: PasswordStrengthLevel;
  strengthText: string;
  hint: string;
}>();

const password = defineModel<string>('password', { required: true });

defineEmits<{
  close: [];
  submit: [];
}>();
</script>

<template>
  <el-dialog
    :model-value="true"
    title="重置密码"
    width="460px"
    class="user-form-dialog"
    :close-on-click-modal="false"
    @update:model-value="(visible) => { if (!visible) $emit('close'); }"
  >
    <el-form label-position="top" class="user-form-modal compact" @submit.prevent="$emit('submit')">
      <el-form-item label="新密码" required>
        <el-input v-model="password" autofocus type="password" autocomplete="new-password" placeholder="至少 8 位，含数字和大小写字母" show-password />
      </el-form-item>
      <div class="user-password-meter compact-meter" :class="strengthClass">
        <div class="user-password-meter-head">
          <span>{{ hint }}</span>
          <strong v-if="strengthText">{{ strengthText }}</strong>
        </div>
        <div class="user-password-meter-track" aria-hidden="true">
          <i v-for="(rule, index) in rules" :key="rule.key" :class="{ active: index < strength }"></i>
        </div>
      </div>
      <div class="user-password-rules">
        <span v-for="rule in rules" :key="rule.key" :class="{ passed: rule.valid }">
          <AppIcon :name="rule.valid ? 'circleCheck' : 'circleHelp'" :size="14" />
          {{ rule.label }}
        </span>
      </div>
    </el-form>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" @click="$emit('submit')">保存</el-button>
    </template>
  </el-dialog>
</template>
