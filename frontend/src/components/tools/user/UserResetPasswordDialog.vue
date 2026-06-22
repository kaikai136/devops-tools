<script setup lang="ts">
import AppIcon from '../../common/AppIcon.vue';
import type { PasswordRule, PasswordStrengthLevel } from '../../../composables/usePasswordStrength';

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
  <div class="modal-backdrop user-modal-backdrop">
    <form class="user-form-modal compact" @submit.prevent="$emit('submit')">
      <button class="modal-close" type="button" aria-label="关闭" @click="$emit('close')"><AppIcon name="x" :size="16" /></button>
      <h2>重置密码</h2>
      <label class="required">
        <span>新密码</span>
        <input v-model="password" autofocus type="password" autocomplete="new-password" placeholder="至少 8 位，含数字和大小写字母" />
      </label>
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
      <div class="user-form-actions">
        <button type="button" @click="$emit('close')">取消</button>
        <button class="user-primary-button" type="submit">保存</button>
      </div>
    </form>
  </div>
</template>
